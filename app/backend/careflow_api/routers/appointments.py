
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from careflow_api.dependencies import require_role
from careflow_api.storage import appointments, doctors
from careflow_api.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
)


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


# ---------------------------------------------------------
# POST /appointments
# Patient: Request an appointment
# ---------------------------------------------------------

@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    request: AppointmentCreate,
    current_user: Annotated[
        dict,
        Depends(require_role("patient")),
    ],
):
    """Patients can request appointments with available doctors."""

    doctor = doctors.get_by_id(request.doctor_id)

    if doctor is None or not doctor.get("available", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Available doctor not found",
        )

    now = datetime.now(timezone.utc)

    if request.scheduled_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment must be scheduled in the future",
        )

    appointment_id = str(uuid4())

    appointment = {
        "id": appointment_id,
        "patient_email": current_user["email"],
        "doctor_id": request.doctor_id,
        "scheduled_at": request.scheduled_at,
        "reason": request.reason,
        "status": "requested",
        "created_at": now,
    }

    return appointments.create_appointment(appointment)


# ---------------------------------------------------------
# GET /appointments/mine
# Patient: View own appointments
# ---------------------------------------------------------

@router.get(
    "/mine",
    response_model=list[AppointmentResponse],
)
async def list_my_appointments(
    current_user: Annotated[
        dict,
        Depends(require_role("patient")),
    ],
):
    """Patients can view only their own appointments."""

    return appointments.list_for_patient(
        current_user["email"],
    )


# ---------------------------------------------------------
# GET /appointments/doctor
# Doctor: View assigned appointments
# ---------------------------------------------------------

@router.get(
    "/doctor",
    response_model=list[AppointmentResponse],
)
async def list_doctor_appointments(
    current_user: Annotated[
        dict,
        Depends(require_role("doctor")),
    ],
):
    """Doctors can view appointments assigned to their doctor profile."""

    doctor_id = current_user.get("doctor_id")

    if not doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor account is not linked to a doctor profile",
        )

    return appointments.list_for_doctor(doctor_id)


# ---------------------------------------------------------
# GET /appointments/all
# Admin: View all appointments
# ---------------------------------------------------------

@router.get(
    "/all",
    response_model=list[AppointmentResponse],
)
async def list_all_appointments(
    current_user: Annotated[
        dict,
        Depends(require_role("admin")),
    ],
):
    """Admins can view all appointments."""

    return appointments.list_all()


# ---------------------------------------------------------
# PATCH /appointments/{appointment_id}/cancel
# Patient: Cancel own appointment
# ---------------------------------------------------------

@router.patch(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
async def cancel_patient_appointment(
    appointment_id: str,
    current_user: Annotated[
        dict,
        Depends(require_role("patient")),
    ],
):
    """Patients can cancel only their own active appointments."""

    appointment = appointments.get_by_id(appointment_id)

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment["patient_email"] != current_user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot cancel another patient's appointment",
        )

    current_status = appointment["status"]

    if current_status not in ("requested", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This appointment can no longer be cancelled",
        )

    # Only update if the status is still what we originally retrieved.
    updated_appointment = appointments.transition_status(
        appointment_id=appointment_id,
        expected_status=current_status,
        new_status="cancelled",
    )

    if updated_appointment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment status changed. Please refresh and try again.",
        )

    return updated_appointment


# ---------------------------------------------------------
# PATCH /appointments/{appointment_id}/status
# Doctor: Update assigned appointment status
# ---------------------------------------------------------

@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentResponse,
)
async def update_appointment_status(
    appointment_id: str,
    request: AppointmentStatusUpdate,
    current_user: Annotated[
        dict,
        Depends(require_role("doctor")),
    ],
):
    """Doctors can update only appointments assigned to them."""

    appointment = appointments.get_by_id(appointment_id)

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment["doctor_id"] != current_user.get("doctor_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This appointment is not assigned to you",
        )

    current_status = appointment["status"]
    new_status = request.status

    allowed_transitions = {
        "requested": {"confirmed", "cancelled"},
        "confirmed": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot change appointment from "
                f"{current_status} to {new_status}"
            ),
        )

    # Conditional transition prevents overwriting a concurrent update.
    updated_appointment = appointments.transition_status(
        appointment_id=appointment_id,
        expected_status=current_status,
        new_status=new_status,
    )

    if updated_appointment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment status changed. Please refresh and try again.",
        )

    return updated_appointment
