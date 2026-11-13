
import boto3
import pytest

from uuid import uuid4
from moto import mock_aws

from careflow_api.dynamodb_tables import create_dynamodb_tables
from careflow_api.dynamodb_repositories import (
    DynamoDBAppointmentRepository,
    DynamoDBDoctorAccountProvisioner,
    DynamoDBDoctorRepository,
    DynamoDBOutboxRepository,
    DynamoDBUserRepository,
)
from careflow_api.event_processor import create_event_processor


# =============================================================
# MOTO REPOSITORY FIXTURE
# Used by normal repository unit tests.
# =============================================================

@pytest.fixture
def repositories():
    with mock_aws():
        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-east-2",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )

        tables = create_dynamodb_tables(dynamodb)

        yield {
            "users": DynamoDBUserRepository(tables["users"]),
            "doctors": DynamoDBDoctorRepository(tables["doctors"]),
            "appointments": DynamoDBAppointmentRepository(
                tables["appointments"],
                outbox_table=tables["outbox"],
            ),
            "outbox": DynamoDBOutboxRepository(
                tables["outbox"],
            ),
            "provisioner": DynamoDBDoctorAccountProvisioner(
                tables["users"],
                tables["doctors"],
            ),
        }


# =============================================================
# DYNAMODB LOCAL FIXTURE
# Used for actual transaction integration tests.
#
# DynamoDB Local must be running at localhost:8000.
# =============================================================

@pytest.fixture
def local_repositories():
    """Connect to DynamoDB Local using unique test table names."""

    suffix = uuid4().hex[:10]

    dynamodb = boto3.resource(
        "dynamodb",
        region_name="us-east-2",
        endpoint_url="http://localhost:8000",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    tables = create_dynamodb_tables(
        dynamodb,
        table_names={
            "users": f"CareFlow-Test-Users-{suffix}",
            "doctors": f"CareFlow-Test-Doctors-{suffix}",
            "appointments": f"CareFlow-Test-Appointments-{suffix}",
            "outbox": f"CareFlow-Test-Outbox-{suffix}",
        },
    )

    try:
        yield {
            "users": DynamoDBUserRepository(tables["users"]),
            "doctors": DynamoDBDoctorRepository(tables["doctors"]),
            "appointments": DynamoDBAppointmentRepository(
                tables["appointments"],
                outbox_table=tables["outbox"],
            ),
            "outbox": DynamoDBOutboxRepository(
                tables["outbox"],
            ),
            "provisioner": DynamoDBDoctorAccountProvisioner(
                tables["users"],
                tables["doctors"],
            ),
        }

    finally:
        for table in tables.values():
            table.delete()


# =============================================================
# SAMPLE DATA
# =============================================================

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
# USER REPOSITORY
# =============================================================

def test_create_and_get_user(repositories, sample_user):
    users = repositories["users"]

    created = users.create_user(sample_user)
    retrieved = users.get_by_email(sample_user["email"])

    assert created == sample_user
    assert retrieved == sample_user


def test_get_missing_user_returns_none(repositories):
    assert repositories["users"].get_by_email(
        "missing@example.com"
    ) is None


def test_duplicate_user_is_rejected(repositories, sample_user):
    users = repositories["users"]
    users.create_user(sample_user)

    with pytest.raises(ValueError, match="User already exists"):
        users.create_user(sample_user)


# =============================================================
# DOCTOR REPOSITORY
# =============================================================

def test_create_and_get_doctor(repositories, sample_doctor):
    doctors = repositories["doctors"]

    created = doctors.create_doctor(sample_doctor)
    retrieved = doctors.get_by_id("doctor-001")

    assert created == sample_doctor
    assert retrieved == sample_doctor
    assert isinstance(retrieved["consultation_fee"], float)


def test_missing_doctor_returns_none(repositories):
    assert repositories["doctors"].get_by_id(
        "missing-doctor"
    ) is None


def test_duplicate_doctor_is_rejected(repositories, sample_doctor):
    doctors = repositories["doctors"]
    doctors.create_doctor(sample_doctor)

    with pytest.raises(ValueError, match="Doctor already exists"):
        doctors.create_doctor(sample_doctor)


def test_list_available_doctors(repositories, sample_doctor):
    doctors = repositories["doctors"]

    unavailable = {
        **sample_doctor,
        "id": "doctor-002",
        "available": False,
    }

    doctors.create_doctor(sample_doctor)
    doctors.create_doctor(unavailable)

    result = doctors.list_available()

    assert len(result) == 1
    assert result[0]["id"] == "doctor-001"


# =============================================================
# APPOINTMENT REPOSITORY
# =============================================================

def test_create_and_get_appointment(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]

    created = appointments.create_appointment(sample_appointment)
    retrieved = appointments.get_by_id("appointment-001")

    assert created == sample_appointment
    assert retrieved == sample_appointment


def test_missing_appointment_returns_none(repositories):
    assert repositories["appointments"].get_by_id(
        "missing-appointment"
    ) is None


def test_duplicate_appointment_is_rejected(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    appointments.create_appointment(sample_appointment)

    with pytest.raises(ValueError, match="Appointment already exists"):
        appointments.create_appointment(sample_appointment)


def test_query_appointments_for_patient(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]

    second = {
        **sample_appointment,
        "id": "appointment-002",
        "scheduled_at": "2026-12-02T10:00:00+00:00",
    }

    other_patient = {
        **sample_appointment,
        "id": "appointment-003",
        "patient_email": "other@example.com",
        "scheduled_at": "2026-12-03T10:00:00+00:00",
    }

    appointments.create_appointment(sample_appointment)
    appointments.create_appointment(second)
    appointments.create_appointment(other_patient)

    result = appointments.list_for_patient(
        "patient@example.com"
    )

    assert len(result) == 2
    assert {
        item["id"] for item in result
    } == {"appointment-001", "appointment-002"}


def test_query_appointments_for_doctor(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]

    second = {
        **sample_appointment,
        "id": "appointment-002",
        "scheduled_at": "2026-12-02T10:00:00+00:00",
    }

    other_doctor = {
        **sample_appointment,
        "id": "appointment-003",
        "doctor_id": "doctor-002",
        "scheduled_at": "2026-12-03T10:00:00+00:00",
    }

    appointments.create_appointment(sample_appointment)
    appointments.create_appointment(second)
    appointments.create_appointment(other_doctor)

    result = appointments.list_for_doctor("doctor-001")

    assert len(result) == 2
    assert all(
        item["doctor_id"] == "doctor-001"
        for item in result
    )


def test_list_all_appointments(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]

    appointments.create_appointment(sample_appointment)

    appointments.create_appointment({
        **sample_appointment,
        "id": "appointment-002",
        "scheduled_at": "2026-12-02T10:00:00+00:00",
    })

    assert len(appointments.list_all()) == 2


def test_successful_status_transition(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "requested",
        "confirmed",
    )

    assert updated is not None
    assert updated["status"] == "confirmed"


def test_stale_status_transition_is_rejected(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "confirmed",
        "completed",
    )

    assert updated is None

    unchanged = appointments.get_by_id("appointment-001")
    assert unchanged["status"] == "requested"


def test_transition_for_missing_appointment_returns_none(
    repositories,
):
    updated = repositories["appointments"].transition_status(
        "missing-appointment",
        "requested",
        "confirmed",
    )

    assert updated is None


# =============================================================
# TRANSACTIONAL APPOINTMENT + OUTBOX TESTS (MOTO)
# =============================================================

def test_appointment_creation_writes_outbox_event(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]

    created = appointments.create_appointment(sample_appointment)

    assert created == sample_appointment

    events = outbox.list_pending()

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "appointment.created"
    assert event["aggregate_type"] == "appointment"
    assert event["aggregate_id"] == "appointment-001"
    assert event["status"] == "pending"
    assert event["payload"]["appointment_id"] == "appointment-001"
    assert event["payload"]["patient_email"] == "patient@example.com"
    assert event["payload"]["doctor_id"] == "doctor-001"


def test_duplicate_appointment_does_not_create_extra_outbox_event(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    with pytest.raises(ValueError, match="Appointment already exists"):
        appointments.create_appointment(sample_appointment)

    events = outbox.list_pending()

    assert len(events) == 1
    assert events[0]["event_type"] == "appointment.created"


def test_status_transition_writes_outbox_event(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "requested",
        "confirmed",
    )

    assert updated is not None
    assert updated["status"] == "confirmed"

    events = outbox.list_pending()

    assert len(events) == 2

    status_events = [
        event
        for event in events
        if event["event_type"] == "appointment.status_changed"
    ]

    assert len(status_events) == 1

    event = status_events[0]

    assert event["aggregate_id"] == "appointment-001"
    assert event["status"] == "pending"
    assert event["payload"]["previous_status"] == "requested"
    assert event["payload"]["new_status"] == "confirmed"


def test_created_outbox_event_is_accepted_by_event_processor(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]
    processor = create_event_processor()

    appointments.create_appointment(sample_appointment)

    events = outbox.list_pending()

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "appointment.created"

    # Validate the actual repository-generated event.
    result = processor(
        event,
        event["event_id"],
    )

    assert result is None


def test_status_changed_outbox_event_is_accepted_by_event_processor(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]
    processor = create_event_processor()

    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "requested",
        "confirmed",
    )

    assert updated is not None

    events = outbox.list_pending()

    status_events = [
        event
        for event in events
        if event["event_type"] == "appointment.status_changed"
    ]

    assert len(status_events) == 1

    event = status_events[0]

    # Validate the actual repository-generated event.
    result = processor(
        event,
        event["event_id"],
    )

    assert result is None


def test_stale_transition_does_not_create_outbox_event(
    repositories,
    sample_appointment,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "confirmed",
        "completed",
    )

    assert updated is None

    events = outbox.list_pending()

    assert len(events) == 1
    assert events[0]["event_type"] == "appointment.created"

    current = appointments.get_by_id("appointment-001")
    assert current["status"] == "requested"


def test_missing_appointment_transition_does_not_create_outbox_event(
    repositories,
):
    appointments = repositories["appointments"]
    outbox = repositories["outbox"]

    updated = appointments.transition_status(
        "missing-appointment",
        "requested",
        "confirmed",
    )

    assert updated is None
    assert outbox.list_pending() == []


# =============================================================
# DOCTOR ACCOUNT PROVISIONER
# =============================================================

def test_successful_atomic_doctor_account_provisioning(
    local_repositories,
    sample_doctor,
):
    """
    Test actual DynamoDB transaction behavior using DynamoDB Local.

    This test verifies that:
    1. The doctor account user is created.
    2. The doctor profile is linked to the new account.
    3. Both changes are committed successfully.
    """

    doctors = local_repositories["doctors"]
    users = local_repositories["users"]
    provisioner = local_repositories["provisioner"]

    doctors.create_doctor(sample_doctor)

    doctor_user = {
        "full_name": "Dr. Test",
        "email": "doctor@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    result = provisioner.provision_doctor_account(
        "doctor-001",
        doctor_user,
    )

    assert result == doctor_user

    created_user = users.get_by_email("doctor@example.com")
    assert created_user == doctor_user

    linked_doctor = doctors.get_by_id("doctor-001")
    assert linked_doctor["account_email"] == "doctor@example.com"


def test_provisioner_rejects_missing_doctor(repositories):
    doctor_user = {
        "full_name": "Dr. Missing",
        "email": "missing@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "missing-doctor",
    }

    with pytest.raises(ValueError, match="Doctor not found"):
        repositories["provisioner"].provision_doctor_account(
            "missing-doctor",
            doctor_user,
        )


def test_provisioner_rejects_existing_email(
    repositories,
    sample_doctor,
):
    doctors = repositories["doctors"]
    users = repositories["users"]

    doctors.create_doctor(sample_doctor)

    users.create_user({
        "full_name": "Existing Patient",
        "email": "existing@example.com",
        "hashed_password": "test-hash",
        "role": "patient",
    })

    doctor_user = {
        "full_name": "Dr. Test",
        "email": "existing@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    with pytest.raises(ValueError, match="already exists"):
        repositories["provisioner"].provision_doctor_account(
            "doctor-001",
            doctor_user,
        )


def test_provisioner_rejects_already_linked_doctor(
    repositories,
    sample_doctor,
):
    doctors = repositories["doctors"]

    linked_doctor = {
        **sample_doctor,
        "account_email": "existing-doctor@example.com",
    }

    doctors.create_doctor(linked_doctor)

    doctor_user = {
        "full_name": "Dr. Test",
        "email": "new-doctor@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-001",
    }

    with pytest.raises(ValueError, match="already has a login account"):
        repositories["provisioner"].provision_doctor_account(
            "doctor-001",
            doctor_user,
        )


def test_provisioner_rejects_wrong_doctor_link(
    repositories,
    sample_doctor,
):
    repositories["doctors"].create_doctor(sample_doctor)

    doctor_user = {
        "full_name": "Dr. Test",
        "email": "wrong-link@example.com",
        "hashed_password": "test-hash",
        "role": "doctor",
        "doctor_id": "doctor-002",
    }

    with pytest.raises(ValueError, match="correct profile"):
        repositories["provisioner"].provision_doctor_account(
            "doctor-001",
            doctor_user,
        )


# =============================================================
# DYNAMODB LOCAL INTEGRATION TESTS
# These tests use the actual DynamoDB Local database.
# =============================================================

def test_local_create_and_get_user(
    local_repositories,
    sample_user,
):
    users = local_repositories["users"]

    users.create_user(sample_user)

    retrieved = users.get_by_email(
        sample_user["email"]
    )

    assert retrieved == sample_user


def test_local_duplicate_user_is_rejected(
    local_repositories,
    sample_user,
):
    users = local_repositories["users"]

    users.create_user(sample_user)

    with pytest.raises(ValueError, match="User already exists"):
        users.create_user(sample_user)


def test_local_create_and_list_available_doctors(
    local_repositories,
    sample_doctor,
):
    doctors = local_repositories["doctors"]

    unavailable_doctor = {
        **sample_doctor,
        "id": "doctor-002",
        "available": False,
    }

    doctors.create_doctor(sample_doctor)
    doctors.create_doctor(unavailable_doctor)

    retrieved = doctors.get_by_id("doctor-001")
    available = doctors.list_available()

    assert retrieved == sample_doctor
    assert isinstance(retrieved["consultation_fee"], float)

    assert len(available) == 1
    assert available[0]["id"] == "doctor-001"


def test_local_duplicate_doctor_is_rejected(
    local_repositories,
    sample_doctor,
):
    doctors = local_repositories["doctors"]

    doctors.create_doctor(sample_doctor)

    with pytest.raises(ValueError, match="Doctor already exists"):
        doctors.create_doctor(sample_doctor)


def test_local_appointment_queries_return_application_records(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]

    second_appointment = {
        **sample_appointment,
        "id": "appointment-002",
        "scheduled_at": "2026-12-02T10:00:00+00:00",
    }

    other_patient_appointment = {
        **sample_appointment,
        "id": "appointment-003",
        "patient_email": "other@example.com",
        "scheduled_at": "2026-12-03T10:00:00+00:00",
    }

    appointments.create_appointment(sample_appointment)
    appointments.create_appointment(second_appointment)
    appointments.create_appointment(other_patient_appointment)

    # Verify direct retrieval.
    retrieved = appointments.get_by_id("appointment-001")
    assert retrieved == sample_appointment
    assert "appointment_id" not in retrieved

    # Verify the patient GSI.
    patient_results = appointments.list_for_patient(
        "patient@example.com"
    )

    assert len(patient_results) == 2
    assert [
        item["id"] for item in patient_results
    ] == [
        "appointment-001",
        "appointment-002",
    ]

    # Verify the doctor GSI.
    doctor_results = appointments.list_for_doctor("doctor-001")

    assert len(doctor_results) == 3

    # Internal DynamoDB keys must not leak into application records.
    for record in patient_results + doctor_results:
        assert "appointment_id" not in record


def test_local_duplicate_appointment_is_rejected(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]

    appointments.create_appointment(sample_appointment)

    with pytest.raises(
        ValueError,
        match="Appointment already exists",
    ):
        appointments.create_appointment(sample_appointment)


# =============================================================
# TRANSACTIONAL APPOINTMENT + OUTBOX TESTS (DYNAMODB LOCAL)
# =============================================================

def test_local_appointment_creation_writes_outbox_event(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]
    outbox = local_repositories["outbox"]

    created = appointments.create_appointment(sample_appointment)

    assert created == sample_appointment

    events = outbox.list_pending()

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "appointment.created"
    assert event["aggregate_type"] == "appointment"
    assert event["aggregate_id"] == "appointment-001"
    assert event["status"] == "pending"
    assert event["payload"]["appointment_id"] == "appointment-001"


def test_local_duplicate_appointment_does_not_create_extra_event(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]
    outbox = local_repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    with pytest.raises(
        ValueError,
        match="Appointment already exists",
    ):
        appointments.create_appointment(sample_appointment)

    events = outbox.list_pending()

    assert len(events) == 1
    assert events[0]["event_type"] == "appointment.created"


def test_local_status_transition_writes_outbox_event(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]
    outbox = local_repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "requested",
        "confirmed",
    )

    assert updated is not None
    assert updated["status"] == "confirmed"

    events = outbox.list_pending()

    assert len(events) == 2

    status_events = [
        event
        for event in events
        if event["event_type"] == "appointment.status_changed"
    ]

    assert len(status_events) == 1

    event = status_events[0]

    assert event["aggregate_id"] == "appointment-001"
    assert event["status"] == "pending"
    assert event["payload"]["previous_status"] == "requested"
    assert event["payload"]["new_status"] == "confirmed"


def test_local_stale_transition_does_not_create_outbox_event(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]
    outbox = local_repositories["outbox"]

    appointments.create_appointment(sample_appointment)

    updated = appointments.transition_status(
        "appointment-001",
        "confirmed",
        "completed",
    )

    assert updated is None

    events = outbox.list_pending()

    assert len(events) == 1
    assert events[0]["event_type"] == "appointment.created"

    current = appointments.get_by_id("appointment-001")
    assert current["status"] == "requested"


def test_local_missing_appointment_transition_does_not_create_event(
    local_repositories,
):
    appointments = local_repositories["appointments"]
    outbox = local_repositories["outbox"]

    updated = appointments.transition_status(
        "missing-appointment",
        "requested",
        "confirmed",
    )

    assert updated is None
    assert outbox.list_pending() == []


def test_local_appointment_status_transition_is_conditional(
    local_repositories,
    sample_appointment,
):
    appointments = local_repositories["appointments"]

    appointments.create_appointment(sample_appointment)

    # Valid transition.
    confirmed = appointments.transition_status(
        "appointment-001",
        "requested",
        "confirmed",
    )

    assert confirmed is not None
    assert confirmed["status"] == "confirmed"

    # Stale transition must not overwrite the current status.
    stale_update = appointments.transition_status(
        "appointment-001",
        "requested",
        "cancelled",
    )

    assert stale_update is None

    current = appointments.get_by_id("appointment-001")

    assert current["status"] == "confirmed"
