import unittest
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


class AppointmentToolsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.engine = engine
        Base.metadata.create_all(bind=engine)
        self.session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.tools = AppointmentTools(self.session_factory)
        self.appointment_date = date.today() + timedelta(days=14)
        with self.session_factory() as db:
            doctor = Doctor(
                name="Dr. Test Rao",
                speciality="Cardiology",
                experience=10,
                consultation_fee=500,
            )
            db.add(doctor)
            db.flush()
            self.doctor_id = doctor.id
            slots = [
                AvailableSlot(
                    doctor_id=doctor.id,
                    appointment_date=self.appointment_date,
                    appointment_time=time(9, 0),
                    is_booked=False,
                ),
                AvailableSlot(
                    doctor_id=doctor.id,
                    appointment_date=self.appointment_date,
                    appointment_time=time(11, 0),
                    is_booked=False,
                ),
            ]
            db.add_all(slots)
            db.flush()
            self.slot_id = slots[0].id
            self.alternative_slot_id = slots[1].id
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

    def booking_arguments(self) -> dict[str, Any]:
        return {
            "phone_number": PHONE_NUMBER,
            "doctor_id": self.doctor_id,
            "slot_id": self.slot_id,
        }

    def result(self, params: ToolParams) -> dict[str, Any]:
        if params.result is None:
            self.fail("The tool did not return a result.")
        return params.result

    def phone_confirmed_context(self) -> LLMContext:
        return self.context(
            ("user", f"My phone number is {PHONE_NUMBER}."),
            (
                "assistant",
                f"I heard {PHONE_NUMBER}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
        )

    def booking_confirmed_context(self) -> LLMContext:
        return self.context(
            ("user", f"My phone number is {PHONE_NUMBER}."),
            (
                "assistant",
                f"I heard {PHONE_NUMBER}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
            (
                "assistant",
                f"Please confirm booking Dr. Test Rao on "
                f"{self.appointment_date.isoformat()} at 09:00. "
                "Should I book this appointment?",
            ),
            ("user", "Yes."),
        )

    async def test_availability_returns_matching_database_slots(self) -> None:
        params = ToolParams(self.context(("user", "Find cardiology.")))

        await self.tools.check_doctor_availability(
            params,
            speciality="cardiology",
            appointment_date=self.appointment_date.isoformat(),
        )

        result = self.result(params)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["available_slots"]), 2)
        self.assertEqual(
            result["available_slots"][0]["doctor_name"],
            "Dr. Test Rao",
        )
        self.assertEqual(result["available_slots"][0]["slot_id"], self.slot_id)

    async def test_booking_requires_two_confirmations_and_updates_sqlite(self) -> None:
        initial = ToolParams(
            self.context(
                ("user", f"Book Dr. Test Rao. My phone number is {PHONE_NUMBER}.")
            )
        )
        await self.tools.book_appointment(initial, **self.booking_arguments())
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )
        self.assertEqual(self.count_appointments(), 0)

        phone_confirmed = ToolParams(self.phone_confirmed_context())
        await self.tools.book_appointment(
            phone_confirmed,
            **self.booking_arguments(),
        )
        self.assertEqual(
            self.result(phone_confirmed)["confirmation_required"],
            "booking",
        )
        self.assertEqual(self.count_appointments(), 0)

        unrelated_yes = ToolParams(
            self.context(
                ("user", f"My phone number is {PHONE_NUMBER}."),
                (
                    "assistant",
                    f"I heard {PHONE_NUMBER}. Is that phone number correct?",
                ),
                ("user", "Yes, that is correct."),
                ("assistant", "Would you like any other help?"),
                ("user", "Yes."),
            )
        )
        await self.tools.book_appointment(
            unrelated_yes,
            **self.booking_arguments(),
        )
        self.assertEqual(
            self.result(unrelated_yes)["confirmation_required"],
            "booking",
        )
        self.assertEqual(self.count_appointments(), 0)

        booking_confirmed = ToolParams(self.booking_confirmed_context())
        await self.tools.book_appointment(
            booking_confirmed,
            **self.booking_arguments(),
        )
        self.assertTrue(self.result(booking_confirmed)["success"])
        self.assertEqual(self.count_appointments(), 1)
        self.assertTrue(self.slot_is_booked(self.slot_id))

    async def test_booking_rejects_number_not_spoken_by_the_user(self) -> None:
        params = ToolParams(
            self.context(
                ("assistant", f"Use the phone number {PHONE_NUMBER}."),
                ("user", "Please book the appointment."),
            )
        )

        await self.tools.book_appointment(params, **self.booking_arguments())

        result = self.result(params)
        self.assertFalse(result["success"])
        self.assertIn("spoken words", result["message"])
        self.assertEqual(self.count_appointments(), 0)

    async def test_slot_that_becomes_unavailable_returns_real_alternatives(self) -> None:
        initial = ToolParams(
            self.context(
                ("user", f"Book Dr. Test Rao. My phone number is {PHONE_NUMBER}.")
            )
        )
        await self.tools.book_appointment(initial, **self.booking_arguments())
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )

        phone_confirmed = ToolParams(self.phone_confirmed_context())
        await self.tools.book_appointment(
            phone_confirmed,
            **self.booking_arguments(),
        )
        self.assertEqual(
            self.result(phone_confirmed)["confirmation_required"],
            "booking",
        )

        with self.session_factory() as db:
            book_appointment(
                db,
                BookingRequest(
                    phone_number=OTHER_PHONE_NUMBER,
                    doctor_id=self.doctor_id,
                    slot_id=self.slot_id,
                ),
            )

        params = ToolParams(self.booking_confirmed_context())
        await self.tools.book_appointment(params, **self.booking_arguments())

        result = self.result(params)
        self.assertFalse(result["success"])
        self.assertEqual(
            result["available_slots"][0]["slot_id"],
            self.alternative_slot_id,
        )
        self.assertEqual(self.count_appointments(), 1)

    async def test_cancellation_requires_phone_and_action_confirmation(self) -> None:
        appointment_id = self.create_appointment(PHONE_NUMBER)
        initial = ToolParams(
            self.context(("user", f"Cancel it. My phone number is {PHONE_NUMBER}."))
        )
        await self.tools.cancel_appointment(initial, phone_number=PHONE_NUMBER)
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )
        self.assertEqual(self.appointment_status(appointment_id), "booked")

        confirmed_phone = ToolParams(self.phone_confirmed_context())
        await self.tools.cancel_appointment(
            confirmed_phone,
            phone_number=PHONE_NUMBER,
        )
        self.assertEqual(
            self.result(confirmed_phone)["confirmation_required"],
            "cancellation",
        )
        self.assertEqual(self.appointment_status(appointment_id), "booked")

        cancellation_context = self.context(
            ("user", f"My phone number is {PHONE_NUMBER}."),
            (
                "assistant",
                f"I heard {PHONE_NUMBER}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
            (
                "assistant",
                f"Cancel appointment {appointment_id} with Dr. Test Rao on "
                f"{self.appointment_date.isoformat()} at 09:00? Should I cancel it?",
            ),
            ("user", "No."),
        )
        refused = ToolParams(cancellation_context)
        await self.tools.cancel_appointment(
            refused,
            phone_number=PHONE_NUMBER,
            appointment_id=appointment_id,
        )
        self.assertIn("not cancelled", self.result(refused)["message"])
        self.assertEqual(self.appointment_status(appointment_id), "booked")

    async def test_cancellation_does_not_expose_another_phone_appointments(self) -> None:
        self.create_appointment(PHONE_NUMBER)
        other_tools = AppointmentTools(self.session_factory)
        initial = ToolParams(
            self.context(("user", f"My phone number is {OTHER_PHONE_NUMBER}."))
        )
        await other_tools.cancel_appointment(
            initial,
            phone_number=OTHER_PHONE_NUMBER,
        )
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )

        context = self.context(
            ("user", f"My phone number is {OTHER_PHONE_NUMBER}."),
            (
                "assistant",
                f"I heard {OTHER_PHONE_NUMBER}. Is that phone number correct?",
            ),
            ("user", "Yes, that is correct."),
        )
        params = ToolParams(context)

        await other_tools.cancel_appointment(
            params,
            phone_number=OTHER_PHONE_NUMBER,
        )

        result = self.result(params)
        self.assertFalse(result["success"])
        self.assertIn("No active appointment", result["message"])
        self.assertEqual(self.count_appointments(), 1)

    def create_appointment(self, phone_number: str) -> int:
        with self.session_factory() as db:
            appointment = book_appointment(
                db,
                BookingRequest(
                    phone_number=phone_number,
                    doctor_id=self.doctor_id,
                    slot_id=self.slot_id,
                ),
            )
            return appointment.id

    def count_appointments(self) -> int:
        with self.session_factory() as db:
            return len(db.scalars(select(Appointment)).all())

    def appointment_status(self, appointment_id: int) -> str:
        with self.session_factory() as db:
            appointment = db.get(Appointment, appointment_id)
            assert appointment is not None
            return appointment.status

    def slot_is_booked(self, slot_id: int) -> bool:
        with self.session_factory() as db:
            slot = db.get(AvailableSlot, slot_id)
            assert slot is not None
            return slot.is_booked


if __name__ == "__main__":
    unittest.main()
