from voice_scenario_support import (
    PHONE_NUMBER,
    ToolParams,
    VoiceScenarioCase,
)


class VoicePhoneValidationTests(VoiceScenarioCase):
    async def test_invalid_phone_blocks_booking(self) -> None:
        params = ToolParams(
            self.context(("user", "My phone number is 12345."))
        )

        await self.tools.book_appointment(
            params,
            phone_number="12345",
            doctor_id=self.doctor_id,
            slot_id=self.slot_id,
        )

        result = self.result(params)
        self.assertFalse(result["success"])
        self.assertIn("7 to 15 digits", result["message"])
        self.assertEqual(self.appointments(), [])

    async def test_invalid_phone_blocks_cancellation(self) -> None:
        params = ToolParams(
            self.context(("user", "Please cancel my appointment."))
        )

        await self.tools.cancel_appointment(
            params,
            phone_number="12345",
        )

        result = self.result(params)
        self.assertFalse(result["success"])
        self.assertIn("7 to 15 digits", result["message"])
        self.assertEqual(self.appointments(), [])

    async def test_spoken_digit_words_match_the_transcribed_phone(self) -> None:
        params = ToolParams(
            self.context(
                (
                    "user",
                    "My phone number is nine eight seven six five four three "
                    "two one zero.",
                )
            )
        )

        await self.tools.book_appointment(
            params,
            phone_number=PHONE_NUMBER,
            doctor_id=self.doctor_id,
            slot_id=self.slot_id,
        )

        result = self.result(params)
        self.assertEqual(result["confirmation_required"], "phone_number")
        self.assertEqual(self.appointments(), [])

    async def test_declining_phone_readback_prevents_booking(self) -> None:
        initial = ToolParams(
            self.context(("user", f"My phone number is {PHONE_NUMBER}."))
        )
        await self.tools.book_appointment(
            initial,
            phone_number=PHONE_NUMBER,
            doctor_id=self.doctor_id,
            slot_id=self.slot_id,
        )
        self.assertEqual(
            self.result(initial)["confirmation_required"],
            "phone_number",
        )

        declined = ToolParams(
            self.context(
                ("user", f"My phone number is {PHONE_NUMBER}."),
                (
                    "assistant",
                    f"I heard {PHONE_NUMBER}. Is that phone number correct?",
                ),
                ("user", "No, I changed my mind."),
            )
        )
        await self.tools.book_appointment(
            declined,
            phone_number=PHONE_NUMBER,
            doctor_id=self.doctor_id,
            slot_id=self.slot_id,
        )

        self.assertIn("not confirmed", self.result(declined)["message"])
        self.assertEqual(self.appointments(), [])
