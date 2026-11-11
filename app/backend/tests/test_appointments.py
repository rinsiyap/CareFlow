
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from careflow_api.dependencies import appointments, doctors, users
from careflow_api.main import app
from careflow_api.security import hash_password


client = TestClient(app)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def reset_test_data():
    """Keep API tests isolated using the in-memory repositories."""
    users.clear()
    doctors.clear()
    appointments.clear()

    yield

    users.clear()
    doctors.clear()
    appointments.clear()


# ============================================================
# TEST HELPERS
# ============================================================

def register_and_login_patient(email="patient@example.com"):
    """Register a patient and return an access token."""
    password = "PatientTest!2026Secure"

    register_response = client.post(
        "/auth/register",
        json={
            "full_name": "Demo Patient",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def create_test_admin():
    """Create and authenticate a test administrator."""
    email = "admin@example.com"
    password = "AdminTest!2026Secure"

    users[email] = {
        "full_name": "Demo Admin",
        "email": email,
        "hashed_password": hash_password(password),
        "role": "admin",
    }

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def sample_doctor(doctor_id="doctor-1", available=True):
    return {
        "id": doctor_id,
        "full_name": f"Dr. {doctor_id}",
        "specialization": "Cardiology",
        "qualifications": "MBBS, MD",
        "experience_years": 10,
        "consultation_fee": 500.0,
        "available": available,
    }


def create_test_doctor(doctor_id="doctor-1"):
    """Create a doctor profile and authenticate its doctor account."""
    doctors[doctor_id] = sample_doctor(doctor_id)

    email = f"{doctor_id}@example.com"
    password = "DoctorTest!2026Secure"

    users[email] = {
        "full_name": f"Dr. {doctor_id}",
        "email": email,
        "hashed_password": hash_password(password),
        "role": "doctor",
        "doctor_id": doctor_id,
    }

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def create_appointment(patient_token, doctor_id="doctor-1"):
    """Create a future appointment through the API."""
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


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# APPOINTMENT CREATION VALIDATION
# ============================================================

def test_patient_cannot_book_appointment_in_the_past():
    doctors["doctor-1"] = sample_doctor()
    patient_token = register_and_login_patient()

    response = client.post(
        "/appointments",
        headers=auth_headers(patient_token),
        json={
            "doctor_id": "doctor-1",
            "scheduled_at": (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat(),
            "reason": "Routine consultation",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Appointment must be scheduled in the future"
    )


def test_patient_cannot_book_appointment_with_unknown_doctor():
    patient_token = register_and_login_patient()

    response = create_appointment(
        patient_token,
        doctor_id="unknown-doctor",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Available doctor not found"


def test_appointment_rejects_timezone_naive_datetime():
    patient_token = register_and_login_patient()
    doctors["doctor-1"] = sample_doctor()

    naive_datetime = (
        datetime.now() + timedelta(days=2)
    ).isoformat()

    response = client.post(
        "/appointments",
        headers=auth_headers(patient_token),
        json={
            "doctor_id": "doctor-1",
            "scheduled_at": naive_datetime,
            "reason": "Routine consultation",
        },
    )

    assert response.status_code == 422


def test_appointment_rejects_missing_reason():
    patient_token = register_and_login_patient()
    doctors["doctor-1"] = sample_doctor()

    response = client.post(
        "/appointments",
        headers=auth_headers(patient_token),
        json={
            "doctor_id": "doctor-1",
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 422


# ============================================================
# APPOINTMENT ACCESS
# ============================================================

def test_patient_only_sees_own_appointments():
    doctors["doctor-1"] = sample_doctor()

    first_patient = register_and_login_patient(
        "first@example.com",
    )
    second_patient = register_and_login_patient(
        "second@example.com",
    )

    first_booking = create_appointment(first_patient)
    second_booking = create_appointment(second_patient)

    assert first_booking.status_code == 201
    assert second_booking.status_code == 201

    response = client.get(
        "/appointments/mine",
        headers=auth_headers(first_patient),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["patient_email"] == "first@example.com"


def test_admin_can_view_all_appointments():
    doctors["doctor-1"] = sample_doctor()

    first_patient = register_and_login_patient(
        "first@example.com",
    )
    second_patient = register_and_login_patient(
        "second@example.com",
    )

    assert create_appointment(first_patient).status_code == 201
    assert create_appointment(second_patient).status_code == 201

    admin_token = create_test_admin()

    response = client.get(
        "/appointments/all",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 2

    patient_emails = {
        item["patient_email"] for item in response.json()
    }
    assert patient_emails == {
        "first@example.com",
        "second@example.com",
    }


def test_patient_cannot_view_all_appointments():
    patient_token = register_and_login_patient()

    response = client.get(
        "/appointments/all",
        headers=auth_headers(patient_token),
    )

    assert response.status_code == 403


def test_doctor_account_without_profile_link_cannot_list_appointments():
    email = "unlinked-doctor@example.com"
    password = "DoctorTest!2026Secure"

    users[email] = {
        "full_name": "Unlinked Doctor",
        "email": email,
        "hashed_password": hash_password(password),
        "role": "doctor",
    }

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/appointments/doctor",
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Doctor account is not linked to a doctor profile"
    )


# ============================================================
# APPOINTMENT STATUS VALIDATION
# ============================================================

def test_doctor_cannot_skip_requested_to_completed():
    doctors["doctor-1"] = sample_doctor()

    patient_token = register_and_login_patient()
    booking = create_appointment(patient_token)

    assert booking.status_code == 201
    appointment_id = booking.json()["id"]

    doctor_token = create_test_doctor()

    response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers=auth_headers(doctor_token),
        json={"status": "completed"},
    )

    assert response.status_code == 400
    assert "Cannot change appointment" in response.json()["detail"]


def test_appointment_status_rejects_unsupported_value():
    doctors["doctor-1"] = sample_doctor()

    patient_token = register_and_login_patient()
    booking = create_appointment(patient_token)

    assert booking.status_code == 201
    appointment_id = booking.json()["id"]

    doctor_token = create_test_doctor()

    response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers=auth_headers(doctor_token),
        json={"status": "pending"},
    )

    assert response.status_code == 422


def test_cancelling_unknown_appointment_returns_404():
    patient_token = register_and_login_patient()

    response = client.patch(
        "/appointments/unknown-appointment/cancel",
        headers=auth_headers(patient_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Appointment not found"


def test_updating_unknown_appointment_returns_404():
    doctor_token = create_test_doctor()

    response = client.patch(
        "/appointments/unknown-appointment/status",
        headers=auth_headers(doctor_token),
        json={"status": "confirmed"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Appointment not found"


# ============================================================
# CONDITIONAL STATUS TRANSITION CONFLICTS
# ============================================================

def test_patient_cancellation_returns_409_on_concurrent_status_change(
    monkeypatch,
):
    doctors["doctor-1"] = sample_doctor()

    patient_token = register_and_login_patient()
    booking = create_appointment(patient_token)

    assert booking.status_code == 201
    appointment_id = booking.json()["id"]

    def simulate_concurrent_change(
        appointment_id,
        expected_status,
        new_status,
    ):
        return None

    monkeypatch.setattr(
        appointments,
        "transition_status",
        simulate_concurrent_change,
    )

    response = client.patch(
        f"/appointments/{appointment_id}/cancel",
        headers=auth_headers(patient_token),
    )

    assert response.status_code == 409
    assert "status changed" in response.json()["detail"]


def test_doctor_status_update_returns_409_on_concurrent_change(
    monkeypatch,
):
    doctors["doctor-1"] = sample_doctor()

    patient_token = register_and_login_patient()
    booking = create_appointment(patient_token)

    assert booking.status_code == 201
    appointment_id = booking.json()["id"]

    doctor_token = create_test_doctor()

    def simulate_concurrent_change(
        appointment_id,
        expected_status,
        new_status,
    ):
        return None

    monkeypatch.setattr(
        appointments,
        "transition_status",
        simulate_concurrent_change,
    )

    response = client.patch(
        f"/appointments/{appointment_id}/status",
        headers=auth_headers(doctor_token),
        json={"status": "confirmed"},
    )

    assert response.status_code == 409
    assert "status changed" in response.json()["detail"]
