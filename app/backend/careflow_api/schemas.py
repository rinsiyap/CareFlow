from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()

        if value.count("@") != 1:
            raise ValueError("Enter a valid email address")

        local, domain = value.split("@")

        if not local or "." not in domain or domain.startswith("."):
            raise ValueError("Enter a valid email address")

        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    full_name: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DoctorCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    specialization: str = Field(min_length=2, max_length=100)
    qualifications: str = Field(min_length=2, max_length=200)
    experience_years: int = Field(ge=0, le=60)
    consultation_fee: float = Field(gt=0, le=100000)
    available: bool = True


class DoctorResponse(BaseModel):
    id: str
    full_name: str
    specialization: str
    qualifications: str
    experience_years: int
    consultation_fee: float
    available: bool


class AppointmentCreate(BaseModel):
    doctor_id: str = Field(min_length=1, max_length=100)
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=500)


    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Appointment time must include a timezone")

        return value


class AppointmentStatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "cancelled"]


class AppointmentResponse(BaseModel):
    id: str
    patient_email: str
    doctor_id: str
    scheduled_at: datetime
    reason: str
    status: str
    created_at: datetime



class DoctorAccountCreate(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()

        if (
            "@" not in value
            or value.startswith("@")
            or value.endswith("@")
            or "." not in value.split("@")[-1]
        ):
            raise ValueError("A valid email address is required")

        return value
