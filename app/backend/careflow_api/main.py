
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load the project-root .env before importing storage.
# main.py is located in app/backend/careflow_api/.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=False)

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from careflow_api.storage import storage, users
from careflow_api.routers import auth, doctors, appointments
from careflow_api.security import hash_password


def bootstrap_admin() -> None:
    """Create the local development admin from environment variables."""

    email = os.getenv(
        "CARE_FLOW_BOOTSTRAP_ADMIN_EMAIL", ""
    ).strip().lower()

    password = os.getenv(
        "CARE_FLOW_BOOTSTRAP_ADMIN_PASSWORD", ""
    )

    full_name = os.getenv(
        "CARE_FLOW_BOOTSTRAP_ADMIN_NAME", ""
    ).strip()

    # Bootstrap is optional.
    if not email and not password and not full_name:
        print("Admin bootstrap skipped: credentials not configured.")
        return

    # Reject incomplete configuration.
    if not email or not password or not full_name:
        raise RuntimeError(
            "Admin bootstrap requires CARE_FLOW_BOOTSTRAP_ADMIN_EMAIL, "
            "CARE_FLOW_BOOTSTRAP_ADMIN_PASSWORD, and "
            "CARE_FLOW_BOOTSTRAP_ADMIN_NAME."
        )

    if len(password) < 12:
        raise RuntimeError(
            "The bootstrap admin password must contain at least 12 characters."
        )

    # Check whether the admin already exists.
    existing_user = users.get_by_email(email)

    if existing_user:
        if existing_user.get("role") != "admin":
            raise RuntimeError(
                "The configured bootstrap admin email already belongs "
                "to a non-admin account."
            )

        print(f"Admin account already exists: {email}")
        return

    # Create the admin account.
    admin_user = {
        "full_name": full_name,
        "email": email,
        "hashed_password": hash_password(password),
        "role": "admin",
    }

    users.create_user(admin_user)

    print(f"Local development admin bootstrapped: {email}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run application startup initialization."""

    bootstrap_admin()
    yield


app = FastAPI(
    title="CareFlow API",
    description=(
        "A containerized clinic appointment demonstration platform. "
        "Uses synthetic demonstration data only."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)

app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(appointments.router)


@app.get("/", tags=["General"])
async def root():
    return {
        "application": "CareFlow",
        "version": "1.0.0",
        "message": "CareFlow API is running",
        "documentation": "/docs",
    }


@app.get("/health/live", tags=["Health"])
async def liveness():
    return {
        "status": "alive",
        "application": "careflow-api",
    }


@app.get("/health/ready", tags=["Health"])
async def readiness():
    """Check whether the application and storage are ready."""

    try:
        database_health = storage.health_check()

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "application": "careflow-api",
                "database": "unavailable",
                "storage_backend": storage.backend,
                "environment": "local",
            },
        )

    return {
        "status": "ready",
        "application": "careflow-api",
        "database": database_health["status"],
        "storage_backend": database_health["backend"],
        "environment": "local",
    }
