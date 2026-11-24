import unittest
from datetime import date, time
from types import SimpleNamespace

from app.schemas import AppointmentResponse


class DashboardAppointmentResponseTests(unittest.TestCase):
    def test_response_includes_phone_number_and_doctor_details(self) -> None:
        appointment = SimpleNamespace(
            id=7,
            patient_name="Asha",
            phone_number="+919876543210",
            doctor_id=2,
            slot_id=14,
            appointment_date=date(2026, 11, 25),
            appointment_time=time(10, 30),
            status="booked",
            doctor=SimpleNamespace(
                id=2,
                name="Dr. Rao",
                speciality="Cardiology",
            ),
        )

        response = AppointmentResponse.model_validate(appointment)

        self.assertEqual(response.phone_number, "+919876543210")
        self.assertEqual(response.doctor.name, "Dr. Rao")


if __name__ == "__main__":
    unittest.main()
