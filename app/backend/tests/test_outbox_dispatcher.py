
import json
from datetime import datetime, timezone

import pytest

from careflow_api.outbox_dispatcher import OutboxDispatcher


QUEUE_URL = "http://localhost:4566/000000000000/careflow-events"

FIXED_NOW = "2026-11-11T10:05:00+00:00"


def make_event(event_id: str, status: str = "pending") -> dict:
    return {
        "event_id": event_id,
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": f"appointment-{event_id}",
        "status": status,
        "created_at": "2026-11-11T10:00:00+00:00",
        "payload": {
            "appointment_id": f"appointment-{event_id}",
            "patient_email": "patient@example.com",
            "doctor_id": "doctor-001",
            "appointment_status": "requested",
        },
    }


class FakeOutboxRepository:
    """In-memory repository implementing the outbox lease interface."""

    def __init__(self, events):
        self.events = [event.copy() for event in events]
        self.marked = []

    def list_pending(self, limit=100):
        return [
            event.copy()
            for event in self.events
            if event["status"] == "pending"
        ][:limit]

    def list_expired_processing(self, now, limit=100):
        return [
            event.copy()
            for event in self.events
            if (
                event["status"] == "processing"
                and event.get("lease_expires_at", "") <= now
            )
        ][:limit]

    def claim_event(
        self,
        event_id,
        lease_owner,
        lease_expires_at,
        now,
    ):
        for event in self.events:
            if event["event_id"] != event_id:
                continue

            is_pending = event["status"] == "pending"

            is_expired = (
                event["status"] == "processing"
                and event.get("lease_expires_at", "") <= now
            )

            if not (is_pending or is_expired):
                return None

            event["status"] = "processing"
            event["lease_owner"] = lease_owner
            event["lease_expires_at"] = lease_expires_at
            event["attempts"] = event.get("attempts", 0) + 1

            return event.copy()

        return None

    def release_claim(self, event_id, lease_owner):
        for event in self.events:
            if (
                event["event_id"] == event_id
                and event["status"] == "processing"
                and event.get("lease_owner") == lease_owner
            ):
                event["status"] = "pending"
                event.pop("lease_owner", None)
                event.pop("lease_expires_at", None)
                return event.copy()

        return None

    def mark_claimed_delivered(
        self,
        event_id,
        lease_owner,
        delivered_at,
    ):
        for event in self.events:
            if (
                event["event_id"] == event_id
                and event["status"] == "processing"
                and event.get("lease_owner") == lease_owner
            ):
                event["status"] = "delivered"
                event["delivered_at"] = delivered_at
                event.pop("lease_owner", None)
                event.pop("lease_expires_at", None)

                self.marked.append(event_id)

                return event.copy()

        return None


class FakeSQSClient:
    def __init__(self, failing_event_ids=None):
        self.messages = []
        self.failing_event_ids = set(failing_event_ids or [])

    def send_message(
        self,
        QueueUrl,
        MessageBody,
        MessageAttributes,
    ):
        event = json.loads(MessageBody)
        event_id = event["event_id"]

        if event_id in self.failing_event_ids:
            raise RuntimeError("Simulated SQS failure")

        self.messages.append(
            {
                "QueueUrl": QueueUrl,
                "MessageBody": MessageBody,
                "MessageAttributes": MessageAttributes,
            }
        )

        return {"MessageId": f"message-{event_id}"}


@pytest.fixture
def fixed_clock():
    return lambda: datetime(
        2026,
        11,
        11,
        10,
        5,
        tzinfo=timezone.utc,
    )


def make_dispatcher(repository, sqs, fixed_clock, **kwargs):
    kwargs.setdefault("worker_id", "worker-001")

    return OutboxDispatcher(
        repository,
        sqs,
        QUEUE_URL,
        clock=fixed_clock,
        **kwargs,
    )


def test_dispatch_publishes_and_marks_event_delivered(fixed_clock):
    repository = FakeOutboxRepository([make_event("event-001")])
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.events_found == 1
    assert report.messages_sent == 1
    assert report.events_marked_delivered == 1
    assert report.events_already_updated == 0
    assert report.failures == []

    event = repository.events[0]

    assert event["status"] == "delivered"
    assert event["delivered_at"] == FIXED_NOW
    assert "lease_owner" not in event
    assert "lease_expires_at" not in event

    assert len(sqs.messages) == 1
    assert sqs.messages[0]["QueueUrl"] == QUEUE_URL


def test_dispatch_serializes_clean_event_envelope_and_sets_message_attributes(
    fixed_clock,
):
    repository = FakeOutboxRepository([make_event("event-001")])
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    dispatcher.dispatch_pending()

    message = sqs.messages[0]
    body = json.loads(message["MessageBody"])

    assert body == {
        "event_id": "event-001",
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-event-001",
        "created_at": "2026-11-11T10:00:00+00:00",
        "payload": {
            "appointment_id": "appointment-event-001",
            "patient_email": "patient@example.com",
            "doctor_id": "doctor-001",
            "appointment_status": "requested",
        },
    }

    assert "status" not in body
    assert "lease_owner" not in body
    assert "lease_expires_at" not in body
    assert "attempts" not in body

    assert message["MessageAttributes"]["event_id"] == {
        "DataType": "String",
        "StringValue": "event-001",
    }

    assert message["MessageAttributes"]["event_type"] == {
        "DataType": "String",
        "StringValue": "appointment.created",
    }


def test_sqs_failure_releases_claim_and_leaves_event_pending(
    fixed_clock,
):
    repository = FakeOutboxRepository([make_event("event-001")])
    sqs = FakeSQSClient(failing_event_ids={"event-001"})

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.messages_sent == 0
    assert report.events_marked_delivered == 0

    event = repository.events[0]

    assert event["status"] == "pending"
    assert "lease_owner" not in event
    assert "lease_expires_at" not in event
    assert repository.marked == []

    assert len(report.failures) == 1
    assert report.failures[0]["stage"] == "send"


def test_dispatch_continues_after_one_event_fails(fixed_clock):
    repository = FakeOutboxRepository(
        [
            make_event("event-001"),
            make_event("event-002"),
        ]
    )
    sqs = FakeSQSClient(failing_event_ids={"event-001"})

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.events_found == 2
    assert report.messages_sent == 1
    assert report.events_marked_delivered == 1

    assert repository.events[0]["status"] == "pending"
    assert repository.events[1]["status"] == "delivered"

    assert len(report.failures) == 1
    assert report.failures[0]["event_id"] == "event-001"


def test_dispatch_respects_limit(fixed_clock):
    repository = FakeOutboxRepository(
        [
            make_event("event-001"),
            make_event("event-002"),
            make_event("event-003"),
        ]
    )
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending(limit=2)

    assert report.events_found == 2
    assert report.messages_sent == 2
    assert len(sqs.messages) == 2


def test_event_claimed_by_another_worker_is_skipped(fixed_clock):
    class ConcurrentUpdateRepository(FakeOutboxRepository):
        def claim_event(
            self,
            event_id,
            lease_owner,
            lease_expires_at,
            now,
        ):
            return None

    repository = ConcurrentUpdateRepository(
        [make_event("event-001")]
    )
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.events_found == 1
    assert report.messages_sent == 0
    assert report.events_marked_delivered == 0
    assert report.events_already_updated == 1
    assert sqs.messages == []


def test_expired_processing_event_is_reclaimed_and_published(
    fixed_clock,
):
    event = make_event("event-001", status="processing")
    event["lease_owner"] = "old-worker"
    event["lease_expires_at"] = "2026-11-11T10:00:00+00:00"
    event["attempts"] = 1

    repository = FakeOutboxRepository([event])
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.events_found == 1
    assert report.messages_sent == 1
    assert report.events_marked_delivered == 1

    assert repository.events[0]["status"] == "delivered"
    assert repository.events[0]["attempts"] == 2
    assert repository.events[0]["delivered_at"] == FIXED_NOW


def test_active_processing_event_is_not_reclaimed(fixed_clock):
    event = make_event("event-001", status="processing")
    event["lease_owner"] = "active-worker"
    event["lease_expires_at"] = "2026-11-11T10:10:00+00:00"

    repository = FakeOutboxRepository([event])
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.events_found == 0
    assert report.messages_sent == 0
    assert sqs.messages == []

    assert repository.events[0]["lease_owner"] == "active-worker"


def test_two_dispatchers_do_not_both_publish_same_event(fixed_clock):
    repository = FakeOutboxRepository([make_event("event-001")])

    first_sqs = FakeSQSClient()
    second_sqs = FakeSQSClient()

    first_dispatcher = make_dispatcher(
        repository,
        first_sqs,
        fixed_clock,
        worker_id="worker-001",
    )

    second_dispatcher = make_dispatcher(
        repository,
        second_sqs,
        fixed_clock,
        worker_id="worker-002",
    )

    first_report = first_dispatcher.dispatch_pending()
    second_report = second_dispatcher.dispatch_pending()

    assert first_report.messages_sent == 1
    assert first_report.events_marked_delivered == 1

    assert second_report.messages_sent == 0
    assert len(first_sqs.messages) + len(second_sqs.messages) == 1


def test_mark_failure_leaves_lease_for_expiry_retry(fixed_clock):
    class MarkFailureRepository(FakeOutboxRepository):
        def mark_claimed_delivered(
            self,
            event_id,
            lease_owner,
            delivered_at,
        ):
            raise RuntimeError("Simulated DynamoDB failure")

    repository = MarkFailureRepository([make_event("event-001")])
    sqs = FakeSQSClient()

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.messages_sent == 1
    assert report.events_marked_delivered == 0
    assert len(sqs.messages) == 1

    event = repository.events[0]

    assert event["status"] == "processing"
    assert event["lease_owner"] == "worker-001"
    assert "lease_expires_at" in event

    assert len(report.failures) == 1
    assert report.failures[0]["stage"] == "mark_delivered"


def test_release_failure_is_reported_separately(fixed_clock):
    class ReleaseFailureRepository(FakeOutboxRepository):
        def release_claim(self, event_id, lease_owner):
            raise RuntimeError("Simulated release failure")

    repository = ReleaseFailureRepository([make_event("event-001")])
    sqs = FakeSQSClient(failing_event_ids={"event-001"})

    dispatcher = make_dispatcher(repository, sqs, fixed_clock)

    report = dispatcher.dispatch_pending()

    assert report.messages_sent == 0
    assert len(report.failures) == 2

    assert report.failures[0]["stage"] == "send"
    assert report.failures[1]["stage"] == "release_claim"

    assert repository.events[0]["status"] == "processing"


def test_dispatch_rejects_invalid_limit():
    dispatcher = OutboxDispatcher(
        FakeOutboxRepository([]),
        FakeSQSClient(),
        QUEUE_URL,
    )

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        dispatcher.dispatch_pending(limit=0)


def test_dispatch_rejects_empty_queue_url():
    with pytest.raises(
        ValueError,
        match="queue_url must not be empty",
    ):
        OutboxDispatcher(
            FakeOutboxRepository([]),
            FakeSQSClient(),
            "",
        )


def test_dispatch_rejects_invalid_lease_duration():
    with pytest.raises(
        ValueError,
        match="lease_duration_seconds must be greater than zero",
    ):
        OutboxDispatcher(
            FakeOutboxRepository([]),
            FakeSQSClient(),
            QUEUE_URL,
            lease_duration_seconds=0,
        )


def test_dispatch_rejects_empty_worker_id():
    with pytest.raises(
        ValueError,
        match="worker_id must not be empty",
    ):
        OutboxDispatcher(
            FakeOutboxRepository([]),
            FakeSQSClient(),
            QUEUE_URL,
            worker_id=" ",
        )


def test_dispatch_rejects_naive_clock():
    repository = FakeOutboxRepository([])
    sqs = FakeSQSClient()

    naive_clock = lambda: datetime(2026, 11, 11, 10, 5)

    dispatcher = OutboxDispatcher(
        repository,
        sqs,
        QUEUE_URL,
        clock=naive_clock,
    )

    with pytest.raises(
        ValueError,
        match="clock must return a timezone-aware datetime",
    ):
        dispatcher.dispatch_pending()
