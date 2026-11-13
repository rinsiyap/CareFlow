
"""
Standalone CareFlow outbox dispatcher.

Run from app/backend:

    python -m careflow_api.outbox_worker

Each invocation dispatches one batch of pending events.
It does not start the FastAPI application.
"""

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


logger = logging.getLogger("careflow.outbox_worker")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def parse_batch_size(value: str | None) -> int:
    """Read and validate the maximum number of events per invocation."""

    if value is None or not value.strip():
        return 10

    try:
        batch_size = int(value)
    except ValueError as exc:
        raise ValueError(
            "CARE_FLOW_OUTBOX_DISPATCH_BATCH_SIZE must be an integer."
        ) from exc

    if batch_size < 1:
        raise ValueError(
            "CARE_FLOW_OUTBOX_DISPATCH_BATCH_SIZE must be at least 1."
        )

    return batch_size


def dispatch_once(
    *,
    queue_url: str,
    region: str,
    batch_size: int = 10,
    storage_instance: Any | None = None,
    sqs_client: Any | None = None,
):
    """
    Dispatch one batch of pending outbox events.

    Optional injected dependencies allow local tests to run without
    connecting to AWS.
    """

    if not queue_url or not queue_url.strip():
        raise ValueError("An SQS queue URL is required.")

    if not region or not region.strip():
        raise ValueError("An AWS region is required.")

    if batch_size < 1:
        raise ValueError("Batch size must be at least 1.")

    if storage_instance is None:
        # Import only when dispatching. The worker's configuration
        # is loaded before this import initializes application storage.
        from careflow_api.storage import storage

        storage_instance = storage

    if storage_instance.backend != "dynamodb":
        raise RuntimeError(
            "The outbox worker requires "
            "CARE_FLOW_STORAGE_BACKEND=dynamodb."
        )

    if storage_instance.outbox is None:
        raise RuntimeError(
            "The configured storage backend has no outbox repository."
        )

    if sqs_client is None:
        import boto3

        sqs_client = boto3.client(
            "sqs",
            region_name=region,
        )

    from careflow_api.outbox_dispatcher import OutboxDispatcher

    dispatcher = OutboxDispatcher(
        outbox_repository=storage_instance.outbox,
        sqs_client=sqs_client,
        queue_url=queue_url,
    )

    return dispatcher.dispatch_pending(limit=batch_size)


def main() -> int:
    """Load configuration and dispatch one batch."""

    load_dotenv(
        dotenv_path=PROJECT_ROOT / ".env",
        override=False,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        backend = os.getenv(
            "CARE_FLOW_STORAGE_BACKEND",
            "memory",
        ).strip().lower()

        if backend != "dynamodb":
            raise RuntimeError(
                "Set CARE_FLOW_STORAGE_BACKEND=dynamodb "
                "before running the outbox worker."
            )

        queue_url = os.getenv(
            "CARE_FLOW_SQS_QUEUE_URL",
            "",
        ).strip()

        if not queue_url:
            raise RuntimeError(
                "CARE_FLOW_SQS_QUEUE_URL is not configured."
            )

        region = (
            os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("AWS_REGION")
            or "us-east-2"
        ).strip()

        batch_size = parse_batch_size(
            os.getenv("CARE_FLOW_OUTBOX_DISPATCH_BATCH_SIZE")
        )

        report = dispatch_once(
            queue_url=queue_url,
            region=region,
            batch_size=batch_size,
        )

        print(json.dumps(asdict(report), indent=2))

        if report.failures:
            logger.error(
                "Outbox dispatch completed with %d failure(s).",
                len(report.failures),
            )
            return 1

        logger.info(
            "Outbox dispatch completed: %d event(s) found, "
            "%d message(s) sent, %d event(s) marked delivered.",
            report.events_found,
            report.messages_sent,
            report.events_marked_delivered,
        )

        return 0

    except Exception:
        logger.exception("Outbox dispatch failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
