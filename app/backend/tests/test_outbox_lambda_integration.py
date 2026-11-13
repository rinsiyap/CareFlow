
import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from careflow_api.dynamodb_tables import create_dynamodb_tables
from careflow_api.dynamodb_repositories import (
    DynamoDBAppointmentRepository,
    DynamoDBOutboxRepository,
    DynamoDBProcessedEventsRepository,
)
from careflow_api.event_processor import create_event_processor
from careflow_api.outbox_dispatcher import OutboxDispatcher
from careflow_api.lambda_handler import create_sqs_handler


QUEUE_URL = "https://sqs.us-east-2.amazonaws.com/000000000000/careflow-events"

FIXED_NOW = datetime(
    2026,
    11,
    12,
    10,
    0,
    0,
    tzinfo=timezone.utc,
)


class FakeSQSClient:
    """Capture SQS messages without contacting AWS."""

    def __init__(self):
        self.messages = []

    def send_message(
        self,
        QueueUrl,
        MessageBody,
        MessageAttributes,
    ):
        message_id = f"message-{len(self.messages) + 1}"

        self.messages.append({
            "QueueUrl": QueueUrl,
            "MessageBody": MessageBody,
            "MessageAttributes": MessageAttributes,
            "MessageId": message_id,
        })

        return {"MessageId": message_id}


@pytest.fixture
def integration_environment():
    """Create all CareFlow DynamoDB tables using Moto."""

    with mock_aws():
        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-east-2",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )

        tables = create_dynamodb_tables(dynamodb)

        yield {
            "appointments": DynamoDBAppointmentRepository(
                tables["appointments"],
                outbox_table=tables["outbox"],
            ),
            "outbox": DynamoDBOutboxRepository(
                tables["outbox"],
            ),
            "processed_events": DynamoDBProcessedEventsRepository(
                tables["processed_events"],
            ),
        }


@pytest.fixture
def sample_appointment():
    return {
        "id": "appointment-integration-001",
        "patient_email": "patient@example.com",
        "doctor_id": "doctor-001",
        "scheduled_at": "2026-12-01T10:00:00+00:00",
        "reason": "General consultation",
        "status": "requested",
        "created_at": "2026-11-12T09:00:00+00:00",
    }


def test_appointment_outbox_dispatch_lambda_end_to_end(
    integration_environment,
    sample_appointment,
):
    appointments = integration_environment["appointments"]
    outbox = integration_environment["outbox"]
    processed_events = integration_environment["processed_events"]

    # ---------------------------------------------------------
    # 1. Create an appointment and generate its outbox event.
    # ---------------------------------------------------------

    created = appointments.create_appointment(sample_appointment)

    assert created == sample_appointment

    updated = appointments.transition_status(
        "appointment-integration-001",
        "requested",
        "confirmed",
    )

    assert updated is not None
    assert updated["status"] == "confirmed"

    pending_events = outbox.list_pending()

    assert len(pending_events) == 2

    assert {
        event["event_type"] for event in pending_events
    } == {
        "appointment.created",
        "appointment.status_changed",
    }

    # ---------------------------------------------------------
    # 2. Dispatch real outbox events to fake SQS.
    # ---------------------------------------------------------

    sqs = FakeSQSClient()

    dispatcher = OutboxDispatcher(
        outbox_repository=outbox,
        sqs_client=sqs,
        queue_url=QUEUE_URL,
        clock=lambda: FIXED_NOW,
        lease_duration_seconds=60,
        worker_id="integration-dispatcher",
    )

    report = dispatcher.dispatch_pending(limit=10)

    assert report.events_found == 2
    assert report.messages_sent == 2
    assert report.events_marked_delivered == 2
    assert report.failures == []

    assert len(sqs.messages) == 2

    # Verify that dispatched events are marked delivered.
    for message in sqs.messages:
        event = json.loads(message["MessageBody"])

        stored_event = outbox.get_by_id(event["event_id"])

        assert stored_event is not None
        assert stored_event["status"] == "delivered"

    # ---------------------------------------------------------
    # 3. Validate dispatched events independently.
    # ---------------------------------------------------------

    validation_processor = create_event_processor()

    for message in sqs.messages:
        event = json.loads(message["MessageBody"])

        validation_processor(
            event,
            event["event_id"],
        )

    # ---------------------------------------------------------
    # 4. Build the event processor and track processing calls.
    # ---------------------------------------------------------

    processed_calls = []

    processor = create_event_processor(
        on_valid_event=lambda event: processed_calls.append(
            (
                event["event_id"],
                event["event_id"],
                event["event_type"],
            )
        )
    )

    # ---------------------------------------------------------
    # 5. Create the Lambda SQS handler.
    # ---------------------------------------------------------

    handler = create_sqs_handler(
        processed_events_repository=processed_events,
        processor=processor,
        lease_seconds=300,
        clock=lambda: FIXED_NOW,
        worker_id_factory=lambda: "integration-lambda-worker",
    )

    # Convert captured SQS messages into a Lambda SQS batch.
    records = [
        {
            "messageId": message["MessageId"],
            "body": message["MessageBody"],
        }
        for message in sqs.messages
    ]

    lambda_event = {
        "Records": records,
    }

    # ---------------------------------------------------------
    # 6. Process both events through Lambda.
    # ---------------------------------------------------------

    result = handler(lambda_event, None)

    assert result == {
        "batchItemFailures": [],
    }

    assert len(processed_calls) == 2

    processed_event_ids = {
        event_id for event_id, _, _ in processed_calls
    }

    assert len(processed_event_ids) == 2

    # Verify that both events are marked processed in DynamoDB.
    for event_id in processed_event_ids:
        stored = processed_events.get_by_id(event_id)

        assert stored is not None
        assert stored["status"] == "processed"

    # ---------------------------------------------------------
    # 7. Deliver the exact same SQS batch again.
    # ---------------------------------------------------------

    duplicate_result = handler(lambda_event, None)

    assert duplicate_result == {
        "batchItemFailures": [],
    }

    # The processor must not run again for duplicate events.
    assert len(processed_calls) == 2

    # Both events must remain processed.
    for event_id in processed_event_ids:
        stored = processed_events.get_by_id(event_id)

        assert stored is not None
        assert stored["status"] == "processed"
