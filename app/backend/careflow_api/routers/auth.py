
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from careflow_api.dependencies import (
    get_current_user,
    require_role,
)
from careflow_api.storage import users
from careflow_api.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from careflow_api.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(request: RegisterRequest):

    email = request.email

    # Check whether an account already exists.
    existing_user = users.get_by_email(email)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Public registration can ONLY create patient accounts.
    user = {
        "full_name": request.full_name.strip(),
        "email": email,
        "hashed_password": hash_password(request.password),
        "role": "patient",
    }

    # Save through the domain-specific repository interface.
    users.create_user(user)

    return UserResponse(
        full_name=user["full_name"],
        email=user["email"],
        role=user["role"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):

    email = request.email.strip().lower()

    # Retrieve the account using the repository contract.
    user = users.get_by_email(email)

    if user is None or not verify_password(
        request.password,
        user["hashed_password"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        subject=user["email"],
        role=user["role"],
    )

    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    return UserResponse(
        full_name=current_user["full_name"],
        email=current_user["email"],
        role=current_user["role"],
    )


@router.get("/admin-check")
async def admin_check(
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    return {
        "message": "Admin access granted",
        "user": current_user["email"],
    }


@router.get("/doctor-check")
async def doctor_check(
    current_user: Annotated[dict, Depends(require_role("doctor"))],
):
    return {
        "message": "Doctor access granted",
        "user": current_user["email"],
    }
