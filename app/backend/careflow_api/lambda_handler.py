
"""
CareFlow SQS Lambda consumer.

The handler:
- Validates SQS event messages.
- Claims event IDs using the processed-events repository.
- Skips events already marked as processed.
- Retries events with an active processing lease.
- Validates appointment events before processing.
- Releases claims when processing fails.
- Returns partial batch failures for SQS retries.

This module connects directly to an existing DynamoDB table.
It never creates DynamoDB tables.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


REQUIRED_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "created_at",
    "payload",
)


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    """Convert a datetime to a timezone-aware UTC ISO timestamp."""

    if not isinstance(value, datetime):
        raise TypeError("The clock must return a datetime.")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


def _new_worker_id() -> str:
    """Generate a unique worker ID."""

    return f"careflow-lambda-{uuid.uuid4().hex}"


def _parse_event_body(body: Any) -> dict[str, Any]:
    """Parse and validate the event envelope sent by the outbox dispatcher."""

    if not isinstance(body, str):
        raise ValueError("SQS message body must be a JSON string.")

    try:
        event = json.loads(body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("SQS message body is not valid JSON.") from exc

    if not isinstance(event, dict):
        raise ValueError("SQS message body must contain a JSON object.")

    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            raise ValueError(f"Event is missing required field: {field}")

    for field in REQUIRED_EVENT_FIELDS[:-1]:
        value = event[field]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Event field {field} must be a non-empty string."
            )

    if not isinstance(event["payload"], dict):
        raise ValueError("Event payload must be a JSON object.")

    return event


def create_sqs_handler(
    processed_events_repository: Any,
    processor: Callable[[dict[str, Any], str], None],
    lease_seconds: int = 300,
    clock: Callable[[], datetime] = _utc_now,
    worker_id_factory: Callable[[], str] = _new_worker_id,
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """
    Build a testable SQS Lambda handler.

    The processor receives:
        event: The validated event envelope.
        idempotency_key: The event_id, which downstream actions must use
                         to prevent duplicate external side effects.
    """

    if processed_events_repository is None:
        raise ValueError("A processed-events repository is required.")

    if not callable(processor):
        raise TypeError("processor must be callable.")

    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
        raise TypeError("lease_seconds must be an integer.")

    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be greater than zero.")

    if not callable(clock):
        raise TypeError("clock must be callable.")

    if not callable(worker_id_factory):
        raise TypeError("worker_id_factory must be callable.")

    def handler(
        event: dict[str, Any],
        context: Any = None,
    ) -> dict[str, Any]:
        """Process one SQS batch and return failed message identifiers."""

        if not isinstance(event, dict):
            raise ValueError("Lambda event must be an object.")

        records = event.get("Records")

        if not isinstance(records, list):
            raise ValueError("Lambda event must contain a Records list.")

        worker_id = worker_id_factory()

        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError(
                "worker_id_factory must return a non-empty string."
            )

        failures: list[dict[str, str]] = []

        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Each SQS record must be an object.")

            message_id = record.get("messageId")

            if not isinstance(message_id, str) or not message_id.strip():
                raise ValueError(
                    "Each SQS record must have a messageId."
                )

            try:
                _process_record(
                    record=record,
                    repository=processed_events_repository,
                    processor=processor,
                    worker_id=worker_id,
                    lease_seconds=lease_seconds,
                    clock=clock,
                )
            except Exception:
                # Do not log message bodies, event payloads, or patient data.
                failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": failures}

    return handler


def _process_record(
    record: dict[str, Any],
    repository: Any,
    processor: Callable[[dict[str, Any], str], None],
    worker_id: str,
    lease_seconds: int,
    clock: Callable[[], datetime],
) -> None:
    """Process one SQS record or raise to request an SQS retry."""

    event = _parse_event_body(record.get("body"))
    event_id = event["event_id"]

    now = clock()
    now_iso = _iso_utc(now)

    lease_expires_at = _iso_utc(
        now + timedelta(seconds=lease_seconds)
    )

    claim = repository.claim_event(
        event_id=event_id,
        lease_owner=worker_id,
        lease_expires_at=lease_expires_at,
        now=now_iso,
    )

    if claim is None:
        existing = repository.get_by_id(event_id)

        if existing is not None and existing.get("status") == "processed":
            # A previous delivery completed successfully.
            return

        # An active lease or an unexpected state must be retried.
        raise RuntimeError(
            f"Event {event_id!r} could not be claimed for processing."
        )

    try:
        # The processor validates the appointment event and receives
        # event_id as its idempotency key.
        processor(event, event_id)

    except Exception:
        try:
            repository.release_claim(
                event_id=event_id,
                lease_owner=worker_id,
            )
        except Exception:
            # The lease will eventually expire if release also fails.
            pass

        raise

    processed_at = _iso_utc(clock())

    marked = repository.mark_processed(
        event_id=event_id,
        lease_owner=worker_id,
        processed_at=processed_at,
    )

    if marked is None:
        # The lease may have expired or been taken over. Ask SQS to retry.
        raise RuntimeError(
            f"Event {event_id!r} could not be marked as processed."
        )


_runtime_handler: (
    Callable[[dict[str, Any], Any], dict[str, Any]] | None
) = None


def lambda_handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """
    AWS Lambda entry point.

    Connects directly to an existing DynamoDB table.
    It deliberately does not use careflow_api.storage because that module
    can create tables.
    """

    global _runtime_handler

    if _runtime_handler is None:
        import boto3

        from careflow_api.dynamodb_repositories import (
            DynamoDBProcessedEventsRepository,
        )
        from careflow_api.event_processor import create_event_processor

        table_name = os.getenv("CARE_FLOW_PROCESSED_EVENTS_TABLE")

        if not table_name:
            raise RuntimeError(
                "CARE_FLOW_PROCESSED_EVENTS_TABLE must identify an "
                "existing DynamoDB table."
            )

        region = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-2"
        )

        dynamodb = boto3.resource(
            "dynamodb",
            region_name=region,
        )

        table = dynamodb.Table(table_name)

        repository = DynamoDBProcessedEventsRepository(table)

        processor = create_event_processor()

        _runtime_handler = create_sqs_handler(
            processed_events_repository=repository,
            processor=processor,
        )

    return _runtime_handler(event, context)
