import re
from collections.abc import Callable
from datetime import date, time
from typing import Any

from fastapi import HTTPException
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Appointment, AvailableSlot, Doctor
from app.schemas import (
    BookingRequest,
    CancelRequest,
    normalize_phone_number,
)
from app.services import (
    book_appointment,
    cancel_appointment,
    list_appointments,
    list_availability,
    list_doctors,
)


_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


class AppointmentTools:
    """Database-backed tools and confirmation state for one voice call."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self._session_factory = session_factory
        self._confirmed_phone: str | None = None
        self._pending_phone: str | None = None
        self._pending_booking: tuple[str, int, int] | None = None
        self._pending_cancellation: tuple[str, int] | None = None

    def get_tools(self) -> list[Callable[..., Any]]:
        return [
            self.check_doctor_availability,
            self.book_appointment,
            self.cancel_appointment,
        ]

    async def check_doctor_availability(
        self,
        params: FunctionCallParams,
        doctor_name: str | None = None,
        speciality: str | None = None,
        appointment_date: str | None = None,
    ) -> None:
        """Find real future slots by doctor name or speciality.

        Args:
            doctor_name: Optional full or partial doctor name to search for.
            speciality: Optional speciality to search for.
            appointment_date: Optional date in YYYY-MM-DD format.
        """
        name_query = (doctor_name or "").strip()
        speciality_query = (speciality or "").strip()
        if not name_query and not speciality_query:
            await params.result_callback(
                {
                    "success": False,
                    "message": "Ask which doctor or speciality the patient prefers.",
                    "available_slots": [],
                }
            )
            return

        try:
            selected_date = (
                date.fromisoformat(appointment_date)
                if appointment_date
                else None
            )
        except ValueError:
            await params.result_callback(
                {
                    "success": False,
                    "message": "The appointment date must be in YYYY-MM-DD format.",
                    "available_slots": [],
                }
            )
            return

        if len(name_query) > 120 or len(speciality_query) > 120:
            await params.result_callback(
                {
                    "success": False,
                    "message": "The doctor name or speciality is too long.",
                    "available_slots": [],
                }
            )
            return

        with self._session_factory() as db:
            doctors = list_doctors(db)
            matching_doctors = [
                doctor
                for doctor in doctors
                if (
                    not name_query
                    or name_query.casefold() in doctor.name.casefold()
                )
                and (
                    not speciality_query
                    or speciality_query.casefold()
                    in doctor.speciality.casefold()
                )
            ]
            if not matching_doctors:
                await params.result_callback(
                    {
                        "success": False,
                        "message": "No doctor matched that name or speciality.",
                        "available_slots": [],
                    }
                )
                return

            matching_doctor_ids = {doctor.id for doctor in matching_doctors}
            slots = list_availability(db, doctor_id=None, appointment_date=selected_date)
            matches = [
                slot
                for slot in slots
                if slot.doctor_id in matching_doctor_ids
            ]
            result = [
                {
                    "doctor_id": slot.doctor_id,
                    "doctor_name": slot.doctor.name,
                    "speciality": slot.doctor.speciality,
                    "slot_id": slot.id,
                    "appointment_date": slot.appointment_date.isoformat(),
                    "appointment_time": slot.appointment_time.strftime("%H:%M"),
                }
                for slot in matches
            ]

        await params.result_callback(
            {
                "success": True,
                "message": (
                    "Available slots found."
                    if result
                    else "No available slots matched that doctor, speciality, or date."
                ),
                "available_slots": result,
            }
        )

    async def book_appointment(
        self,
        params: FunctionCallParams,
        phone_number: str,
        doctor_id: int,
        slot_id: int,
        patient_name: str | None = None,
    ) -> None:
        """Book an available slot after phone and slot confirmation.

        Args:
            phone_number: The phone number spoken and confirmed by the patient.
            doctor_id: The ID of the doctor selected by the patient.
            slot_id: The ID of the available time slot selected by the patient.
            patient_name: Optional patient name.
        """
        try:
            normalized_phone = normalize_phone_number(phone_number)
            request = BookingRequest(
                phone_number=normalized_phone,
                doctor_id=doctor_id,
                slot_id=slot_id,
                patient_name=patient_name,
            )
        except ValueError as error:
            await params.result_callback(
                {"success": False, "message": str(error)}
            )
            return

        if not _phone_was_spoken(params.context, request.phone_number):
            await params.result_callback(
                {
                    "success": False,
                    "message": (
                        "The phone number must come from the patient's spoken "
                        "words. Ask them to say it one digit at a time."
                    ),
                }
            )
            return

        if self._decline_phone(request.phone_number, params.context):
            await params.result_callback(
                {
                    "success": False,
                    "message": (
                        "The phone number was not confirmed. Do not book; ask for "
                        "the correct number only if the patient wants to continue."
                    ),
                }
            )
            return

        if not self._confirm_phone(request.phone_number, params.context):
            await params.result_callback(
                {
                    "success": False,
                    "confirmation_required": "phone_number",
                    "message": (
                        f"Read the full phone number {request.phone_number} back "
                        "to the patient and ask if it is correct. Do not book yet."
                    ),
                }
            )
            return

        with self._session_factory() as db:
            if db.get(Doctor, doctor_id) is None:
                self._pending_booking = None
                await params.result_callback(
                    {
                        "success": False,
                        "message": "The selected doctor was not found.",
                        "available_slots": [],
                    }
                )
                return

            slot = _find_available_slot(db, doctor_id, slot_id)
            if slot is None:
                self._pending_booking = None
                alternatives = _available_slots_for_doctor(db, doctor_id)
                await params.result_callback(
                    {
                        "success": False,
                        "message": (
                            "That slot is no longer available. Offer only these "
                            "currently available alternatives."
                        ),
                        "available_slots": alternatives,
                    }
                )
                return

            target = (request.phone_number, doctor_id, slot_id)
            if (
                self._pending_booking == target
                and _declined_details(
                    params.context,
                    doctor_name=slot.doctor.name,
                    appointment_date=slot.appointment_date,
                    appointment_time=slot.appointment_time,
                    action_word="book",
                )
            ):
                self._pending_booking = None
                await params.result_callback(
                    {
                        "success": False,
                        "message": (
                            "Understood. The appointment was not booked."
                        ),
                    }
                )
                return

            if self._pending_booking != target or not _confirmed_details(
                params.context,
                doctor_name=slot.doctor.name,
                appointment_date=slot.appointment_date,
                appointment_time=slot.appointment_time,
                action_word="book",
            ):
                self._pending_booking = target
                self._pending_cancellation = None
                await params.result_callback(
                    {
                        "success": False,
                        "confirmation_required": "booking",
                        "message": (
                            f"Ask whether to book {slot.doctor.name} on "
                            f"{slot.appointment_date.isoformat()} at "
                            f"{slot.appointment_time.strftime('%H:%M')}. "
                            "Wait for an explicit yes before calling this tool again."
                        ),
                    }
                )
                return

            try:
                appointment = book_appointment(db, request)
            except HTTPException as error:
                self._pending_booking = None
                alternatives = _available_slots_for_doctor(
                    db,
                    doctor_id,
                    slot.appointment_date,
                )
                await params.result_callback(
                    {
                        "success": False,
                        "message": error.detail,
                        "available_slots": alternatives,
                    }
                )
                return

            self._pending_booking = None
            self._pending_cancellation = None
            response = {
                "success": True,
                "message": "Appointment booked successfully.",
                "appointment": {
                    "appointment_id": appointment.id,
                    "doctor_name": slot.doctor.name,
                    "appointment_date": appointment.appointment_date.isoformat(),
                    "appointment_time": appointment.appointment_time.strftime("%H:%M"),
                    "status": appointment.status,
                },
            }

        await params.result_callback(response)

    async def cancel_appointment(
        self,
        params: FunctionCallParams,
        phone_number: str,
        appointment_id: int | None = None,
    ) -> None:
        """Cancel a booked appointment owned by the confirmed phone number.

        Args:
            phone_number: The phone number spoken and confirmed by the patient.
            appointment_id: Optional appointment ID when the patient knows it.
        """
        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as error:
            await params.result_callback(
                {"success": False, "message": str(error)}
            )
            return

        if not _phone_was_spoken(params.context, normalized_phone):
            await params.result_callback(
                {
                    "success": False,
                    "message": (
                        "The phone number must come from the patient's spoken "
                        "words. Ask them to say it one digit at a time."
                    ),
                }
            )
            return

        if self._decline_phone(normalized_phone, params.context):
            await params.result_callback(
                {
                    "success": False,
                    "message": (
                        "The phone number was not confirmed. Do not cancel; ask "
                        "for the correct number only if the patient wants to continue."
                    ),
                }
            )
            return

        if not self._confirm_phone(normalized_phone, params.context):
            await params.result_callback(
                {
                    "success": False,
                    "confirmation_required": "phone_number",
                    "message": (
                        f"Read the full phone number {normalized_phone} back "
                        "to the patient and ask if it is correct. Do not cancel yet."
                    ),
                }
            )
            return

        with self._session_factory() as db:
            appointments = list_appointments(
                db,
                appointment_status="booked",
                phone_number=normalized_phone,
            )
            appointment = next(
                (
                    item
                    for item in appointments
                    if item.id == appointment_id
                ),
                None,
            ) if appointment_id is not None else None

            if appointment_id is None and self._pending_cancellation is not None:
                pending_phone, pending_id = self._pending_cancellation
                if pending_phone == normalized_phone:
                    appointment = next(
                        (item for item in appointments if item.id == pending_id),
                        None,
                    )

            if appointment is None and appointment_id is None:
                if not appointments:
                    self._pending_cancellation = None
                    await params.result_callback(
                        {
                            "success": False,
                            "message": (
                                "No active appointment was found for that phone number."
                            ),
                        }
                    )
                    return
                if len(appointments) > 1:
                    self._pending_cancellation = None
                    await params.result_callback(
                        {
                            "success": True,
                            "message": (
                                "Ask which appointment they mean. Do not cancel "
                                "until one appointment is selected."
                            ),
                            "appointments": [
                                _appointment_summary(item)
                                for item in appointments
                            ],
                        }
                    )
                    return
                appointment = appointments[0]

            if appointment is None:
                self._pending_cancellation = None
                await params.result_callback(
                    {
                        "success": False,
                        "message": (
                            "No active appointment with that ID belongs to this "
                            "phone number."
                        ),
                    }
                )
                return

            target = (normalized_phone, appointment.id)
            if (
                self._pending_cancellation == target
                and _declined_details(
                    params.context,
                    doctor_name=appointment.doctor.name,
                    appointment_date=appointment.appointment_date,
                    appointment_time=appointment.appointment_time,
                    action_word="cancel",
                )
            ):
                self._pending_cancellation = None
                await params.result_callback(
                    {
                        "success": False,
                        "message": (
                            "Understood. The appointment was not cancelled."
                        ),
                    }
                )
                return

            if self._pending_cancellation != target or not _confirmed_details(
                params.context,
                doctor_name=appointment.doctor.name,
                appointment_date=appointment.appointment_date,
                appointment_time=appointment.appointment_time,
                action_word="cancel",
            ):
                self._pending_cancellation = target
                self._pending_booking = None
                await params.result_callback(
                    {
                        "success": False,
                        "confirmation_required": "cancellation",
                        "message": (
                            f"Ask whether to cancel appointment {appointment.id} "
                            f"with {appointment.doctor.name} on "
                            f"{appointment.appointment_date.isoformat()} at "
                            f"{appointment.appointment_time.strftime('%H:%M')}. "
                            "Wait for an explicit yes before calling this tool again."
                        ),
                    }
                )
                return

            request = CancelRequest(
                phone_number=normalized_phone,
                appointment_id=appointment.id,
            )
            try:
                cancelled = cancel_appointment(db, request)
            except HTTPException as error:
                self._pending_cancellation = None
                await params.result_callback(
                    {"success": False, "message": error.detail}
                )
                return

            self._pending_cancellation = None
            response = {
                "success": True,
                "message": "Appointment cancelled successfully.",
                "appointment": _appointment_summary(cancelled),
            }

        await params.result_callback(response)

    def _confirm_phone(self, phone_number: str, context: LLMContext) -> bool:
        if self._confirmed_phone == phone_number:
            return True

        if (
            self._pending_phone in (None, phone_number)
            and _confirmed_phone_exchange(context, phone_number)
        ):
            self._confirmed_phone = phone_number
            self._pending_phone = None
            return True

        self._confirmed_phone = None
        self._pending_phone = phone_number
        self._pending_booking = None
        self._pending_cancellation = None
        return False

    def _decline_phone(self, phone_number: str, context: LLMContext) -> bool:
        if (
            self._pending_phone != phone_number
            or not _declined_phone_exchange(context, phone_number)
        ):
            return False

        self._pending_phone = None
        self._confirmed_phone = None
        self._pending_booking = None
        self._pending_cancellation = None
        return True


def _find_available_slot(
    db: Session,
    doctor_id: int,
    slot_id: int,
) -> AvailableSlot | None:
    return next(
        (
            slot
            for slot in list_availability(db, doctor_id, None)
            if slot.id == slot_id
        ),
        None,
    )


def _available_slots_for_doctor(
    db: Session,
    doctor_id: int,
    appointment_date: date | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "doctor_id": slot.doctor_id,
            "doctor_name": slot.doctor.name,
            "speciality": slot.doctor.speciality,
            "slot_id": slot.id,
            "appointment_date": slot.appointment_date.isoformat(),
            "appointment_time": slot.appointment_time.strftime("%H:%M"),
        }
        for slot in list_availability(db, doctor_id, appointment_date)
    ]


def _appointment_summary(appointment: Appointment) -> dict[str, Any]:
    return {
        "appointment_id": appointment.id,
        "doctor_name": appointment.doctor.name,
        "appointment_date": appointment.appointment_date.isoformat(),
        "appointment_time": appointment.appointment_time.strftime("%H:%M"),
        "status": appointment.status,
    }


def _phone_was_spoken(context: LLMContext, phone_number: str) -> bool:
    expected_digits = re.sub(r"\D", "", phone_number)
    for role, text in _conversation_messages(context):
        if role != "user":
            continue

        current_digits: list[str] = []
        sequences: list[str] = []
        for token in re.findall(r"\+?\d+|[a-z]+", text.casefold()):
            if token in _DIGIT_WORDS:
                current_digits.append(_DIGIT_WORDS[token])
            elif token.lstrip("+").isdigit():
                current_digits.append(token.lstrip("+"))
            elif token == "plus":
                continue
            else:
                if current_digits:
                    sequences.append("".join(current_digits))
                    current_digits = []
        if current_digits:
            sequences.append("".join(current_digits))

        if expected_digits in sequences:
            return True
    return False


def _confirmed_phone_exchange(context: LLMContext, phone_number: str) -> bool:
    exchange = _latest_exchange(context)
    if exchange is None:
        return False
    assistant_text, user_text = exchange
    assistant_digits = re.sub(r"\D", "", assistant_text)
    return (
        phone_number.lstrip("+") in assistant_digits
        and _asks_for_confirmation(assistant_text)
        and _is_explicit_yes(user_text)
    )


def _details_exchange_matches(
    context: LLMContext,
    *,
    doctor_name: str,
    appointment_date: date,
    appointment_time: time,
    action_word: str,
    user_matcher: Callable[[str], bool],
) -> bool:
    exchange = _latest_exchange(context)
    if exchange is None:
        return False
    assistant_text, user_text = exchange
    lower_text = assistant_text.casefold()
    return (
        doctor_name.casefold() in lower_text
        and _date_mentioned(assistant_text, appointment_date)
        and _time_mentioned(assistant_text, appointment_time)
        and action_word in lower_text
        and _asks_for_confirmation(assistant_text)
        and user_matcher(user_text)
    )


def _date_mentioned(text: str, target_date: date) -> bool:
    lower_text = text.casefold()
    if target_date.isoformat() in lower_text:
        return True

    full_month = target_date.strftime("%B").casefold()
    short_month = target_date.strftime("%b").casefold()
    month_pattern = rf"(?:{re.escape(full_month)}|{re.escape(short_month)})"
    day_pattern = rf"0?{target_date.day}(?:st|nd|rd|th)?"
    spoken_match = re.search(
        rf"\b{month_pattern}\s+{day_pattern}\b"
        rf"|\b{day_pattern}\s+(?:of\s+)?{month_pattern}\b",
        lower_text,
    )
    if not spoken_match:
        return False

    years = re.findall(r"\b(?:19|20)\d{2}\b", lower_text)
    return not years or str(target_date.year) in years


def _time_mentioned(text: str, target_time: time) -> bool:
    lower_text = text.casefold()
    hh_mm = target_time.strftime("%H:%M")
    h_mm = f"{target_time.hour}:{target_time.minute:02d}"
    wrong_meridiem = "pm|p\\.m\\." if target_time.hour < 12 else "am|a\\.m\\."
    if re.search(
        rf"(?<!\d)(?:{re.escape(hh_mm)}|{re.escape(h_mm)})"
        rf"(?!\d)(?!\s*(?:{wrong_meridiem}))",
        lower_text,
    ):
        return True

    hour12 = target_time.hour % 12 or 12
    meridiem = "am|a\\.m\\." if target_time.hour < 12 else "pm|p\\.m\\."
    minute_part = (
        "(?::00)?"
        if target_time.minute == 0
        else rf":{target_time.minute:02d}"
    )
    return bool(
        re.search(
            rf"(?<!\d)0?{hour12}{minute_part}\s*(?:{meridiem})(?![a-z])",
            lower_text,
        )
    )


def _confirmed_details(
    context: LLMContext,
    *,
    doctor_name: str,
    appointment_date: date,
    appointment_time: time,
    action_word: str,
) -> bool:
    return _details_exchange_matches(
        context,
        doctor_name=doctor_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        action_word=action_word,
        user_matcher=_is_explicit_yes,
    )


def _declined_phone_exchange(context: LLMContext, phone_number: str) -> bool:
    exchange = _latest_exchange(context)
    if exchange is None:
        return False
    assistant_text, user_text = exchange
    assistant_digits = re.sub(r"\D", "", assistant_text)
    return (
        phone_number.lstrip("+") in assistant_digits
        and _asks_for_confirmation(assistant_text)
        and _is_explicit_no(user_text)
    )


def _declined_details(
    context: LLMContext,
    *,
    doctor_name: str,
    appointment_date: date,
    appointment_time: time,
    action_word: str,
) -> bool:
    return _details_exchange_matches(
        context,
        doctor_name=doctor_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        action_word=action_word,
        user_matcher=_is_explicit_no,
    )


def _asks_for_confirmation(text: str) -> bool:
    lower_text = text.casefold()
    return "?" in text and any(
        phrase in lower_text
        for phrase in (
            "confirm",
            "correct",
            "right",
            "should i",
            "shall i",
            "would you like",
            "go ahead",
            "proceed",
            "do you want",
        )
    )


def _is_explicit_yes(text: str) -> bool:
    normalized = re.sub(r"[^a-z ]", " ", text.casefold())
    normalized = " ".join(normalized.split())
    if any(
        word in normalized.split()
        for word in ("no", "not", "never", "wait", "stop", "but")
    ):
        return False
    return normalized in {
        "yes",
        "yes please",
        "yes please do it",
        "yes do it",
        "yes book it",
        "yes cancel it",
        "yes go ahead",
        "yes that is correct",
        "yes that is right",
        "yes confirm",
        "yes i confirm",
        "yes sure",
        "yes okay",
        "yes ok",
        "yeah",
        "yeah please",
        "yep",
        "correct",
        "that is correct",
        "that is right",
        "confirmed",
        "i confirm",
        "please do",
        "please do it",
        "go ahead",
        "go ahead please",
        "book it",
        "cancel it",
        "sure",
        "okay",
        "ok",
        "absolutely",
    }


def _is_explicit_no(text: str) -> bool:
    normalized = re.sub(r"[^a-z ]", " ", text.casefold())
    normalized = " ".join(normalized.split())
    return (
        normalized in {
            "no",
            "no thanks",
            "no thank you",
            "not now",
            "never mind",
            "nevermind",
            "i changed my mind",
            "i have changed my mind",
            "do not book",
            "do not cancel",
        }
        or normalized.startswith("no ")
        or normalized.startswith("i changed my mind ")
        or normalized.startswith("i have changed my mind ")
    )


def _latest_exchange(context: LLMContext) -> tuple[str, str] | None:
    messages = _conversation_messages(context)
    latest_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if messages[index][0] == "user"
        ),
        None,
    )
    if latest_user_index is None:
        return None

    assistant_text = next(
        (
            text
            for role, text in reversed(messages[:latest_user_index])
            if role == "assistant"
        ),
        None,
    )
    if assistant_text is None:
        return None
    return assistant_text, messages[latest_user_index][1]


def _conversation_messages(context: LLMContext) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    for message in context.get_messages():
        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        else:
            role = getattr(message, "role", None)
            content = getattr(message, "content", None)
        if role in {"assistant", "user"}:
            text = _text_content(content)
            if text:
                messages.append((role, text))
    return messages


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""
