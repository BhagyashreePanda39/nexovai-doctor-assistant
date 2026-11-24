from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, AvailableSlot, Doctor
from app.schemas import (
    AppointmentActionResponse,
    AppointmentResponse,
    AvailabilityResponse,
    BookingRequest,
    CancelRequest,
    DoctorResponse,
)
from app.services import (
    book_appointment,
    cancel_appointment,
    list_appointments,
    list_availability,
    list_doctors,
)


router = APIRouter(prefix="/api")
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/doctors", response_model=list[DoctorResponse], tags=["doctors"])
def get_doctors(db: DatabaseSession) -> list[Doctor]:
    """Return all doctors and their consultation details."""
    return list_doctors(db)


@router.get(
    "/availability",
    response_model=list[AvailabilityResponse],
    tags=["availability"],
)
def get_availability(
    db: DatabaseSession,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
    appointment_date: date | None = None,
) -> list[AvailableSlot]:
    """Return future slots that are not booked, with optional filters."""
    return list_availability(db, doctor_id, appointment_date)


@router.post(
    "/appointments",
    response_model=AppointmentActionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["appointments"],
)
def create_appointment(
    request: BookingRequest,
    db: DatabaseSession,
) -> AppointmentActionResponse:
    appointment = book_appointment(db, request)
    return AppointmentActionResponse(
        message="Appointment booked successfully.",
        appointment=appointment,
    )


@router.get(
    "/appointments",
    response_model=list[AppointmentResponse],
    tags=["appointments"],
)
def get_appointments(
    db: DatabaseSession,
    appointment_status: Annotated[
        Literal["booked", "cancelled"] | None,
        Query(alias="status"),
    ] = None,
) -> list[Appointment]:
    """Return appointments, optionally filtered by booked/cancelled status."""
    return list_appointments(db, appointment_status)


@router.post(
    "/appointments/cancel",
    response_model=AppointmentActionResponse,
    tags=["appointments"],
)
def cancel_existing_appointment(
    request: CancelRequest,
    db: DatabaseSession,
) -> AppointmentActionResponse:
    appointment = cancel_appointment(db, request)
    return AppointmentActionResponse(
        message="Appointment cancelled successfully.",
        appointment=appointment,
    )
