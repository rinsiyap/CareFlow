
import pytest

from careflow_api.repositories import (
    InMemoryAppointmentRepository,
    InMemoryDoctorAccountProvisioner,
    InMemoryDoctorRepository,
    InMemoryUserRepository,
)
from careflow_api.repository_contracts import (
    AppointmentRepository,
    DoctorAccountProvisioner,
    DoctorRepository,
    UserRepository,
)


# =============================================================
# FIXTURES
# =============================================================

@pytest.fixture
def user_repository():
    return InMemoryUserRepository()


@pytest.fixture
def doctor_repository():
    return InMemoryDoctorRepository()


@pytest.fixture
def appointment_repository():
    return InMemoryAppointmentRepository()


@pytest.fixture
def provisioner(user_repository, doctor_repository):
    return InMemoryDoctorAccountProvisioner(
        users=user_repository,
        doctors=doctor_repository,
    )


@pytest.fixture
def sample_user():
    return {
        "full_name": "Test Patient",
        "email": "patient@example.com",
        "hashed_password": "test-hash",
        "role": "patient",
    }


@pytest.fixture
def sample_doctor():
    return {
        "id": "doctor-001",
        "full_name": "Dr. Test",
        "specialization": "General Medicine",
        "qualifications": "MBBS",
        "experience_years": 5,
        "consultation_fee": 500.0,
        "available": True,
    }


@pytest.fixture
def sample_appointment():
    return {
        "id": "appointment-001",
        "patient_email": "patient@example.com",
        "doctor_id": "doctor-001",
        "scheduled_at": "2026-12-01T10:00:00+00:00",
        "reason": "General consultation",
        "status": "requested",
        "created_at": "2026-11-11T10:00:00+00:00",
    }


# =============================================================
# USER REPOSITORY TESTS
# =============================================================

def test_user_repository_satisfies_contract(user_repository):
    assert isinstance(user_repository, UserRepository)


def test_create_and_retrieve_user(user_repository, sample_user):
    created = user_repository.create_user(sample_user)

    retrieved = user_repository.get_by_email(
        "patient@example.com"
    )

    assert created == sample_user
    assert retrieved == sample_user


def test_get_nonexistent_user_returns_none(user_repository):
    assert user_repository.get_by_email(
        "missing@example.com"
    ) is None


def test_duplicate_user_creation_is_rejected(
    user_repository,
    sample_user,
):
    user_repository.create_user(sample_user)

    with pytest.raises(ValueError, match="Record already exists"):
        user_repository.create_user(sample_user)


# =============================================================
# DOCTOR REPOSITORY TESTS
# =============================================================

def test_doctor_repository_satisfies_contract(doctor_repository):
    assert isinstance(doctor_repository, DoctorRepository)


def test_create_and_retrieve_doctor(
    doctor_repository,
    sample_doctor,
):
    created = doctor_repository.create_doctor(sample_doctor)

    retrieved = doctor_repository.get_by_id("doctor-001")

    assert created == sample_doctor
    assert retrieved == sample_doctor


def test_get_nonexistent_doctor_returns_none(doctor_repository):
    assert doctor_repository.get_by_id("missing-doctor") is None


def test_list_available_returns_only_available_doctors(
    doctor_repository,
    sample_doctor,
):
    unavailable_doctor = {
        **sample_doctor,
        "id": "doctor-002",
        "full_name": "Dr. Unavailable",
        "available": False,
    }

    doctor_repository.create_doctor(sample_doctor)
    doctor_repository.create_doctor(unavailable_doctor)

    available = doctor_repository.list_available()

    assert len(available) == 1
    assert available[0]["id"] == "doctor-001"
    assert available[0]["available"] is True


def test_duplicate_doctor_creation_is_rejected(
    doctor_repository,
    sample_doctor,
):
    doctor_repository.create_doctor(sample_doctor)

    with pytest.raises(ValueError, match="Record already exists"):
        doctor_repository.create_doctor(sample_doctor)


# =============================================================
# APPOINTMENT REPOSITORY TESTS
# =============================================================

def test_appointment_repository_satisfies_contract(
    appointment_repository,
):
    assert isinstance(
        appointment_repository,
        AppointmentRepository,
    )


def test_create_and_retrieve_appointment(
    appointment_repository,
    sample_appointment,
):
    created = appointment_repository.create_appointment(
        sample_appointment
    )

    retrieved = appointment_repository.get_by_id(
        "appointment-001"
    )

    assert created == sample_appointment
    assert retrieved == sample_appointment


def test_get_nonexistent_appointment_returns_none(
    appointment_repository,
):
    assert appointment_repository.get_by_id(
        "missing-appointment"
    ) is None


def test_list_appointments_for_patient(
    appointment_repository,
    sample_appointment,
):
    second_appointment = {
        **sample_appointment,
        "id": "appointment-002",
    }

    other_patient_appointment = {
        **sample_appointment,
        "id": "appointment-003",
        "patient_email": "other@example.com",
    }

    appointment_repository.create_appointment(sample_appointment)
    appointment_repository.create_appointment(second_appointment)
    appointment_repository.create_appointment(
        other_patient_appointment
    )

    results = appointment_repository.list_for_patient(
        "patient@example.com"
    )

    assert len(results) == 2
    assert {
        appointment["id"] for appointment in results
    } == {"appointment-001", "appointment-002"}


def test_list_appointments_for_doctor(
    appointment_repository,
    sample_appointment,
):
    second_appointment = {
        **sample_appointment,
        "id": "appointment-002",
    }

    other_doctor_appointment = {
        **sample_appointment,
        "id": "appointment-003",
        "doctor_id": "doctor-002",
    }

    appointment_repository.create_appointment(sample_appointment)
    appointment_repository.create_appointment(second_appointment)
    appointment_repository.create_appointment(
        other_doctor_appointment
    )

    results = appointment_repository.list_for_doctor(
        "doctor-001"
    )

    assert len(results) == 2
    assert all(
        appointment["doctor_id"] == "doctor-001"
        for appointment in results
    )


def test_list_all_appointments(
    appointment_repository,
    sample_appointment,
):
    second_appointment = {
        **sample_appointment,
        "id": "appointment-002",
    }

    appointment_repository.create_appointment(sample_appointment)
    appointment_repository.create_appointment(second_appointment)

    results = appointment_repository.list_all()

    assert len(results) == 2


def test_successful_appointment_status_transition(
    appointment_repository,
    sample_appointment,
):
    appointment_repository.create_appointment(sample_appointment)

    updated = appointment_repository.transition_status(
        appointment_id="appointment-001",
        expected_status="requested",
        new_status="confirmed",
    )

    assert updated is not None
    assert updated["status"] == "confirmed"


def test_stale_appointment_status_transition_is_rejected(
    appointment_repository,
    sample_appointment,
):
    appointment_repository.create_appointment(sample_appointment)

    updated = appointment_repository.transition_status(
        appointment_id="appointment-001",
        expected_status="confirmed",
        new_status="completed",
    )

    assert updated is None

    unchanged = appointment_repository.get_by_id(
        "appointment-001"
    )

    assert unchanged["status"] == "requested"


def test_transition_for_nonexistent_appointment_returns_none(
    appointment_repository,
):
    updated = appointment_repository.transition_status(
        appointment_id="missing-appointment",
        expected_status="requested",
        new_status="confirmed",
    )

    assert updated is None


def test_appointment_can_transition_from_confirmed_to_completed(
    appointment_repository,
    sample_appointment,
):
    appointment_repository.create_appointment(sample_appointment)

    appointment_repository.transition_status(
        appointment_id="appointment-001",
        expected_status="requested",
        new_status="confirmed",
    )

    updated = appointment_repository.transition_status(
        appointment_id="appointment-001",
        expected_status="confirmed",
        new_status="completed",
    )

    assert updated is not None
    assert updated["status"] == "completed"


# =============================================================
# DOCTOR ACCOUNT PROVISIONER TESTS
# =============================================================

def test_provisioner_satisfies_contract(provisioner):
    assert isinstance(provisioner, DoctorAccountProvisioner)


def test_provision_doctor_account_successfully(
    user_repository,
    doctor_repository,
    provisioner,
    sample_doctor,
):
    doctor_repository.create_doctor(sample_doctor)

    doctor_user = {
        "full_name": sample_doctor["full_name"],
        "email": "doctor@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    created_user = provisioner.provision_doctor_account(
        doctor_id="doctor-001",
        user=doctor_user,
    )

    linked_doctor = doctor_repository.get_by_id("doctor-001")
    stored_user = user_repository.get_by_email(
        "doctor@example.com"
    )

    assert created_user == doctor_user
    assert stored_user == doctor_user
    assert linked_doctor["account_email"] == "doctor@example.com"


def test_provisioner_rejects_missing_doctor(
    provisioner,
):
    doctor_user = {
        "full_name": "Dr. Missing",
        "email": "missing@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "missing-doctor",
    }

    with pytest.raises(ValueError, match="Doctor not found"):
        provisioner.provision_doctor_account(
            doctor_id="missing-doctor",
            user=doctor_user,
        )


def test_provisioner_rejects_duplicate_email(
    user_repository,
    doctor_repository,
    provisioner,
    sample_doctor,
):
    doctor_repository.create_doctor(sample_doctor)

    user_repository.create_user({
        "full_name": "Existing User",
        "email": "existing@example.com",
        "hashed_password": "test-hash",
        "role": "patient",
    })

    doctor_user = {
        "full_name": sample_doctor["full_name"],
        "email": "existing@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    with pytest.raises(
        ValueError,
        match="An account with this email already exists",
    ):
        provisioner.provision_doctor_account(
            doctor_id="doctor-001",
            user=doctor_user,
        )

    assert doctor_repository.get_by_id(
        "doctor-001"
    ).get("account_email") is None


def test_provisioner_rejects_already_linked_doctor(
    user_repository,
    doctor_repository,
    provisioner,
    sample_doctor,
):
    linked_doctor = {
        **sample_doctor,
        "account_email": "already-linked@example.com",
    }

    doctor_repository.create_doctor(linked_doctor)

    doctor_user = {
        "full_name": linked_doctor["full_name"],
        "email": "new-doctor@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    with pytest.raises(
        ValueError,
        match="This doctor already has a login account",
    ):
        provisioner.provision_doctor_account(
            doctor_id="doctor-001",
            user=doctor_user,
        )

    assert user_repository.get_by_email(
        "new-doctor@example.com"
    ) is None


def test_provisioner_rejects_wrong_doctor_link(
    user_repository,
    doctor_repository,
    provisioner,
    sample_doctor,
):
    doctor_repository.create_doctor(sample_doctor)

    doctor_user = {
        "full_name": sample_doctor["full_name"],
        "email": "wrong-link@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-002",
    }

    with pytest.raises(
        ValueError,
        match="Doctor account is not linked to the correct profile",
    ):
        provisioner.provision_doctor_account(
            doctor_id="doctor-001",
            user=doctor_user,
        )

    assert user_repository.get_by_email(
        "wrong-link@example.com"
    ) is None
