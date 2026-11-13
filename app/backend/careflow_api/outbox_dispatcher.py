
"""Publish DynamoDB outbox events to SQS using worker leases."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


@dataclass
class DispatchReport:
    """Summary of one outbox dispatch run."""

    events_found: int = 0
    messages_sent: int = 0
    events_marked_delivered: int = 0
    events_already_updated: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


class OutboxDispatcher:
    """
    Publishes outbox events to SQS using atomic DynamoDB leases.

    Delivery is at-least-once. Consumers should use event_id for
    idempotency because a message may be sent successfully while
    the subsequent DynamoDB update fails.
    """

    EVENT_FIELDS = (
        "event_id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "created_at",
        "payload",
    )

    def __init__(
        self,
        outbox_repository: Any,
        sqs_client: Any,
        queue_url: str,
        clock: Callable[[], datetime] | None = None,
        lease_duration_seconds: int = 60,
        worker_id: str | None = None,
    ) -> None:
        if not isinstance(queue_url, str) or not queue_url.strip():
            raise ValueError("queue_url must not be empty.")

        if (
            not isinstance(lease_duration_seconds, int)
            or isinstance(lease_duration_seconds, bool)
            or lease_duration_seconds < 1
        ):
            raise ValueError(
                "lease_duration_seconds must be greater than zero."
            )

        if worker_id is not None and (
            not isinstance(worker_id, str) or not worker_id.strip()
        ):
            raise ValueError("worker_id must not be empty.")

        self.outbox_repository = outbox_repository
        self.sqs_client = sqs_client
        self.queue_url = queue_url
        self.clock = clock or (
            lambda: datetime.now(timezone.utc)
        )
        self.lease_duration_seconds = lease_duration_seconds
        self.worker_id = worker_id or str(uuid.uuid4())

    def _now(self) -> datetime:
        """Return the injected clock value normalized to UTC."""

        value = self.clock()

        if not isinstance(value, datetime):
            raise ValueError("clock must return a datetime.")

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "clock must return a timezone-aware datetime."
            )

        return value.astimezone(timezone.utc)

    def _get_candidates(
        self,
        now: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Combine pending and expired processing events without duplicates."""

        pending = self.outbox_repository.list_pending(limit=limit)

        expired = self.outbox_repository.list_expired_processing(
            now=now,
            limit=limit,
        )

        unique_events: dict[str, dict[str, Any]] = {}

        for event in [*pending, *expired]:
            event_id = str(event["event_id"])
            unique_events[event_id] = event

        candidates = list(unique_events.values())
        candidates.sort(
            key=lambda event: str(event.get("created_at", ""))
        )

        return candidates[:limit]

    @classmethod
    def _build_message_event(
        cls,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build the public event envelope.

        Outbox delivery state, attempts, and lease information must
        remain internal to DynamoDB.
        """

        return {
            field: event[field]
            for field in cls.EVENT_FIELDS
            if field in event
        }

    def dispatch_pending(self, limit: int = 10) -> DispatchReport:
        """
        Claim and publish up to limit pending or expired events.

        Failed SQS sends release their lease back to pending.
        Successful sends are marked delivered only while this worker
        still owns the lease.
        """

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
        ):
            raise ValueError("limit must be greater than zero.")

        now = self._now()
        now_iso = now.isoformat()

        events = self._get_candidates(
            now=now_iso,
            limit=limit,
        )

        report = DispatchReport(events_found=len(events))

        for event in events:
            event_id = str(event["event_id"])

            claim_time = self._now()
            claim_time_iso = claim_time.isoformat()

            lease_expires_at = (
                claim_time
                + timedelta(seconds=self.lease_duration_seconds)
            ).isoformat()

            try:
                claimed_event = self.outbox_repository.claim_event(
                    event_id=event_id,
                    lease_owner=self.worker_id,
                    lease_expires_at=lease_expires_at,
                    now=claim_time_iso,
                )

            except Exception as error:
                report.failures.append(
                    {
                        "event_id": event_id,
                        "stage": "claim",
                        "error": str(error),
                    }
                )
                continue

            if claimed_event is None:
                report.events_already_updated += 1
                continue

            source_event = (
                claimed_event
                if isinstance(claimed_event, dict)
                else event
            )

            message_event = self._build_message_event(source_event)

            try:
                message_body = json.dumps(
                    message_event,
                    separators=(",", ":"),
                    sort_keys=True,
                )

                self.sqs_client.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=message_body,
                    MessageAttributes={
                        "event_id": {
                            "DataType": "String",
                            "StringValue": event_id,
                        },
                        "event_type": {
                            "DataType": "String",
                            "StringValue": str(
                                message_event.get(
                                    "event_type",
                                    "unknown",
                                )
                            ),
                        },
                    },
                )

                report.messages_sent += 1

            except Exception as error:
                report.failures.append(
                    {
                        "event_id": event_id,
                        "stage": "send",
                        "error": str(error),
                    }
                )

                try:
                    self.outbox_repository.release_claim(
                        event_id=event_id,
                        lease_owner=self.worker_id,
                    )
                except Exception as release_error:
                    report.failures.append(
                        {
                            "event_id": event_id,
                            "stage": "release_claim",
                            "error": str(release_error),
                        }
                    )

                continue

            try:
                delivered_at = self._now().isoformat()

                updated = (
                    self.outbox_repository.mark_claimed_delivered(
                        event_id=event_id,
                        lease_owner=self.worker_id,
                        delivered_at=delivered_at,
                    )
                )

                if updated is None:
                    report.events_already_updated += 1
                    continue

                report.events_marked_delivered += 1

            except Exception as error:
                report.failures.append(
                    {
                        "event_id": event_id,
                        "stage": "mark_delivered",
                        "error": str(error),
                    }
                )

        return report
