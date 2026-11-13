
from types import SimpleNamespace

import pytest

from careflow_api.outbox_worker import (
    dispatch_once,
    parse_batch_size,
)


class FakeOutboxRepository:
    """In-memory outbox repository with worker lease support."""

    def __init__(self, events):
        self.events = [event.copy() for event in events]
        self.delivered = []

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

                self.delivered.append(
                    (event_id, delivered_at)
                )

                return event.copy()

        return None


class FakeSQSClient:
    def __init__(self):
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": f"message-{len(self.messages)}"}


def make_event(event_id="event-1"):
    return {
        "event_id": event_id,
        "event_type": "appointment.created",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment-1",
        "status": "pending",
        "created_at": "2026-11-11T10:00:00+00:00",
        "payload": {
            "appointment_id": "appointment-1",
        },
    }


def test_parse_batch_size_defaults_to_ten():
    assert parse_batch_size(None) == 10
    assert parse_batch_size("") == 10


def test_parse_batch_size_accepts_positive_integer():
    assert parse_batch_size("5") == 5


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "abc", "1.5"],
)
def test_parse_batch_size_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_batch_size(value)


def test_dispatch_once_uses_injected_dependencies():
    outbox = FakeOutboxRepository([make_event()])
    sqs = FakeSQSClient()

    storage = SimpleNamespace(
        backend="dynamodb",
        outbox=outbox,
    )

    report = dispatch_once(
        queue_url="https://example.test/queue",
        region="us-east-2",
        batch_size=10,
        storage_instance=storage,
        sqs_client=sqs,
    )

    assert report.events_found == 1
    assert report.messages_sent == 1
    assert report.events_marked_delivered == 1
    assert report.failures == []

    assert len(sqs.messages) == 1
    assert sqs.messages[0]["QueueUrl"] == (
        "https://example.test/queue"
    )

    assert outbox.delivered[0][0] == "event-1"
    assert outbox.events[0]["status"] == "delivered"


def test_dispatch_once_respects_batch_size():
    events = [
        make_event("event-1"),
        make_event("event-2"),
        make_event("event-3"),
    ]

    outbox = FakeOutboxRepository(events)
    sqs = FakeSQSClient()

    storage = SimpleNamespace(
        backend="dynamodb",
        outbox=outbox,
    )

    report = dispatch_once(
        queue_url="https://example.test/queue",
        region="us-east-2",
        batch_size=2,
        storage_instance=storage,
        sqs_client=sqs,
    )

    assert report.events_found == 2
    assert report.messages_sent == 2
    assert report.events_marked_delivered == 2
    assert len(sqs.messages) == 2

    delivered_events = [
        event
        for event in outbox.events
        if event["status"] == "delivered"
    ]

    pending_events = [
        event
        for event in outbox.events
        if event["status"] == "pending"
    ]

    assert len(delivered_events) == 2
    assert len(pending_events) == 1


def test_dispatch_once_rejects_memory_backend():
    storage = SimpleNamespace(
        backend="memory",
        outbox=None,
    )

    with pytest.raises(RuntimeError, match="requires"):
        dispatch_once(
            queue_url="https://example.test/queue",
            region="us-east-2",
            storage_instance=storage,
            sqs_client=FakeSQSClient(),
        )


def test_dispatch_once_rejects_missing_outbox():
    storage = SimpleNamespace(
        backend="dynamodb",
        outbox=None,
    )

    with pytest.raises(RuntimeError, match="no outbox"):
        dispatch_once(
            queue_url="https://example.test/queue",
            region="us-east-2",
            storage_instance=storage,
            sqs_client=FakeSQSClient(),
        )


def test_dispatch_once_rejects_empty_queue_url():
    storage = SimpleNamespace(
        backend="dynamodb",
        outbox=FakeOutboxRepository([]),
    )

    with pytest.raises(ValueError, match="queue URL"):
        dispatch_once(
            queue_url="",
            region="us-east-2",
            storage_instance=storage,
            sqs_client=FakeSQSClient(),
        )
