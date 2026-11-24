from datetime import date, timedelta

from voice_scenario_support import (
    OTHER_PHONE_NUMBER,
    ToolParams,
    VoiceScenarioCase,
)


class VoiceBookingScenarioTests(VoiceScenarioCase):
    async def test_no_available_slots_are_reported_without_invention(self) -> None:
        params = ToolParams(
            self.context(("user", "Do you have a cardiologist?"))
        )

        await self.tools.check_doctor_availability(
            params,
            speciality="Cardiology",
            appointment_date=(date.today() + timedelta(days=60)).isoformat(),
        )

        result = self.result(params)
        self.assertTrue(result["success"])
        self.assertEqual(result["available_slots"], [])
        self.assertIn("No available slots", result["message"])

    async def test_invalid_doctor_is_reported_for_search_and_booking(self) -> None:
        search = ToolParams(self.context(("user", "Find Dr. Nobody.")))
        await self.tools.check_doctor_availability(
            search,
            doctor_name="Dr. Nobody",
        )
        self.assertFalse(self.result(search)["success"])
        self.assertIn("No doctor matched", self.result(search)["message"])

        arguments = self.booking_arguments(doctor_id=9999)
        result = await self.establish_phone(
            self.tools.book_appointment,
            arguments,
        )

        self.assertIn("not found", result["message"])
        self.assertEqual(self.appointments(), [])

    async def test_already_booked_slot_returns_an_available_alternative(self) -> None:
        self.create_appointment(OTHER_PHONE_NUMBER)
        result = await self.establish_phone(
            self.tools.book_appointment,
            self.booking_arguments(),
        )

        self.assertFalse(result["success"])
        self.assertIn("no longer available", result["message"])
        self.assertEqual(
            result["available_slots"][0]["slot_id"],
            self.alternative_slot_id,
        )
        self.assertEqual(len(self.appointments()), 1)

    async def test_user_change_of_mind_does_not_book(self) -> None:
        result = await self.establish_phone(
            self.tools.book_appointment,
            self.booking_arguments(),
        )
        self.assertEqual(result["confirmation_required"], "booking")

        declined = ToolParams(
            self.booking_confirmation_context(response="No, I changed my mind.")
        )
        await self.tools.book_appointment(
            declined,
            **self.booking_arguments(),
        )

        self.assertIn("not booked", self.result(declined)["message"])
        self.assertEqual(self.appointments(), [])
        self.assertFalse(self.slot_is_booked(self.slot_id))

    async def test_successful_booking_persists_after_both_confirmations(self) -> None:
        result = await self.establish_phone(
            self.tools.book_appointment,
            self.booking_arguments(),
        )
        self.assertEqual(result["confirmation_required"], "booking")

        confirmed = ToolParams(self.booking_confirmation_context())
        await self.tools.book_appointment(
            confirmed,
            **self.booking_arguments(),
        )

        result = self.result(confirmed)
        self.assertTrue(result["success"])
        self.assertEqual(len(self.appointments()), 1)
        self.assertTrue(self.slot_is_booked(self.slot_id))
