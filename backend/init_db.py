from datetime import date, time, timedelta

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import AvailableSlot, Doctor


MOCK_DOCTORS = [
    {
        "name": "Dr. Ananya Rao",
        "speciality": "Cardiology",
        "experience": 12,
        "consultation_fee": 800,
    },
    {
        "name": "Dr. Rohan Mehta",
        "speciality": "Dermatology",
        "experience": 9,
        "consultation_fee": 600,
    },
    {
        "name": "Dr. Priya Nair",
        "speciality": "Pediatrics",
        "experience": 15,
        "consultation_fee": 700,
    },
    {
        "name": "Dr. Kabir Shah",
        "speciality": "General Medicine",
        "experience": 7,
        "consultation_fee": 500,
    },
]

MOCK_TIMES = (time(9, 0), time(11, 0), time(14, 0))


def upcoming_weekdays(start: date, count: int) -> list[date]:
    dates: list[date] = []
    current = start + timedelta(days=1)
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    slot_dates = upcoming_weekdays(date.today(), count=3)

    with SessionLocal() as db:
        for doctor_data in MOCK_DOCTORS:
            doctor = db.scalar(
                select(Doctor).where(Doctor.name == doctor_data["name"])
            )
            if doctor is None:
                doctor = Doctor(**doctor_data)
                db.add(doctor)
                db.flush()

            for slot_date in slot_dates:
                for slot_time in MOCK_TIMES:
                    existing_slot = db.scalar(
                        select(AvailableSlot).where(
                            AvailableSlot.doctor_id == doctor.id,
                            AvailableSlot.appointment_date == slot_date,
                            AvailableSlot.appointment_time == slot_time,
                        )
                    )
                    if existing_slot is None:
                        db.add(
                            AvailableSlot(
                                doctor_id=doctor.id,
                                appointment_date=slot_date,
                                appointment_time=slot_time,
                                is_booked=False,
                            )
                        )

        db.commit()

    print(
        f"Database initialized: {len(MOCK_DOCTORS)} doctors, "
        f"{len(MOCK_DOCTORS) * len(slot_dates) * len(MOCK_TIMES)} mock slots."
    )


if __name__ == "__main__":
    initialize_database()
