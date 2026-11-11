
import pytest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from careflow_api.dependencies import appointments, doctors, users
from careflow_api.main import app
from careflow_api.security import hash_password

client = TestClient(app)


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def reset_test_data():
    """Reset temporary in-memory repositories before and after each test."""
    users.clear()
    doctors.clear()
    appointments.clear()

    yield

    users.clear()
    doctors.clear()
    appointments.clear()


# ============================================================
# TEST HELPER FUNCTIONS
# ============================================================

def register_patient():
    """Register a standard demo patient."""
    return client.post(
        "/auth/register",
        json={
            "full_name": "Demo Patient",
            "email": "patient@example.com",
            "password": "CareFlowTest!2026",
        },
    )


def login_patient():
    """Register and log in a demo patient, returning the JWT."""
    register_patient()

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "CareFlowTest!2026",
        },
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def create_test_admin():
    """Create a test-only admin account and return its JWT."""
    users["admin@example.com"] = {
        "full_name": "Demo Admin",
        "email": "admin@example.com",
        "hashed_password": hash_password("AdminTest!2026Secure"),
        "role": "admin",
    }

    response = client.post(
        "/auth/login",
        json={
            "email": "admin@example.com",
            "password": "AdminTest!2026Secure",
        },
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def sample_doctor(doctor_id="doctor-1", available=True):
    """Return synthetic doctor data for testing."""
    return {
        "id": doctor_id,
        "full_name": "Dr. Demo",
        "specialization": "Cardiology",
        "qualifications": "MD",
        "experience_years": 10,
        "consultation_fee": 500.0,
        "available": available,
    }


def create_test_doctor(doctor_id="doctor-1"):
    """Create a doctor profile and corresponding test doctor account."""
    doctors[doctor_id] = sample_doctor(doctor_id=doctor_id)

    email = f"{doctor_id}@example.com"

    users[email] = {
        "full_name": "Dr. Demo",
        "email": email,
        "hashed_password": hash_password("DoctorTest!2026Secure"),
        "role": "doctor",
        "doctor_id": doctor_id,
    }

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "DoctorTest!2026Secure",
        },
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def create_test_appointment(patient_token, doctor_id="doctor-1"):
    """Create an appointment using a patient JWT."""
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(days=2)
    ).isoformat()

    return client.post(
        "/appointments",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "doctor_id": doctor_id,
            "scheduled_at": scheduled_at,
            "reason": "Routine consultation",
        },
    )


# ============================================================
# HEALTH CHECK TESTS
# ============================================================

def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["application"] == "CareFlow"


def test_liveness_endpoint():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_endpoint():
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


# ============================================================
# AUTHENTICATION TESTS
# ============================================================

def test_patient_registration():
    response = register_patient()

    assert response.status_code == 201
    assert response.json()["role"] == "patient"
    assert response.json()["email"] == "patient@example.com"


def test_registration_cannot_choose_admin_role():
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Demo Admin",
            "email": "admin@example.com",
            "password": "CareFlowTest!2026",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "patient"


def test_duplicate_registration_is_rejected():
    register_patient()

    response = register_patient()

    assert response.status_code == 409


def test_login_returns_access_token():
    register_patient()

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "CareFlowTest!2026",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["expires_in"] == 1800


def test_invalid_password_is_rejected():
    register_patient()

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "WrongPassword!2026",
        },
    )

    assert response.status_code == 401


def test_profile_requires_authentication():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_authenticated_patient_can_view_profile():
    token = login_patient()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "patient@example.com"
    assert response.json()["role"] == "patient"


def test_patient_cannot_access_admin_endpoint():
    token = login_patient()

    response = client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_can_access_admin_endpoint():
    token = create_test_admin()

    response = client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted"


def test_patient_cannot_access_doctor_endpoint():
    token = login_patient()

    response = client.get(
        "/auth/doctor-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ============================================================
# DOCTOR DIRECTORY TESTS
# ============================================================

def test_doctor_directory_is_public():
    doctors["doctor-1"] = sample_doctor()

    response = client.get("/doctors")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["specialization"] == "Cardiology"


def test_unavailable_doctors_are_not_listed():
    doctors["doctor-2"] = sample_doctor(
        doctor_id="doctor-2",
        available=False,
    )

    response = client.get("/doctors")

    assert response.status_code == 200
    assert response.json() == []


def test_get_doctor_by_id():
    doctors["doctor-1"] = sample_doctor()

    response = client.get("/doctors/doctor-1")

    assert response.status_code == 200
    assert response.json()["id"] == "doctor-1"
    assert response.json()["full_name"] == "Dr. Demo"


def test_get_unknown_doctor_returns_404():
    response = client.get("/doctors/unknown-doctor")

    assert response.status_code == 404


def test_creating_doctor_requires_authentication():
    response = client.post(
        "/doctors",
        json={
            "full_name": "Dr. Demo",
            "specialization": "Cardiology",
            "qualifications": "MD",
            "experience_years": 10,
            "consultation_fee": 500,
            "available": True,
        },
    )

    assert response.status_code == 401


def test_patient_cannot_create_doctor():
    token = login_patient()

    response = client.post(
        "/doctors",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Dr. Demo",
            "specialization": "Cardiology",
            "qualifications": "MD",
            "experience_years": 10,
            "consultation_fee": 500,
            "available": True,
        },
    )

    assert response.status_code == 403


def test_admin_can_create_doctor():
    token = create_test_admin()

    response = client.post(
        "/doctors",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Dr. Demo",
            "specialization": "Cardiology",
            "qualifications": "MD",
            "experience_years": 10,
            "consultation_fee": 500,
            "available": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["full_name"] == "Dr. Demo"
    assert response.json()["specialization"] == "Cardiology"
    assert response.json()["available"] is True
    assert response.json()["id"]


def test_admin_created_doctor_appears_in_directory():
    token = create_test_admin()

    client.post(
        "/doctors",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Dr. Demo",
            "specialization": "Cardiology",
            "qualifications": "MD",
            "experience_years": 10,
            "consultation_fee": 500,
            "available": True,
        },
    )

    response = client.get("/doctors")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["full_name"] == "Dr. Demo"


# ============================================================
# APPOINTMENT MANAGEMENT TESTS
# ============================================================

def test_patient_can_request_appointment():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    response = create_test_appointment(patient_token)

    assert response.status_code == 201
    assert response.json()["status"] == "requested"
    assert response.json()["doctor_id"] == "doctor-1"
    assert response.json()["patient_email"] == "patient@example.com"


def test_patient_cannot_book_unavailable_doctor():
    doctors["doctor-1"] = sample_doctor(available=False)
    patient_token = login_patient()

    response = create_test_appointment(patient_token)

    assert response.status_code == 404


def test_appointment_requires_patient_authentication():
    response = client.post(
        "/appointments",
        json={
            "doctor_id": "doctor-1",
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat(),
            "reason": "Routine consultation",
        },
    )

    assert response.status_code == 401


def test_patient_can_view_own_appointments():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    create_response = create_test_appointment(patient_token)
    assert create_response.status_code == 201

    response = client.get(
        "/appointments/mine",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["patient_email"] == "patient@example.com"


def test_patient_can_cancel_own_appointment():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    create_response = create_test_appointment(patient_token)
    appointment_id = create_response.json()["id"]

    response = client.patch(
        f"/appointments/{appointment_id}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_patient_cannot_cancel_another_patients_appointment():
    doctors["doctor-1"] = sample_doctor()
    first_patient_token = login_patient()

    create_response = create_test_appointment(first_patient_token)
    appointment_id = create_response.json()["id"]

    # Create a second patient without deleting the appointment.
    users.pop("patient@example.com")

    second_patient_email = "secondpatient@example.com"
    users[second_patient_email] = {
        "full_name": "Second Patient",
        "email": second_patient_email,
        "hashed_password": hash_password("SecondPatient!2026Secure"),
        "role": "patient",
    }

    login_response = client.post(
        "/auth/login",
        json={
            "email": second_patient_email,
            "password": "SecondPatient!2026Secure",
        },
    )

    assert login_response.status_code == 200
    second_patient_token = login_response.json()["access_token"]

    response = client.patch(
        f"/appointments/{appointment_id}/cancel",
        headers={"Authorization": f"Bearer {second_patient_token}"},
    )

    assert response.status_code == 403


def test_doctor_can_view_assigned_appointments():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    create_response = create_test_appointment(patient_token)
    assert create_response.status_code == 201

    doctor_token = create_test_doctor()

    response = client.get(
        "/appointments/doctor",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["doctor_id"] == "doctor-1"


def test_doctor_can_confirm_assigned_appointment():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    create_response = create_test_appointment(patient_token)
    appointment_id = create_response.json()["id"]

    doctor_token = create_test_doctor()

    response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"status": "confirmed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_doctor_cannot_update_another_doctors_appointment():
    doctors["doctor-1"] = sample_doctor()
    doctors["doctor-2"] = sample_doctor(doctor_id="doctor-2")

    patient_token = login_patient()
    create_response = create_test_appointment(patient_token)

    appointment_id = create_response.json()["id"]
    doctor_two_token = create_test_doctor("doctor-2")

    response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers={"Authorization": f"Bearer {doctor_two_token}"},
        json={"status": "confirmed"},
    )

    assert response.status_code == 403


def test_completed_appointment_cannot_be_cancelled():
    doctors["doctor-1"] = sample_doctor()
    patient_token = login_patient()

    create_response = create_test_appointment(patient_token)
    appointment_id = create_response.json()["id"]

    doctor_token = create_test_doctor()

    confirm_response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"status": "confirmed"},
    )
    assert confirm_response.status_code == 200

    complete_response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"status": "completed"},
    )
    assert complete_response.status_code == 200

    cancel_response = client.patch(
        f"/appointments/{appointment_id}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert cancel_response.status_code == 400



# ============================================================
# ADMIN-MANAGED DOCTOR ACCOUNT TESTS
# ============================================================

def test_admin_can_create_doctor_account():
    admin_token = create_test_admin()
    doctors["doctor-1"] = sample_doctor()

    response = client.post(
        "/doctors/doctor-1/account",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "doctor@example.com",
            "password": "DoctorLogin!2026Secure",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "doctor"
    assert response.json()["email"] == "doctor@example.com"

    assert users["doctor@example.com"]["role"] == "doctor"
    assert users["doctor@example.com"]["doctor_id"] == "doctor-1"
    assert "hashed_password" in users["doctor@example.com"]
    assert users["doctor@example.com"]["hashed_password"] != "DoctorLogin!2026Secure"


def test_provisioned_doctor_can_login():
    admin_token = create_test_admin()
    doctors["doctor-1"] = sample_doctor()

    create_response = client.post(
        "/doctors/doctor-1/account",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "doctor@example.com",
            "password": "DoctorLogin!2026Secure",
        },
    )

    assert create_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "email": "doctor@example.com",
            "password": "DoctorLogin!2026Secure",
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_patient_cannot_create_doctor_account():
    patient_token = login_patient()
    doctors["doctor-1"] = sample_doctor()

    response = client.post(
        "/doctors/doctor-1/account",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "email": "doctor@example.com",
            "password": "DoctorLogin!2026Secure",
        },
    )

    assert response.status_code == 403


def test_doctor_account_requires_existing_doctor():
    admin_token = create_test_admin()

    response = client.post(
        "/doctors/unknown-doctor/account",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "doctor@example.com",
            "password": "DoctorLogin!2026Secure",
        },
    )

    assert response.status_code == 404


def test_duplicate_doctor_account_is_rejected():
    admin_token = create_test_admin()
    doctors["doctor-1"] = sample_doctor()

    payload = {
        "email": "doctor@example.com",
        "password": "DoctorLogin!2026Secure",
    }

    first_response = client.post(
        "/doctors/doctor-1/account",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/doctors/doctor-1/account",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )

    assert second_response.status_code == 409
