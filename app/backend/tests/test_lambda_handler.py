
import importlib
import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from careflow_api.dynamodb_repositories import (
    DynamoDBProcessedEventsRepository,
)
from careflow_api.lambda_handler import create_sqs_handler


lambda_module = importlib.import_module(
    "careflow_api.lambda_handler"
)
repositories_module = importlib.import_module(
    "careflow_api.dynamodb_repositories"
)
event_processor_module = importlib.import_module(
    "careflow_api.event_processor"
)


@pytest.fixture
def processed_events_repository():
    with mock_aws():
        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-east-2",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )

        table = dynamodb.create_table(
            TableName="CareFlow-ProcessedEvents",
            KeySchema=[
                {
                    "AttributeName": "event_id",
                    "KeyType": "HASH",
                },
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "event_id",
                    "AttributeType": "S",
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        yield DynamoDBProcessedEventsRepository(table)


@pytest.fixture
def fixed_clock():
    return lambda: datetime(
        2026,
        11,
        12,
        10,
        0,
        0,
        tzinfo=timezone.utc,
    )


def make_event(event_id="event-001"):
    return {
        "event_id": event_id,
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-001",
        "created_at": "2026-11-12T09:55:00+00:00",
        "payload": {
            "appointment_id": "appointment-001",
            "status": "requested",
        },
    }


def make_record(event=None, message_id="sqs-message-001", body=None):
    if body is None:
        body = json.dumps(event or make_event())

    return {
        "messageId": message_id,
        "body": body,
    }


def make_handler(repository, processor, clock):
    return create_sqs_handler(
        processed_events_repository=repository,
        processor=processor,
        lease_seconds=300,
        clock=clock,
        worker_id_factory=lambda: "lambda-worker-001",
    )


# ---------------------------------------------------------
# Existing SQS handler tests
# ---------------------------------------------------------


def test_successful_event_is_marked_processed(
    processed_events_repository,
    fixed_clock,
):
    processed = []

    def processor(event, idempotency_key):
        processed.append((event, idempotency_key))

    handler = make_handler(
        processed_events_repository,
        processor,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {"batchItemFailures": []}
    assert len(processed) == 1
    assert processed[0][1] == "event-001"

    stored = processed_events_repository.get_by_id("event-001")

    assert stored["status"] == "processed"
    assert stored["lease_owner"] is None if "lease_owner" in stored else True
    assert stored["processed_at"] == "2026-11-12T10:00:00+00:00"
    assert "lease_owner" not in stored


def test_already_processed_event_is_skipped(
    processed_events_repository,
    fixed_clock,
):
    processed_events_repository.claim_event(
        event_id="event-001",
        lease_owner="previous-worker",
        lease_expires_at="2026-11-12T10:05:00+00:00",
        now="2026-11-12T09:59:00+00:00",
    )
    processed_events_repository.mark_processed(
        event_id="event-001",
        lease_owner="previous-worker",
        processed_at="2026-11-12T09:59:30+00:00",
    )

    processor_calls = []

    handler = make_handler(
        processed_events_repository,
        lambda event, key: processor_calls.append(key),
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {"batchItemFailures": []}
    assert processor_calls == []


def test_active_processing_lease_causes_retry(
    processed_events_repository,
    fixed_clock,
):
    processed_events_repository.claim_event(
        event_id="event-001",
        lease_owner="another-worker",
        lease_expires_at="2026-11-12T10:05:00+00:00",
        now="2026-11-12T09:59:00+00:00",
    )

    processor_calls = []

    handler = make_handler(
        processed_events_repository,
        lambda event, key: processor_calls.append(key),
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "sqs-message-001"},
        ],
    }
    assert processor_calls == []


def test_expired_lease_is_reclaimed(
    processed_events_repository,
    fixed_clock,
):
    processed_events_repository.claim_event(
        event_id="event-001",
        lease_owner="expired-worker",
        lease_expires_at="2026-11-12T09:59:00+00:00",
        now="2026-11-12T09:55:00+00:00",
    )

    processor_calls = []

    handler = make_handler(
        processed_events_repository,
        lambda event, key: processor_calls.append(key),
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {"batchItemFailures": []}
    assert processor_calls == ["event-001"]

    stored = processed_events_repository.get_by_id("event-001")

    assert stored["status"] == "processed"
    assert stored["attempts"] == 2


def test_processor_failure_releases_claim_and_requests_retry(
    processed_events_repository,
    fixed_clock,
):
    def failing_processor(event, idempotency_key):
        raise RuntimeError("Simulated processing failure")

    handler = make_handler(
        processed_events_repository,
        failing_processor,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "sqs-message-001"},
        ],
    }

    stored = processed_events_repository.get_by_id("event-001")

    assert stored["status"] == "pending"
    assert "lease_owner" not in stored
    assert "lease_expires_at" not in stored


def test_malformed_message_requests_retry(
    processed_events_repository,
    fixed_clock,
):
    handler = make_handler(
        processed_events_repository,
        lambda event, key: None,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(
                message_id="malformed-message",
                body="{not-valid-json",
            ),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "malformed-message"},
        ],
    }


def test_batch_returns_only_failed_message_ids(
    processed_events_repository,
    fixed_clock,
):
    def processor(event, idempotency_key):
        if idempotency_key == "event-fails":
            raise RuntimeError("Simulated failure")

    successful_event = make_event("event-succeeds")
    failing_event = make_event("event-fails")

    handler = make_handler(
        processed_events_repository,
        processor,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(
                successful_event,
                message_id="message-success",
            ),
            make_record(
                failing_event,
                message_id="message-failure",
            ),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "message-failure"},
        ],
    }

    assert (
        processed_events_repository.get_by_id("event-succeeds")["status"]
        == "processed"
    )
    assert (
        processed_events_repository.get_by_id("event-fails")["status"]
        == "pending"
    )


def test_lost_lease_after_processing_requests_retry(
    processed_events_repository,
    fixed_clock,
):
    class RepositoryWithFailedMark:
        def claim_event(self, **kwargs):
            return processed_events_repository.claim_event(**kwargs)

        def get_by_id(self, event_id):
            return processed_events_repository.get_by_id(event_id)

        def release_claim(self, **kwargs):
            return processed_events_repository.release_claim(**kwargs)

        def mark_processed(self, **kwargs):
            return None

    handler = make_handler(
        RepositoryWithFailedMark(),
        lambda event, key: None,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "sqs-message-001"},
        ],
    }


def test_invalid_lease_duration_is_rejected(
    processed_events_repository,
):
    with pytest.raises(ValueError):
        create_sqs_handler(
            processed_events_repository=processed_events_repository,
            processor=lambda event, key: None,
            lease_seconds=0,
        )


def test_missing_event_field_requests_retry(
    processed_events_repository,
    fixed_clock,
):
    invalid_event = make_event()
    del invalid_event["aggregate_id"]

    handler = make_handler(
        processed_events_repository,
        lambda event, key: None,
        fixed_clock,
    )

    response = handler({
        "Records": [
            make_record(
                invalid_event,
                message_id="missing-field-message",
            ),
        ],
    })

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "missing-field-message"},
        ],
    }


# ---------------------------------------------------------
# Runtime test helpers
# ---------------------------------------------------------


@pytest.fixture
def reset_lambda_runtime_handler():
    """Reset the cached Lambda runtime handler between tests."""

    lambda_module._runtime_handler = None

    yield

    lambda_module._runtime_handler = None


def make_runtime_event(
    event_id="runtime-event-001",
    appointment_id="runtime-appointment-001",
):
    """Build a valid appointment.created event for runtime tests."""

    return {
        "event_id": event_id,
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": appointment_id,
        "created_at": "2026-11-12T09:55:00+00:00",
        "payload": {
            "appointment_id": appointment_id,
            "patient_email": "patient@example.local",
            "doctor_id": "doctor-001",
            "scheduled_at": "2026-11-15T10:00:00+00:00",
            "status": "requested",
        },
    }


class FakeRuntimeRepository:
    """Minimal repository for mocked Lambda runtime tests."""

    def __init__(self, table):
        self.table = table
        self.claimed_events = []
        self.processed_events = []

    def claim_event(self, **kwargs):
        self.claimed_events.append(kwargs)
        return {"event_id": kwargs["event_id"]}

    def get_by_id(self, event_id):
        return None

    def release_claim(self, **kwargs):
        return {"event_id": kwargs["event_id"]}

    def mark_processed(self, **kwargs):
        self.processed_events.append(kwargs)
        return {
            "event_id": kwargs["event_id"],
            "status": "processed",
        }


# ---------------------------------------------------------
# Lambda runtime initialization tests
# ---------------------------------------------------------


def test_runtime_requires_processed_events_table_configuration(
    monkeypatch,
    reset_lambda_runtime_handler,
):
    """Runtime must fail clearly when its table is not configured."""

    monkeypatch.delenv(
        "CARE_FLOW_PROCESSED_EVENTS_TABLE",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="CARE_FLOW_PROCESSED_EVENTS_TABLE",
    ):
        lambda_module.lambda_handler({}, None)

    assert lambda_module._runtime_handler is None


def test_runtime_initializes_repository_and_event_processor(
    monkeypatch,
    reset_lambda_runtime_handler,
):
    """Runtime should connect the configured table and real processor."""

    monkeypatch.setenv(
        "CARE_FLOW_PROCESSED_EVENTS_TABLE",
        "CareFlow-ProcessedEvents",
    )
    monkeypatch.setenv("AWS_REGION", "us-west-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")

    resource_calls = []
    repository_instances = []
    processor_factory_calls = []

    table = object()

    class FakeDynamoDB:
        def Table(self, table_name):
            assert table_name == "CareFlow-ProcessedEvents"
            return table

    def fake_resource(service_name, **kwargs):
        resource_calls.append((service_name, kwargs))
        return FakeDynamoDB()

    def fake_repository_factory(received_table):
        repository = FakeRuntimeRepository(received_table)
        repository_instances.append(repository)
        return repository

    real_processor_factory = (
        event_processor_module.create_event_processor
    )

    def fake_processor_factory(*args, **kwargs):
        processor_factory_calls.append((args, kwargs))
        return real_processor_factory(*args, **kwargs)

    monkeypatch.setattr(
        boto3,
        "resource",
        fake_resource,
    )

    monkeypatch.setattr(
        repositories_module,
        "DynamoDBProcessedEventsRepository",
        fake_repository_factory,
    )

    monkeypatch.setattr(
        event_processor_module,
        "create_event_processor",
        fake_processor_factory,
    )

    response = lambda_module.lambda_handler(
        {
            "Records": [
                make_record(
                    make_runtime_event(),
                    message_id="runtime-message-001",
                ),
            ],
        },
        None,
    )

    assert response == {"batchItemFailures": []}

    assert resource_calls == [
        (
            "dynamodb",
            {"region_name": "us-west-1"},
        ),
    ]

    assert len(repository_instances) == 1
    assert repository_instances[0].table is table

    assert len(processor_factory_calls) == 1

    assert repository_instances[0].claimed_events[0]["event_id"] == (
        "runtime-event-001"
    )

    assert repository_instances[0].processed_events[0]["event_id"] == (
        "runtime-event-001"
    )


def test_runtime_handler_is_cached_between_invocations(
    monkeypatch,
    reset_lambda_runtime_handler,
):
    """Repeated invocations should reuse runtime dependencies."""

    monkeypatch.setenv(
        "CARE_FLOW_PROCESSED_EVENTS_TABLE",
        "CareFlow-ProcessedEvents",
    )
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    resource_calls = []
    repository_instances = []

    table = object()

    class FakeDynamoDB:
        def Table(self, table_name):
            return table

    def fake_resource(service_name, **kwargs):
        resource_calls.append((service_name, kwargs))
        return FakeDynamoDB()

    def fake_repository_factory(received_table):
        repository = FakeRuntimeRepository(received_table)
        repository_instances.append(repository)
        return repository

    monkeypatch.setattr(
        boto3,
        "resource",
        fake_resource,
    )

    monkeypatch.setattr(
        repositories_module,
        "DynamoDBProcessedEventsRepository",
        fake_repository_factory,
    )

    first_response = lambda_module.lambda_handler(
        {
            "Records": [
                make_record(
                    make_runtime_event(
                        "runtime-event-001",
                        "runtime-appointment-001",
                    ),
                    message_id="runtime-message-001",
                ),
            ],
        },
        None,
    )

    second_response = lambda_module.lambda_handler(
        {
            "Records": [
                make_record(
                    make_runtime_event(
                        "runtime-event-002",
                        "runtime-appointment-002",
                    ),
                    message_id="runtime-message-002",
                ),
            ],
        },
        None,
    )

    assert first_response == {"batchItemFailures": []}
    assert second_response == {"batchItemFailures": []}

    # The default region should be us-east-2.
    assert resource_calls == [
        (
            "dynamodb",
            {"region_name": "us-east-2"},
        ),
    ]

    # Only one repository should be constructed.
    assert len(repository_instances) == 1

    # Both invocations should use that same repository.
    assert len(repository_instances[0].claimed_events) == 2
    assert len(repository_instances[0].processed_events) == 2

    assert lambda_module._runtime_handler is not None
