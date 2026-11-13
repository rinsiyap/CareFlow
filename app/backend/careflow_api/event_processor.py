
"""Validation and processing for CareFlow appointment events.

This processor currently validates events only. It performs no external
notifications or database mutations.
"""

from datetime import datetime
from typing import Any, Callable


SUPPORTED_TRANSITIONS = {
    ("requested", "confirmed"),
    ("requested", "cancelled"),
    ("confirmed", "completed"),
    ("confirmed", "cancelled"),
}

CREATED_PAYLOAD_FIELDS = {
    "appointment_id",
    "patient_email",
    "doctor_id",
    "scheduled_at",
    "status",
}

STATUS_CHANGED_PAYLOAD_FIELDS = {
    "appointment_id",
    "patient_email",
    "doctor_id",
    "previous_status",
    "new_status",
}


class AppointmentEventError(ValueError):
    """Raised when an appointment event is invalid."""


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppointmentEventError(
            f"{field_name} must be a non-empty string"
        )

    return value


def _validate_timestamp(value: Any, field_name: str) -> None:
    timestamp = _require_non_empty_string(value, field_name)

    try:
        parsed = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise AppointmentEventError(
            f"{field_name} must be a valid ISO timestamp"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AppointmentEventError(
            f"{field_name} must include a timezone"
        )


def validate_appointment_event(
    event: dict[str, Any],
    idempotency_key: str,
) -> None:
    """Validate a supported appointment event without side effects."""

    if not isinstance(event, dict):
        raise AppointmentEventError("Event must be a dictionary")

    event_id = _require_non_empty_string(
        event.get("event_id"),
        "event_id",
    )
    supplied_key = _require_non_empty_string(
        idempotency_key,
        "idempotency_key",
    )

    if event_id != supplied_key:
        raise AppointmentEventError(
            "Idempotency key must match event_id"
        )

    event_type = _require_non_empty_string(
        event.get("event_type"),
        "event_type",
    )

    aggregate_type = _require_non_empty_string(
        event.get("aggregate_type"),
        "aggregate_type",
    )

    if aggregate_type != "appointment":
        raise AppointmentEventError(
            "aggregate_type must be appointment"
        )

    aggregate_id = _require_non_empty_string(
        event.get("aggregate_id"),
        "aggregate_id",
    )

    _validate_timestamp(event.get("created_at"), "created_at")

    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise AppointmentEventError("payload must be a dictionary")

    appointment_id = _require_non_empty_string(
        payload.get("appointment_id"),
        "payload.appointment_id",
    )

    if appointment_id != aggregate_id:
        raise AppointmentEventError(
            "aggregate_id must match payload.appointment_id"
        )

    _require_non_empty_string(
        payload.get("patient_email"),
        "payload.patient_email",
    )
    _require_non_empty_string(
        payload.get("doctor_id"),
        "payload.doctor_id",
    )

    if event_type == "appointment.created":
        if set(payload) != CREATED_PAYLOAD_FIELDS:
            raise AppointmentEventError(
                "Invalid appointment.created payload fields"
            )

        if payload.get("status") != "requested":
            raise AppointmentEventError(
                "New appointments must have requested status"
            )

        _validate_timestamp(
            payload.get("scheduled_at"),
            "payload.scheduled_at",
        )

    elif event_type == "appointment.status_changed":
        if set(payload) != STATUS_CHANGED_PAYLOAD_FIELDS:
            raise AppointmentEventError(
                "Invalid appointment.status_changed payload fields"
            )

        previous_status = _require_non_empty_string(
            payload.get("previous_status"),
            "payload.previous_status",
        )
        new_status = _require_non_empty_string(
            payload.get("new_status"),
            "payload.new_status",
        )

        if (previous_status, new_status) not in SUPPORTED_TRANSITIONS:
            raise AppointmentEventError(
                "Unsupported appointment status transition"
            )

    else:
        raise AppointmentEventError(
            f"Unsupported event type: {event_type}"
        )


def create_event_processor(
    on_valid_event: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[[dict[str, Any], str], None]:
    """Create a validation-only processor with an optional local callback."""

    def process_event(
        event: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        validate_appointment_event(event, idempotency_key)

        if on_valid_event is not None:
            on_valid_event(event)

    return process_event
