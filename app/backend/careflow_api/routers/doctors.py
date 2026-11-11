
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from careflow_api.dependencies import require_role
from careflow_api.storage import (
    doctor_account_provisioner,
    doctors,
    users,
)
from careflow_api.schemas import (
    DoctorAccountCreate,
    DoctorCreate,
    DoctorResponse,
)
from careflow_api.security import hash_password


router = APIRouter(prefix="/doctors", tags=["Doctors"])


# ---------------------------------------------------------
# GET /doctors
# Public: List available doctors
# ---------------------------------------------------------

@router.get("", response_model=list[DoctorResponse])
async def list_doctors():
    """List available doctors for patients."""

    return doctors.list_available()


# ---------------------------------------------------------
# GET /doctors/{doctor_id}
# Public: Retrieve a doctor profile
# ---------------------------------------------------------

@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(doctor_id: str):
    """Retrieve a doctor profile."""

    doctor = doctors.get_by_id(doctor_id)

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    return doctor


# ---------------------------------------------------------
# POST /doctors
# Admin only: Create a doctor profile
# ---------------------------------------------------------

@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor(
    request: DoctorCreate,
    admin: Annotated[
        dict,
        Depends(require_role("admin")),
    ],
):
    """Create a doctor profile. Admin access required."""

    doctor_id = str(uuid4())

    doctor = {
        "id": doctor_id,
        **request.model_dump(),
    }

    doctors.create_doctor(doctor)

    return doctor


# ---------------------------------------------------------
# POST /doctors/{doctor_id}/account
# Admin only: Provision a doctor login account
# ---------------------------------------------------------

@router.post(
    "/{doctor_id}/account",
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor_account(
    doctor_id: str,
    request: DoctorAccountCreate,
    current_user: Annotated[
        dict,
        Depends(require_role("admin")),
    ],
):
    """Provision a login account for an existing doctor. Admin only."""

    # Verify that the doctor profile exists.
    doctor = doctors.get_by_id(doctor_id)

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    email = request.email

    # Check whether this email is already registered.
    existing_user = users.get_by_email(email)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Check whether this doctor already has a login account.
    if doctor.get("account_email"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This doctor already has a login account",
        )

    # Prepare the doctor login account.
    doctor_user = {
        "full_name": doctor["full_name"],
        "email": email,
        "hashed_password": hash_password(request.password),
        "role": "doctor",
        "doctor_id": doctor_id,
    }

    # Provision the user account and link it to the doctor profile.
    # The repository implementation handles the combined operation.
    try:
        doctor_account_provisioner.provision_doctor_account(
            doctor_id=doctor_id,
            user=doctor_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {
        "message": "Doctor account created successfully",
        "doctor_id": doctor_id,
        "email": email,
        "role": "doctor",
    }
