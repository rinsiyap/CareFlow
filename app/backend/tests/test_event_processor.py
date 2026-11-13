
import pytest

from careflow_api.event_processor import (
    AppointmentEventError,
    create_event_processor,
    validate_appointment_event,
)


@pytest.fixture
def created_event():
    return {
        "event_id": "event-001",
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-001",
        "created_at": "2026-11-12T08:00:00+00:00",
        "payload": {
            "appointment_id": "appointment-001",
            "patient_email": "patient@example.local",
            "doctor_id": "doctor-001",
            "scheduled_at": "2026-11-15T10:00:00+05:30",
            "status": "requested",
        },
    }


@pytest.fixture
def status_changed_event():
    return {
        "event_id": "event-002",
        "event_type": "appointment.status_changed",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-001",
        "created_at": "2026-11-12T08:30:00+00:00",
        "payload": {
            "appointment_id": "appointment-001",
            "patient_email": "patient@example.local",
            "doctor_id": "doctor-001",
            "previous_status": "requested",
            "new_status": "confirmed",
        },
    }


def test_valid_created_event(created_event):
    validate_appointment_event(created_event, "event-001")


def test_valid_status_changed_event(status_changed_event):
    validate_appointment_event(status_changed_event, "event-002")


@pytest.mark.parametrize(
    ("previous_status", "new_status"),
    [
        ("requested", "confirmed"),
        ("requested", "cancelled"),
        ("confirmed", "completed"),
        ("confirmed", "cancelled"),
    ],
)
def test_supported_status_transitions(
    status_changed_event,
    previous_status,
    new_status,
):
    status_changed_event["payload"]["previous_status"] = previous_status
    status_changed_event["payload"]["new_status"] = new_status

    validate_appointment_event(status_changed_event, "event-002")


def test_rejects_unsupported_status_transition(status_changed_event):
    status_changed_event["payload"]["previous_status"] = "requested"
    status_changed_event["payload"]["new_status"] = "completed"

    with pytest.raises(AppointmentEventError):
        validate_appointment_event(status_changed_event, "event-002")


def test_rejects_wrong_idempotency_key(created_event):
    with pytest.raises(AppointmentEventError):
        validate_appointment_event(created_event, "different-event")


def test_rejects_aggregate_id_mismatch(created_event):
    created_event["aggregate_id"] = "different-appointment"

    with pytest.raises(AppointmentEventError):
        validate_appointment_event(created_event, "event-001")


def test_rejects_unsupported_event_type(created_event):
    created_event["event_type"] = "appointment.deleted"

    with pytest.raises(AppointmentEventError):
        validate_appointment_event(created_event, "event-001")


def test_rejects_timezone_missing_from_scheduled_at(created_event):
    created_event["payload"]["scheduled_at"] = "2026-11-15T10:00:00"

    with pytest.raises(AppointmentEventError):
        validate_appointment_event(created_event, "event-001")


def test_rejects_extra_payload_field(created_event):
    created_event["payload"]["reason"] = "General consultation"

    with pytest.raises(AppointmentEventError):
        validate_appointment_event(created_event, "event-001")


def test_processor_calls_callback_after_validation(created_event):
    received_events = []
    processor = create_event_processor(received_events.append)

    processor(created_event, "event-001")

    assert received_events == [created_event]


def test_processor_does_not_call_callback_for_invalid_event(created_event):
    received_events = []
    processor = create_event_processor(received_events.append)

    created_event["payload"]["status"] = "completed"

    with pytest.raises(AppointmentEventError):
        processor(created_event, "event-001")

    assert received_events == []
