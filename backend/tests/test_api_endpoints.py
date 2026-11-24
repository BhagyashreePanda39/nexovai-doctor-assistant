import unittest
from datetime import date, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AvailableSlot, Doctor


class AppointmentApiTests(unittest.TestCase):
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
        with self.session_factory() as db:
            doctor = Doctor(
                name="Dr. Test Rao",
                speciality="Cardiology",
                experience=10,
                consultation_fee=500,
            )
            db.add(doctor)
            db.flush()
            slot = AvailableSlot(
                doctor_id=doctor.id,
                appointment_date=date.today() + timedelta(days=10),
                appointment_time=time(10, 30),
                is_booked=False,
            )
            db.add(slot)
            db.commit()
            self.doctor_id = doctor.id
            self.slot_id = slot.id
            self.appointment_date = slot.appointment_date.isoformat()

        self.previous_override = app.dependency_overrides.get(get_db)

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        if self.previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = self.previous_override
        self.engine.dispose()

    def booking_request(self) -> dict[str, object]:
        return {
            "phone_number": "+1 (555) 123-4567",
            "doctor_id": self.doctor_id,
            "slot_id": self.slot_id,
            "patient_name": "Asha",
        }

    def test_doctors_and_open_availability_are_served_from_sqlite(self) -> None:
        doctors = self.client.get("/api/doctors")
        availability = self.client.get(
            "/api/availability",
            params={
                "doctor_id": self.doctor_id,
                "appointment_date": self.appointment_date,
            },
        )

        self.assertEqual(doctors.status_code, 200)
        self.assertEqual(doctors.json()[0]["name"], "Dr. Test Rao")
        self.assertEqual(availability.status_code, 200)
        self.assertEqual(availability.json()[0]["id"], self.slot_id)
        self.assertFalse(availability.json()[0]["is_booked"])

    def test_booking_persists_and_rejects_a_second_booking_for_the_slot(self) -> None:
        first_booking = self.client.post(
            "/api/appointments",
            json=self.booking_request(),
        )
        second_booking = self.client.post(
            "/api/appointments",
            json=self.booking_request(),
        )
        appointments = self.client.get(
            "/api/appointments",
            params={"status": "booked"},
        )
        availability = self.client.get(
            "/api/availability",
            params={"doctor_id": self.doctor_id},
        )

        self.assertEqual(first_booking.status_code, 201)
        self.assertEqual(first_booking.json()["appointment"]["phone_number"], "+15551234567")
        self.assertEqual(second_booking.status_code, 409)
        self.assertEqual(len(appointments.json()), 1)
        self.assertFalse(any(slot["id"] == self.slot_id for slot in availability.json()))

    def test_cancellation_checks_ownership_and_reopens_the_slot(self) -> None:
        booking = self.client.post(
            "/api/appointments",
            json=self.booking_request(),
        )
        appointment_id = booking.json()["appointment"]["id"]
        wrong_owner = self.client.post(
            "/api/appointments/cancel",
            json={
                "phone_number": "9999999999",
                "appointment_id": appointment_id,
            },
        )
        cancellation = self.client.post(
            "/api/appointments/cancel",
            json={
                "phone_number": "+15551234567",
                "appointment_id": appointment_id,
            },
        )
        booked = self.client.get(
            "/api/appointments",
            params={"status": "booked"},
        )
        cancelled = self.client.get(
            "/api/appointments",
            params={"status": "cancelled"},
        )
        availability = self.client.get(
            "/api/availability",
            params={"doctor_id": self.doctor_id},
        )

        self.assertEqual(wrong_owner.status_code, 404)
        self.assertEqual(cancellation.status_code, 200)
        self.assertEqual(cancellation.json()["appointment"]["status"], "cancelled")
        self.assertEqual(booked.json(), [])
        self.assertEqual(len(cancelled.json()), 1)
        self.assertTrue(any(slot["id"] == self.slot_id for slot in availability.json()))


if __name__ == "__main__":
    unittest.main()
