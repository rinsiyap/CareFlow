
"""
CareFlow DynamoDB table definitions.

This module creates tables using a supplied DynamoDB resource.
It does not create tables automatically at application startup
unless the DynamoDB storage backend is explicitly selected.
"""

from typing import Any


DEFAULT_TABLE_NAMES = {
    "users": "CareFlow-Users",
    "doctors": "CareFlow-Doctors",
    "appointments": "CareFlow-Appointments",
    "outbox": "CareFlow-Outbox",
    "processed_events": "CareFlow-ProcessedEvents",
}


def create_dynamodb_tables(
    dynamodb: Any,
    table_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Create the five CareFlow DynamoDB tables if they do not exist.

    Tables:
        users            - Stores user accounts.
        doctors          - Stores doctor profiles.
        appointments     - Stores appointment records.
        outbox            - Stores events waiting for asynchronous delivery.
        processed_events - Tracks Lambda event processing and idempotency.

    The outbox table includes a GSI for querying events by status
    and creation time.

    Args:
        dynamodb: A boto3 DynamoDB resource.
        table_names: Optional table-name overrides.

    Returns:
        Dictionary containing the five DynamoDB Table resources.
    """

    names = {
        **DEFAULT_TABLE_NAMES,
        **(table_names or {}),
    }

    existing_tables = set(
        dynamodb.meta.client.list_tables()["TableNames"]
    )

    # ---------------------------------------------------------
    # USERS TABLE
    # ---------------------------------------------------------

    if names["users"] not in existing_tables:
        dynamodb.create_table(
            TableName=names["users"],
            KeySchema=[
                {
                    "AttributeName": "email",
                    "KeyType": "HASH",
                },
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "email",
                    "AttributeType": "S",
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    # ---------------------------------------------------------
    # DOCTORS TABLE
    # ---------------------------------------------------------

    if names["doctors"] not in existing_tables:
        dynamodb.create_table(
            TableName=names["doctors"],
            KeySchema=[
                {
                    "AttributeName": "doctor_id",
                    "KeyType": "HASH",
                },
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "doctor_id",
                    "AttributeType": "S",
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    # ---------------------------------------------------------
    # APPOINTMENTS TABLE
    # ---------------------------------------------------------

    if names["appointments"] not in existing_tables:
        dynamodb.create_table(
            TableName=names["appointments"],
            KeySchema=[
                {
                    "AttributeName": "appointment_id",
                    "KeyType": "HASH",
                },
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "appointment_id",
                    "AttributeType": "S",
                },
                {
                    "AttributeName": "patient_email",
                    "AttributeType": "S",
                },
                {
                    "AttributeName": "doctor_id",
                    "AttributeType": "S",
                },
                {
                    "AttributeName": "scheduled_at",
                    "AttributeType": "S",
                },
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "patient_email-scheduled_at-index",
                    "KeySchema": [
                        {
                            "AttributeName": "patient_email",
                            "KeyType": "HASH",
                        },
                        {
                            "AttributeName": "scheduled_at",
                            "KeyType": "RANGE",
                        },
                    ],
                    "Projection": {
                        "ProjectionType": "ALL",
                    },
                },
                {
                    "IndexName": "doctor_id-scheduled_at-index",
                    "KeySchema": [
                        {
                            "AttributeName": "doctor_id",
                            "KeyType": "HASH",
                        },
                        {
                            "AttributeName": "scheduled_at",
                            "KeyType": "RANGE",
                        },
                    ],
                    "Projection": {
                        "ProjectionType": "ALL",
                    },
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    # ---------------------------------------------------------
    # OUTBOX TABLE
    # ---------------------------------------------------------

    if names["outbox"] not in existing_tables:
        dynamodb.create_table(
            TableName=names["outbox"],
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
                {
                    "AttributeName": "status",
                    "AttributeType": "S",
                },
                {
                    "AttributeName": "created_at",
                    "AttributeType": "S",
                },
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-created_at-index",
                    "KeySchema": [
                        {
                            "AttributeName": "status",
                            "KeyType": "HASH",
                        },
                        {
                            "AttributeName": "created_at",
                            "KeyType": "RANGE",
                        },
                    ],
                    "Projection": {
                        "ProjectionType": "ALL",
                    },
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    # ---------------------------------------------------------
    # PROCESSED EVENTS TABLE
    # ---------------------------------------------------------

    if names["processed_events"] not in existing_tables:
        dynamodb.create_table(
            TableName=names["processed_events"],
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

    # ---------------------------------------------------------
    # RETURN TABLE RESOURCES
    # ---------------------------------------------------------

    tables = {
        key: dynamodb.Table(name)
        for key, name in names.items()
    }

    for table in tables.values():
        table.wait_until_exists()

    return tables
