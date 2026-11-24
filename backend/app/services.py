from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import Appointment, AvailableSlot, Doctor
from app.schemas import BookingRequest, CancelRequest


def list_doctors(db: Session) -> list[Doctor]:
    return list(db.scalars(select(Doctor).order_by(Doctor.name)).all())


def list_availability(
    db: Session,
    doctor_id: int | None,
    appointment_date: date | None,
) -> list[AvailableSlot]:
    active_booking_exists = (
        select(Appointment.id)
        .where(
            Appointment.slot_id == AvailableSlot.id,
            Appointment.status == "booked",
        )
        .exists()
    )
    statement = (
        select(AvailableSlot)
        .options(joinedload(AvailableSlot.doctor))
        .where(
            AvailableSlot.is_booked.is_(False),
            AvailableSlot.appointment_date >= date.today(),
            ~active_booking_exists,
        )
    )
    if doctor_id is not None:
        statement = statement.where(AvailableSlot.doctor_id == doctor_id)
    if appointment_date is not None:
        statement = statement.where(
            AvailableSlot.appointment_date == appointment_date
        )

    return list(
        db.scalars(
            statement.order_by(
                AvailableSlot.appointment_date,
                AvailableSlot.appointment_time,
                AvailableSlot.doctor_id,
            )
        ).all()
    )


def list_appointments(
    db: Session,
    appointment_status: str | None,
    phone_number: str | None = None,
) -> list[Appointment]:
    statement = select(Appointment).options(joinedload(Appointment.doctor))
    if appointment_status is not None:
        statement = statement.where(Appointment.status == appointment_status)
    if phone_number is not None:
        statement = statement.where(Appointment.phone_number == phone_number)
    return list(
        db.scalars(
            statement.order_by(
                Appointment.appointment_date,
                Appointment.appointment_time,
                Appointment.id,
            )
        ).all()
    )


def book_appointment(db: Session, request: BookingRequest) -> Appointment:
    if db.get(Doctor, request.doctor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found.",
        )

    slot = db.get(AvailableSlot, request.slot_id)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment slot not found.",
        )
    if slot.doctor_id != request.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected slot does not belong to this doctor.",
        )
    if slot.appointment_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment slot is in the past.",
        )
    if slot.is_booked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment slot is already booked.",
        )

    claim = db.execute(
        update(AvailableSlot)
        .where(
            AvailableSlot.id == request.slot_id,
            AvailableSlot.doctor_id == request.doctor_id,
            AvailableSlot.is_booked.is_(False),
        )
        .values(is_booked=True)
    )
    if claim.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment slot is no longer available.",
        )

    appointment = Appointment(
        patient_name=request.patient_name,
        phone_number=request.phone_number,
        doctor_id=request.doctor_id,
        slot_id=slot.id,
        appointment_date=slot.appointment_date,
        appointment_time=slot.appointment_time,
        status="booked",
    )
    db.add(appointment)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment slot is no longer available.",
        ) from error

    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, request: CancelRequest) -> Appointment:
    appointment = db.scalar(
        select(Appointment)
        .options(joinedload(Appointment.doctor))
        .where(
            Appointment.id == request.appointment_id,
            Appointment.phone_number == request.phone_number,
        )
    )
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booked appointment not found for this phone number.",
        )
    if appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment is already cancelled.",
        )

    slot = db.get(AvailableSlot, appointment.slot_id)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment slot record is missing.",
        )

    cancellation = db.execute(
        update(Appointment)
        .where(
            Appointment.id == request.appointment_id,
            Appointment.phone_number == request.phone_number,
            Appointment.status == "booked",
        )
        .values(status="cancelled")
    )
    if cancellation.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment is already cancelled or is no longer active.",
        )

    appointment.status = "cancelled"
    slot.is_booked = False
    db.commit()
    db.refresh(appointment)
    return appointment
