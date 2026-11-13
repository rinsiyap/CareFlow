
import boto3
import pytest

from moto import mock_aws

from careflow_api.dynamodb_tables import create_dynamodb_tables
from careflow_api.dynamodb_repositories import (
    DynamoDBOutboxRepository,
)


@pytest.fixture
def outbox_repository():
    with mock_aws():
        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-east-2",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )

        tables = create_dynamodb_tables(dynamodb)

        yield DynamoDBOutboxRepository(tables["outbox"])


@pytest.fixture
def sample_event():
    return {
        "event_id": "event-001",
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-001",
        "status": "pending",
        "created_at": "2026-11-11T10:00:00+00:00",
        "payload": {
            "appointment_id": "appointment-001",
            "patient_email": "patient@example.com",
            "doctor_id": "doctor-001",
            "appointment_status": "requested",
        },
    }


def test_create_and_get_outbox_event(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    created = repository.create_event(sample_event)

    assert created == sample_event

    retrieved = repository.get_by_id("event-001")

    assert retrieved == sample_event


def test_get_missing_event_returns_none(outbox_repository):
    assert outbox_repository.get_by_id("missing-event") is None


def test_duplicate_event_is_rejected(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    repository.create_event(sample_event)

    with pytest.raises(
        ValueError,
        match="Outbox event already exists",
    ):
        repository.create_event(sample_event)


def test_event_requires_required_fields(outbox_repository):
    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        outbox_repository.create_event(
            {
                "event_id": "event-invalid",
                "status": "pending",
            }
        )


def test_new_event_must_be_pending(outbox_repository):
    with pytest.raises(
        ValueError,
        match="status='pending'",
    ):
        outbox_repository.create_event(
            {
                "event_id": "event-invalid",
                "status": "delivered",
                "created_at": "2026-11-11T10:00:00+00:00",
            }
        )


def test_list_pending_returns_events_in_creation_order(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    first_event = {
        **sample_event,
        "event_id": "event-001",
        "created_at": "2026-11-11T09:00:00+00:00",
    }

    second_event = {
        **sample_event,
        "event_id": "event-002",
        "created_at": "2026-11-11T10:00:00+00:00",
    }

    third_event = {
        **sample_event,
        "event_id": "event-003",
        "created_at": "2026-11-11T11:00:00+00:00",
    }

    # Deliberately insert in a different order.
    repository.create_event(second_event)
    repository.create_event(third_event)
    repository.create_event(first_event)

    pending = repository.list_pending()

    assert [
        event["event_id"] for event in pending
    ] == [
        "event-001",
        "event-002",
        "event-003",
    ]


def test_list_pending_respects_limit(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    for number in range(1, 4):
        repository.create_event(
            {
                **sample_event,
                "event_id": f"event-{number:03d}",
                "created_at": (
                    f"2026-11-11T{number:02d}:00:00+00:00"
                ),
            }
        )

    pending = repository.list_pending(limit=2)

    assert len(pending) == 2

    assert [
        event["event_id"] for event in pending
    ] == [
        "event-001",
        "event-002",
    ]


def test_list_pending_rejects_invalid_limit(outbox_repository):
    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        outbox_repository.list_pending(limit=0)


def test_mark_pending_event_as_delivered(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    repository.create_event(sample_event)

    delivered = repository.mark_delivered(
        event_id="event-001",
        delivered_at="2026-11-11T10:05:00+00:00",
    )

    assert delivered is not None
    assert delivered["status"] == "delivered"
    assert delivered["delivered_at"] == (
        "2026-11-11T10:05:00+00:00"
    )

    stored = repository.get_by_id("event-001")

    assert stored["status"] == "delivered"


def test_delivered_event_is_not_returned_as_pending(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    repository.create_event(sample_event)

    repository.mark_delivered(
        event_id="event-001",
        delivered_at="2026-11-11T10:05:00+00:00",
    )

    assert repository.list_pending() == []


def test_event_cannot_be_marked_delivered_twice(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    repository.create_event(sample_event)

    first_update = repository.mark_delivered(
        "event-001",
        "2026-11-11T10:05:00+00:00",
    )

    second_update = repository.mark_delivered(
        "event-001",
        "2026-11-11T10:06:00+00:00",
    )

    assert first_update is not None
    assert second_update is None


def test_missing_event_cannot_be_marked_delivered(
    outbox_repository,
):
    result = outbox_repository.mark_delivered(
        "missing-event",
        "2026-11-11T10:05:00+00:00",
    )

    assert result is None


def test_claim_pending_event(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    claimed = repository.claim_event(
        event_id="event-001",
        lease_owner="worker-001",
        lease_expires_at="2026-11-11T10:06:00+00:00",
        now="2026-11-11T10:05:00+00:00",
    )

    assert claimed is not None
    assert claimed["status"] == "processing"
    assert claimed["lease_owner"] == "worker-001"
    assert claimed["lease_expires_at"] == (
        "2026-11-11T10:06:00+00:00"
    )
    assert claimed["attempts"] == 1


def test_second_worker_cannot_claim_active_lease(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    first_claim = repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    second_claim = repository.claim_event(
        "event-001",
        "worker-002",
        "2026-11-11T10:07:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    assert first_claim is not None
    assert second_claim is None

    stored = repository.get_by_id("event-001")
    assert stored["lease_owner"] == "worker-001"
    assert stored["attempts"] == 1


def test_expired_lease_can_be_claimed_by_another_worker(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    reclaimed = repository.claim_event(
        "event-001",
        "worker-002",
        "2026-11-11T10:08:00+00:00",
        "2026-11-11T10:06:00+00:00",
    )

    assert reclaimed is not None
    assert reclaimed["status"] == "processing"
    assert reclaimed["lease_owner"] == "worker-002"
    assert reclaimed["attempts"] == 2


def test_release_claim_returns_event_to_pending(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    released = repository.release_claim(
        "event-001",
        "worker-001",
    )

    assert released is not None
    assert released["status"] == "pending"
    assert "lease_owner" not in released
    assert "lease_expires_at" not in released

    stored = repository.get_by_id("event-001")
    assert stored["status"] == "pending"


def test_wrong_worker_cannot_release_claim(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    released = repository.release_claim(
        "event-001",
        "worker-002",
    )

    assert released is None

    stored = repository.get_by_id("event-001")
    assert stored["status"] == "processing"
    assert stored["lease_owner"] == "worker-001"


def test_claimed_event_can_be_marked_delivered(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    delivered = repository.mark_claimed_delivered(
        "event-001",
        "worker-001",
        "2026-11-11T10:05:30+00:00",
    )

    assert delivered is not None
    assert delivered["status"] == "delivered"
    assert delivered["delivered_at"] == (
        "2026-11-11T10:05:30+00:00"
    )
    assert "lease_owner" not in delivered
    assert "lease_expires_at" not in delivered


def test_wrong_worker_cannot_mark_event_delivered(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:06:00+00:00",
        "2026-11-11T10:05:00+00:00",
    )

    delivered = repository.mark_claimed_delivered(
        "event-001",
        "worker-002",
        "2026-11-11T10:05:30+00:00",
    )

    assert delivered is None

    stored = repository.get_by_id("event-001")
    assert stored["status"] == "processing"
    assert stored["lease_owner"] == "worker-001"


def test_list_expired_processing_events(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository

    repository.create_event({
        **sample_event,
        "event_id": "event-001",
    })
    repository.create_event({
        **sample_event,
        "event_id": "event-002",
        "created_at": "2026-11-11T10:01:00+00:00",
    })

    repository.claim_event(
        "event-001",
        "worker-001",
        "2026-11-11T10:04:00+00:00",
        "2026-11-11T10:00:00+00:00",
    )

    repository.claim_event(
        "event-002",
        "worker-002",
        "2026-11-11T10:08:00+00:00",
        "2026-11-11T10:01:00+00:00",
    )

    expired = repository.list_expired_processing(
        now="2026-11-11T10:05:00+00:00",
    )

    assert [
        event["event_id"] for event in expired
    ] == ["event-001"]


def test_list_expired_processing_rejects_invalid_limit(
    outbox_repository,
):
    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        outbox_repository.list_expired_processing(
            now="2026-11-11T10:05:00+00:00",
            limit=0,
        )


def test_claim_rejects_empty_worker_id(
    outbox_repository,
    sample_event,
):
    repository = outbox_repository
    repository.create_event(sample_event)

    with pytest.raises(
        ValueError,
        match="lease_owner must not be empty",
    ):
        repository.claim_event(
            "event-001",
            " ",
            "2026-11-11T10:06:00+00:00",
            "2026-11-11T10:05:00+00:00",
        )
