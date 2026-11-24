import unittest
from collections.abc import Awaitable, Callable
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Appointment, AvailableSlot, Doctor
from app.schemas import BookingRequest
from app.services import book_appointment
from app.voice.tools import AppointmentTools
from pipecat.processors.aggregators.llm_context import LLMContext


PHONE_NUMBER = "9876543210"
OTHER_PHONE_NUMBER = "9999999999"


class ToolParams:
    def __init__(self, context: LLMContext) -> None:
        self.context = context
        self.result: dict[str, Any] | None = None

    async def result_callback(self, result: dict[str, Any]) -> None:
        self.result = result


class VoiceScenarioCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.tools = AppointmentTools(self.session_factory)
        self.appointment_date = date.today() + timedelta(days=14)

        with self.session_factory() as db:
            cardiologist = Doctor(
                name="Dr. Ananya Rao",
                speciality="Cardiology",
                experience=12,
                consultation_fee=800,
            )
            dermatologist = Doctor(
                name="Dr. Rohan Mehta",
                speciality="Dermatology",
                experience=9,
                consultation_fee=600,
            )
            db.add_all([cardiologist, dermatologist])
            db.flush()
            self.doctor_id = cardiologist.id
            self.other_doctor_id = dermatologist.id

            slots = [
                AvailableSlot(
                    doctor_id=cardiologist.id,
                    appointment_date=self.appointment_date,
                    appointment_time=time(9, 0),
                    is_booked=False,
                ),
                AvailableSlot(
                    doctor_id=cardiologist.id,
                    appointment_date=self.appointment_date,
                    appointment_time=time(11, 0),
                    is_booked=False,
                ),
                AvailableSlot(
                    doctor_id=dermatologist.id,
                    appointment_date=self.appointment_date,
                    appointment_time=time(10, 0),
                    is_booked=False,
                ),
            ]
            db.add_all(slots)
            db.flush()
            self.slot_id = slots[0].id
            self.alternative_slot_id = slots[1].id
            self.other_doctor_slot_id = slots[2].id
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def context(self, *messages: tuple[str, str]) -> LLMContext:
        return LLMContext(
            messages=[
                {"role": role, "content": content}
                for role, content in messages
            ]
        )

    def result(self, params: ToolParams) -> dict[str, Any]:
        if params.result is None:
            self.fail("The tool did not return a result.")
        return params.result

    def phone_confirmed_context(
        self,
        phone_number: str = PHONE_NUMBER,
    ) -> LLMContext:
        return self.context(
            ("user", f"My phone number is {phone_number}."),
            (
                "assistant",
                f"I heard {phone_number}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
        )

    async def establish_phone(
        self,
        handler: Callable[..., Awaitable[None]],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        phone_number = arguments.get("phone_number", PHONE_NUMBER)
        initial = ToolParams(
            self.context(("user", f"My phone number is {phone_number}."))
        )
        await handler(initial, **arguments)
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )

        verified = ToolParams(self.phone_confirmed_context(phone_number))
        await handler(verified, **arguments)
        return self.result(verified)

    def booking_arguments(
        self,
        phone_number: str = PHONE_NUMBER,
        doctor_id: int | None = None,
        slot_id: int | None = None,
    ) -> dict[str, Any]:
        return {
            "phone_number": phone_number,
            "doctor_id": doctor_id or self.doctor_id,
            "slot_id": slot_id or self.slot_id,
        }

    def booking_confirmation_context(
        self,
        doctor_name: str = "Dr. Ananya Rao",
        appointment_date: date | None = None,
        appointment_time: str = "09:00",
        response: str = "Yes.",
    ) -> LLMContext:
        selected_date = appointment_date or self.appointment_date
        return self.context(
            ("user", f"My phone number is {PHONE_NUMBER}."),
            (
                "assistant",
                f"I heard {PHONE_NUMBER}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
            (
                "assistant",
                f"Please confirm booking {doctor_name} on "
                f"{selected_date.isoformat()} at {appointment_time}. "
                "Should I book this appointment?",
            ),
            ("user", response),
        )

    def create_appointment(
        self,
        phone_number: str = PHONE_NUMBER,
        slot_id: int | None = None,
    ) -> int:
        with self.session_factory() as db:
            appointment = book_appointment(
                db,
                BookingRequest(
                    phone_number=phone_number,
                    doctor_id=self.doctor_id,
                    slot_id=slot_id or self.slot_id,
                ),
            )
            return appointment.id

    def appointments(self) -> list[Appointment]:
        with self.session_factory() as db:
            return list(db.scalars(select(Appointment)).all())

    def appointment_status(self, appointment_id: int) -> str:
        with self.session_factory() as db:
            appointment = db.get(Appointment, appointment_id)
            if appointment is None:
                self.fail(f"Appointment {appointment_id} was not found.")
            return appointment.status

    def slot_is_booked(self, slot_id: int) -> bool:
        with self.session_factory() as db:
            slot = db.get(AvailableSlot, slot_id)
            if slot is None:
                self.fail(f"Slot {slot_id} was not found.")
            return slot.is_booked
