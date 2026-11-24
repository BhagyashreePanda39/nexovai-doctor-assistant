from datetime import date, time

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    speciality: Mapped[str] = mapped_column(String(120), nullable=False)
    experience: Mapped[int] = mapped_column(Integer, nullable=False)
    consultation_fee: Mapped[int] = mapped_column(Integer, nullable=False)

    available_slots: Mapped[list["AvailableSlot"]] = relationship(
        back_populates="doctor"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor"
    )


class AvailableSlot(Base):
    __tablename__ = "available_slots"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "appointment_date",
            "appointment_time",
            name="uq_slot_doctor_datetime",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False, index=True
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="available_slots")
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="slot"
    )


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'cancelled')",
            name="ck_appointment_status",
        ),
        Index(
            "uq_appointments_active_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'booked'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False, index=True
    )
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("available_slots.id"), nullable=False, index=True
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="booked"
    )

    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    slot: Mapped["AvailableSlot"] = relationship(back_populates="appointments")
