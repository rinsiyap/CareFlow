
import boto3
import pytest

from moto import mock_aws

from careflow_api.dynamodb_repositories import (
    DynamoDBProcessedEventsRepository,
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
def claim_values():
    return {
        "event_id": "event-001",
        "lease_owner": "lambda-worker-001",
        "lease_expires_at": "2026-11-12T10:05:00+00:00",
        "now": "2026-11-12T10:00:00+00:00",
    }


def test_claim_new_event(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    claimed = repository.claim_event(**claim_values)

    assert claimed is not None
    assert claimed["event_id"] == "event-001"
    assert claimed["status"] == "processing"
    assert claimed["lease_owner"] == "lambda-worker-001"
    assert claimed["lease_expires_at"] == (
        "2026-11-12T10:05:00+00:00"
    )
    assert claimed["attempts"] == 1


def test_get_by_id_returns_claimed_event(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    event = repository.get_by_id("event-001")

    assert event is not None
    assert event["event_id"] == "event-001"
    assert event["status"] == "processing"


def test_get_by_id_returns_none_for_missing_event(
    processed_events_repository,
):
    assert (
        processed_events_repository.get_by_id("missing-event")
        is None
    )


def test_active_lease_cannot_be_claimed_by_another_worker(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    second_claim = repository.claim_event(
        event_id="event-001",
        lease_owner="lambda-worker-002",
        lease_expires_at="2026-11-12T10:10:00+00:00",
        now="2026-11-12T10:02:00+00:00",
    )

    assert second_claim is None

    stored = repository.get_by_id("event-001")

    assert stored["lease_owner"] == "lambda-worker-001"
    assert stored["attempts"] == 1


def test_expired_lease_can_be_reclaimed(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    reclaimed = repository.claim_event(
        event_id="event-001",
        lease_owner="lambda-worker-002",
        lease_expires_at="2026-11-12T10:12:00+00:00",
        now="2026-11-12T10:05:00+00:00",
    )

    assert reclaimed is not None
    assert reclaimed["status"] == "processing"
    assert reclaimed["lease_owner"] == "lambda-worker-002"
    assert reclaimed["attempts"] == 2


def test_release_claim_returns_event_to_pending(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    released = repository.release_claim(
        "event-001",
        "lambda-worker-001",
    )

    assert released is not None
    assert released["status"] == "pending"
    assert "lease_owner" not in released
    assert "lease_expires_at" not in released

    stored = repository.get_by_id("event-001")

    assert stored["status"] == "pending"


def test_wrong_worker_cannot_release_claim(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    released = repository.release_claim(
        "event-001",
        "lambda-worker-002",
    )

    assert released is None

    stored = repository.get_by_id("event-001")

    assert stored["status"] == "processing"
    assert stored["lease_owner"] == "lambda-worker-001"


def test_claim_can_be_reacquired_after_release(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    repository.release_claim(
        "event-001",
        "lambda-worker-001",
    )

    reclaimed = repository.claim_event(
        event_id="event-001",
        lease_owner="lambda-worker-002",
        lease_expires_at="2026-11-12T10:10:00+00:00",
        now="2026-11-12T10:02:00+00:00",
    )

    assert reclaimed is not None
    assert reclaimed["lease_owner"] == "lambda-worker-002"
    assert reclaimed["attempts"] == 2


def test_mark_claimed_event_processed(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    processed = repository.mark_processed(
        "event-001",
        "lambda-worker-001",
        "2026-11-12T10:01:00+00:00",
    )

    assert processed is not None
    assert processed["status"] == "processed"
    assert processed["processed_at"] == (
        "2026-11-12T10:01:00+00:00"
    )
    assert "lease_owner" not in processed
    assert "lease_expires_at" not in processed


def test_wrong_worker_cannot_mark_event_processed(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    processed = repository.mark_processed(
        "event-001",
        "lambda-worker-002",
        "2026-11-12T10:01:00+00:00",
    )

    assert processed is None

    stored = repository.get_by_id("event-001")

    assert stored["status"] == "processing"
    assert stored["lease_owner"] == "lambda-worker-001"


def test_processed_event_cannot_be_claimed_again(
    processed_events_repository,
    claim_values,
):
    repository = processed_events_repository

    repository.claim_event(**claim_values)

    repository.mark_processed(
        "event-001",
        "lambda-worker-001",
        "2026-11-12T10:01:00+00:00",
    )

    duplicate_claim = repository.claim_event(
        event_id="event-001",
        lease_owner="lambda-worker-002",
        lease_expires_at="2026-11-12T10:10:00+00:00",
        now="2026-11-12T10:06:00+00:00",
    )

    assert duplicate_claim is None

    stored = repository.get_by_id("event-001")

    assert stored["status"] == "processed"


def test_claim_rejects_empty_event_id(
    processed_events_repository,
    claim_values,
):
    values = {
        **claim_values,
        "event_id": " ",
    }

    with pytest.raises(ValueError, match="event_id must not be empty"):
        processed_events_repository.claim_event(**values)


def test_claim_rejects_empty_worker_id(
    processed_events_repository,
    claim_values,
):
    values = {
        **claim_values,
        "lease_owner": " ",
    }

    with pytest.raises(
        ValueError,
        match="lease_owner must not be empty",
    ):
        processed_events_repository.claim_event(**values)
