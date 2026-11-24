import re
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_phone_number(value: str) -> str:
    normalized = re.sub(r"[\s().-]", "", value)
    if not re.fullmatch(r"\+?[0-9]{7,15}", normalized):
        raise ValueError(
            "Enter a phone number with 7 to 15 digits and an optional leading +."
        )
    return normalized


class DoctorResponse(BaseModel):
    id: int
    name: str
    speciality: str
    experience: int
    consultation_fee: int

    model_config = ConfigDict(from_attributes=True)


class DoctorSummary(BaseModel):
    id: int
    name: str
    speciality: str

    model_config = ConfigDict(from_attributes=True)


class AvailabilityResponse(BaseModel):
    id: int
    doctor_id: int
    appointment_date: date
    appointment_time: time
    is_booked: bool
    doctor: DoctorSummary

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: int
    patient_name: str | None
    phone_number: str
    doctor_id: int
    slot_id: int
    appointment_date: date
    appointment_time: time
    status: Literal["booked", "cancelled"]
    doctor: DoctorSummary

    model_config = ConfigDict(from_attributes=True)


class BookingRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=32)
    doctor_id: int = Field(gt=0)
    slot_id: int = Field(gt=0)
    patient_name: str | None = Field(default=None, max_length=120)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return normalize_phone_number(value)

    @field_validator("patient_name")
    @classmethod
    def clean_patient_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CancelRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=32)
    appointment_id: int = Field(gt=0)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return normalize_phone_number(value)


class AppointmentActionResponse(BaseModel):
    message: str
    appointment: AppointmentResponse
