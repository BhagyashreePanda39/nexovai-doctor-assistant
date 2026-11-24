from voice_scenario_support import (
    PHONE_NUMBER,
    OTHER_PHONE_NUMBER,
    ToolParams,
    VoiceScenarioCase,
)


class VoiceCancellationScenarioTests(VoiceScenarioCase):
    async def test_successful_cancellation_finds_and_releases_owned_booking(self) -> None:
        appointment_id = self.create_appointment()
        other_appointment_id = self.create_appointment(
            slot_id=self.alternative_slot_id,
        )
        result = await self.establish_phone(
            self.tools.cancel_appointment,
            {"phone_number": PHONE_NUMBER},
        )
        self.assertEqual(len(result["appointments"]), 2)

        selection = ToolParams(
            self.context(
                ("user", f"My phone number is {PHONE_NUMBER}."),
                (
                    "assistant",
                    f"I heard {PHONE_NUMBER}. Is that phone number correct?",
                ),
                ("user", "Yes, that is correct."),
                (
                    "assistant",
                    f"I found appointments {appointment_id} and "
                    f"{other_appointment_id}. Which one should I cancel?",
                ),
                ("user", f"Please cancel appointment {appointment_id}."),
            )
        )
        await self.tools.cancel_appointment(
            selection,
            phone_number=PHONE_NUMBER,
            appointment_id=appointment_id,
        )
        self.assertEqual(
            self.result(selection)["confirmation_required"],
            "cancellation",
        )

        confirmed = ToolParams(
            self.context(
                ("user", f"My phone number is {PHONE_NUMBER}."),
                (
                    "assistant",
                    f"I heard {PHONE_NUMBER}. Is that phone number correct?",
                ),
                ("user", "Yes, that is correct."),
                (
                    "assistant",
                    f"Cancel appointment {appointment_id} with Dr. Ananya Rao on "
                    f"{self.appointment_date.isoformat()} at 09:00? "
                    "Should I cancel it?",
                ),
                ("user", "Yes."),
            )
        )
        await self.tools.cancel_appointment(
            confirmed,
            phone_number=PHONE_NUMBER,
            appointment_id=appointment_id,
        )

        self.assertTrue(self.result(confirmed)["success"])
        self.assertEqual(self.appointment_status(appointment_id), "cancelled")
        self.assertEqual(self.appointment_status(other_appointment_id), "booked")
        self.assertFalse(self.slot_is_booked(self.slot_id))
        self.assertTrue(self.slot_is_booked(self.alternative_slot_id))

    async def test_missing_appointment_is_reported_after_phone_confirmation(self) -> None:
        result = await self.establish_phone(
            self.tools.cancel_appointment,
            {"phone_number": PHONE_NUMBER},
        )

        self.assertFalse(result["success"])
        self.assertIn("No active appointment", result["message"])
        self.assertEqual(self.appointments(), [])

    async def test_cannot_cancel_appointment_owned_by_another_phone(self) -> None:
        appointment_id = self.create_appointment(PHONE_NUMBER)
        result = await self.establish_phone(
            self.tools.cancel_appointment,
            {"phone_number": OTHER_PHONE_NUMBER},
        )

        self.assertFalse(result["success"])
        self.assertIn("No active appointment", result["message"])
        self.assertEqual(self.appointment_status(appointment_id), "booked")

    async def test_declining_cancellation_preserves_booking(self) -> None:
        appointment_id = self.create_appointment()
        result = await self.establish_phone(
            self.tools.cancel_appointment,
            {"phone_number": PHONE_NUMBER},
        )
        self.assertEqual(result["confirmation_required"], "cancellation")

        declined = ToolParams(
            self.context(
                ("user", f"My phone number is {PHONE_NUMBER}."),
                (
                    "assistant",
                    f"I heard {PHONE_NUMBER}. Is that phone number correct?",
                ),
                ("user", "Yes, that is correct."),
                (
                    "assistant",
                    f"Cancel appointment {appointment_id} with Dr. Ananya Rao on "
                    f"{self.appointment_date.isoformat()} at 09:00? "
                    "Should I cancel it?",
                ),
                ("user", "No, I changed my mind."),
            )
        )
        await self.tools.cancel_appointment(
            declined,
            phone_number=PHONE_NUMBER,
            appointment_id=appointment_id,
        )

        self.assertIn("not cancelled", self.result(declined)["message"])
        self.assertEqual(self.appointment_status(appointment_id), "booked")
        self.assertTrue(self.slot_is_booked(self.slot_id))
