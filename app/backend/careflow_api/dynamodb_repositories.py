
"""
CareFlow DynamoDB repository implementations.

These adapters implement the same repository contracts as the
in-memory implementations.

DynamoDB partition keys:
    Users:        email
    Doctors:      doctor_id
    Appointments: appointment_id
    Outbox:       event_id

The application continues to use "id" for doctor and appointment
records. DynamoDB-specific partition keys are kept internal.

Appointment creation and status transitions can optionally use
DynamoDB transactions to write appointment changes and outbox
events atomically.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from careflow_api.repository_contracts import Record


# =============================================================
# DYNAMODB CONVERSION HELPERS
# =============================================================

def _to_dynamodb(value: Any) -> Any:
    """Convert Python values into DynamoDB-compatible values."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {
            key: _to_dynamodb(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _to_dynamodb(item)
            for item in value
        ]

    return value


def _from_dynamodb(value: Any) -> Any:
    """Convert DynamoDB Decimal values into Python numbers."""

    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)

        return float(value)

    if isinstance(value, dict):
        return {
            key: _from_dynamodb(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _from_dynamodb(item)
            for item in value
        ]

    return value


# =============================================================
# DYNAMODB ERROR HELPERS
# =============================================================

def _is_conditional_failure(error: ClientError) -> bool:
    """Identify a failed DynamoDB conditional write."""

    return (
        error.response.get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _is_transaction_conditional_failure(
    error: ClientError,
) -> bool:
    """
    Identify a conditional failure inside TransactWriteItems.

    DynamoDB reports transaction condition failures through
    TransactionCanceledException and cancellation reasons.
    """

    if error.response.get("Error", {}).get("Code") != (
        "TransactionCanceledException"
    ):
        return False

    cancellation_reasons = (
        error.response.get("CancellationReasons") or []
    )

    return any(
        reason.get("Code") == "ConditionalCheckFailed"
        for reason in cancellation_reasons
    )


def _transaction_condition_failed_at(
    error: ClientError,
    operation_index: int,
) -> bool | None:
    """
    Check whether a specific transaction operation failed its
    condition.

    Returns:
        True: the specified operation failed its condition.
        False: another operation failed, or the specified
               operation did not fail its condition.
        None: cancellation reasons were not provided.
    """

    if error.response.get("Error", {}).get("Code") != (
        "TransactionCanceledException"
    ):
        return False

    reasons = error.response.get("CancellationReasons")

    if not reasons:
        return None

    if operation_index >= len(reasons):
        return None

    return (
        reasons[operation_index].get("Code")
        == "ConditionalCheckFailed"
    )


# =============================================================
# OUTBOX EVENT HELPER
# =============================================================

def _build_outbox_event(
    event_type: str,
    appointment_id: str,
    payload: Record,
) -> Record:
    """Build a new pending appointment outbox event."""

    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "aggregate_type": "appointment",
        "aggregate_id": appointment_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": _to_dynamodb(payload),
    }


# =============================================================
# USER REPOSITORY
# =============================================================

class DynamoDBUserRepository:
    """DynamoDB implementation of UserRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    def get_by_email(self, email: str) -> Record | None:
        response = self.table.get_item(
            Key={"email": email},
            ConsistentRead=True,
        )

        item = response.get("Item")

        if item is None:
            return None

        return _from_dynamodb(item)

    def create_user(self, user: Record) -> Record:
        item = _to_dynamodb(user)

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(email)",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                raise ValueError(
                    f"User already exists: {user['email']}"
                ) from error

            raise

        return user


# =============================================================
# DOCTOR REPOSITORY
# =============================================================

class DynamoDBDoctorRepository:
    """DynamoDB implementation of DoctorRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    @staticmethod
    def _normalize_doctor(item: dict) -> Record:
        """
        Convert a DynamoDB doctor item into an application record.

        Normalize consultation_fee explicitly because the API expects
        a float, including when its value is an integral number.
        """

        item.pop("doctor_id", None)

        record = _from_dynamodb(item)

        if record.get("consultation_fee") is not None:
            record["consultation_fee"] = float(
                record["consultation_fee"]
            )

        return record

    def get_by_id(self, doctor_id: str) -> Record | None:
        response = self.table.get_item(
            Key={"doctor_id": doctor_id},
            ConsistentRead=True,
        )

        item = response.get("Item")

        if item is None:
            return None

        return self._normalize_doctor(item)

    def create_doctor(self, doctor: Record) -> Record:
        item = _to_dynamodb(doctor)

        # Map application "id" to the DynamoDB partition key.
        item["doctor_id"] = doctor["id"]

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(doctor_id)",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                raise ValueError(
                    f"Doctor already exists: {doctor['id']}"
                ) from error

            raise

        return doctor

    def list_available(self) -> list[Record]:
        response = self.table.scan(
            FilterExpression="#available = :available",
            ExpressionAttributeNames={
                "#available": "available",
            },
            ExpressionAttributeValues={
                ":available": True,
            },
        )

        records = []

        while True:
            for item in response.get("Items", []):
                records.append(
                    self._normalize_doctor(item)
                )

            if "LastEvaluatedKey" not in response:
                break

            response = self.table.scan(
                FilterExpression="#available = :available",
                ExpressionAttributeNames={
                    "#available": "available",
                },
                ExpressionAttributeValues={
                    ":available": True,
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )

        return records


# =============================================================
# APPOINTMENT REPOSITORY
# =============================================================

class DynamoDBAppointmentRepository:
    """
    DynamoDB implementation of AppointmentRepository.

    When an outbox table is provided, appointment creation and
    status transitions use atomic DynamoDB transactions.

    Without an outbox table, the repository preserves its original
    direct-write behaviour.
    """

    PATIENT_INDEX = "patient_email-scheduled_at-index"
    DOCTOR_INDEX = "doctor_id-scheduled_at-index"

    def __init__(
        self,
        table: Any,
        outbox_table: Any | None = None,
    ) -> None:
        self.table = table
        self.outbox_table = outbox_table

        # Use the client attached to the same DynamoDB resource.
        self.client = table.meta.client

    def create_appointment(self, appointment: Record) -> Record:
        """
        Create an appointment.

        If an outbox table is configured, the appointment and its
        appointment.created event are stored atomically.
        """

        item = _to_dynamodb(appointment)

        # Map application "id" to the DynamoDB partition key.
        item["appointment_id"] = appointment["id"]

        # Backward-compatible direct write.
        if self.outbox_table is None:
            try:
                self.table.put_item(
                    Item=item,
                    ConditionExpression=(
                        "attribute_not_exists(appointment_id)"
                    ),
                )

            except ClientError as error:
                if _is_conditional_failure(error):
                    raise ValueError(
                        "Appointment already exists: "
                        f"{appointment['id']}"
                    ) from error

                raise

            return appointment

        event = _build_outbox_event(
            event_type="appointment.created",
            appointment_id=appointment["id"],
            payload={
                "appointment_id": appointment["id"],
                "patient_email": appointment["patient_email"],
                "doctor_id": appointment["doctor_id"],
                "scheduled_at": appointment["scheduled_at"],
                "status": appointment["status"],
            },
        )

        try:
            self.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self.table.name,
                            "Item": item,
                            "ConditionExpression": (
                                "attribute_not_exists(appointment_id)"
                            ),
                        }
                    },
                    {
                        "Put": {
                            "TableName": self.outbox_table.name,
                            "Item": _to_dynamodb(event),
                            "ConditionExpression": (
                                "attribute_not_exists(event_id)"
                            ),
                        }
                    },
                ]
            )

        except ClientError as error:
            if _is_transaction_conditional_failure(error):
                raise ValueError(
                    "Appointment already exists or its transaction "
                    "could not be completed: "
                    f"{appointment['id']}"
                ) from error

            raise

        return appointment

    def get_by_id(
        self,
        appointment_id: str,
    ) -> Record | None:
        response = self.table.get_item(
            Key={"appointment_id": appointment_id},
            ConsistentRead=True,
        )

        item = response.get("Item")

        if item is None:
            return None

        item.pop("appointment_id", None)

        return _from_dynamodb(item)

    def list_for_patient(
        self,
        patient_email: str,
    ) -> list[Record]:
        return self._query_index(
            index_name=self.PATIENT_INDEX,
            partition_key="patient_email",
            partition_value=patient_email,
        )

    def list_for_doctor(
        self,
        doctor_id: str,
    ) -> list[Record]:
        return self._query_index(
            index_name=self.DOCTOR_INDEX,
            partition_key="doctor_id",
            partition_value=doctor_id,
        )

    def _query_index(
        self,
        index_name: str,
        partition_key: str,
        partition_value: str,
    ) -> list[Record]:
        response = self.table.query(
            IndexName=index_name,
            KeyConditionExpression=(
                Key(partition_key).eq(partition_value)
            ),
            ScanIndexForward=True,
        )

        records = []

        while True:
            for item in response.get("Items", []):
                # Keep DynamoDB's internal key out of API records.
                item.pop("appointment_id", None)
                records.append(_from_dynamodb(item))

            if "LastEvaluatedKey" not in response:
                break

            response = self.table.query(
                IndexName=index_name,
                KeyConditionExpression=(
                    Key(partition_key).eq(partition_value)
                ),
                ScanIndexForward=True,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )

        return records

    def list_all(self) -> list[Record]:
        response = self.table.scan()

        records = []

        while True:
            for item in response.get("Items", []):
                item.pop("appointment_id", None)
                records.append(_from_dynamodb(item))

            if "LastEvaluatedKey" not in response:
                break

            response = self.table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )

        return records

    def transition_status(
        self,
        appointment_id: str,
        expected_status: str,
        new_status: str,
    ) -> Record | None:
        """
        Change appointment status.

        With an outbox table, the appointment status update and
        appointment.status_changed event are committed atomically.

        Returns None when the appointment is missing or its status
        no longer matches expected_status.
        """

        # Backward-compatible direct update.
        if self.outbox_table is None:
            try:
                response = self.table.update_item(
                    Key={
                        "appointment_id": appointment_id,
                    },
                    UpdateExpression="SET #status = :new_status",
                    ConditionExpression="#status = :expected_status",
                    ExpressionAttributeNames={
                        "#status": "status",
                    },
                    ExpressionAttributeValues={
                        ":expected_status": expected_status,
                        ":new_status": new_status,
                    },
                    ReturnValues="ALL_NEW",
                )

            except ClientError as error:
                if _is_conditional_failure(error):
                    return None

                raise

            item = response["Attributes"]
            item.pop("appointment_id", None)

            return _from_dynamodb(item)

        # Read the appointment to construct the event payload.
        # The transaction below independently checks the expected
        # status to protect against concurrent updates.
        appointment = self.get_by_id(appointment_id)

        if appointment is None:
            return None

        if appointment.get("status") != expected_status:
            return None

        event = _build_outbox_event(
            event_type="appointment.status_changed",
            appointment_id=appointment_id,
            payload={
                "appointment_id": appointment_id,
                "patient_email": appointment["patient_email"],
                "doctor_id": appointment["doctor_id"],
                "previous_status": expected_status,
                "new_status": new_status,
            },
        )

        try:
            self.client.transact_write_items(
                TransactItems=[
                    {
                        "Update": {
                            "TableName": self.table.name,
                            "Key": {
                                "appointment_id": appointment_id,
                            },
                            "UpdateExpression": (
                                "SET #status = :new_status"
                            ),
                            "ConditionExpression": (
                                "#status = :expected_status"
                            ),
                            "ExpressionAttributeNames": {
                                "#status": "status",
                            },
                            "ExpressionAttributeValues": {
                                ":expected_status": expected_status,
                                ":new_status": new_status,
                            },
                        }
                    },
                    {
                        "Put": {
                            "TableName": self.outbox_table.name,
                            "Item": _to_dynamodb(event),
                            "ConditionExpression": (
                                "attribute_not_exists(event_id)"
                            ),
                        }
                    },
                ]
            )

        except ClientError as error:
            if _is_transaction_conditional_failure(error):
                appointment_condition_failed = (
                    _transaction_condition_failed_at(error, 0)
                )

                # If DynamoDB provides cancellation reasons,
                # only treat an appointment condition failure
                # as a stale transition.
                if appointment_condition_failed is False:
                    raise

                # If cancellation reasons are unavailable, retain
                # compatibility with implementations that only
                # expose the transaction-level error code.
                return None

            raise

        # TransactWriteItems does not return updated attributes.
        return self.get_by_id(appointment_id)


# =============================================================
# OUTBOX REPOSITORY
# =============================================================

class DynamoDBOutboxRepository:
    """
    DynamoDB repository for asynchronous application events.

    Events begin with status="pending".

    A dispatcher can:
        1. Retrieve pending events.
        2. Publish each event to a message queue.
        3. Mark successfully published events as delivered.

    The repository supports at-least-once delivery workflows.
    Duplicate message delivery remains possible if a dispatcher
    crashes after publishing but before marking an event delivered.
    """

    PENDING_INDEX = "status-created_at-index"

    def __init__(self, table: Any) -> None:
        self.table = table

    def create_event(self, event: Record) -> Record:
        """
        Store a new pending outbox event.

        Required fields:
            event_id
            status
            created_at

        Duplicate event IDs are rejected.
        """

        required_fields = {
            "event_id",
            "status",
            "created_at",
        }

        missing_fields = required_fields - event.keys()

        if missing_fields:
            raise ValueError(
                "Outbox event is missing required fields: "
                f"{', '.join(sorted(missing_fields))}"
            )

        if event["status"] != "pending":
            raise ValueError(
                "New outbox events must have status='pending'."
            )

        item = _to_dynamodb(event)

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists(event_id)"
                ),
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                raise ValueError(
                    "Outbox event already exists: "
                    f"{event['event_id']}"
                ) from error

            raise

        return event

    def get_by_id(self, event_id: str) -> Record | None:
        """Retrieve an outbox event by its event ID."""

        response = self.table.get_item(
            Key={
                "event_id": event_id,
            },
            ConsistentRead=True,
        )

        item = response.get("Item")

        if item is None:
            return None

        return _from_dynamodb(item)

    def list_pending(self, limit: int = 100) -> list[Record]:
        """
        Retrieve pending events in creation-time order.

        Uses the status-created_at GSI rather than scanning
        the entire outbox table.

        Args:
            limit: Maximum number of events to return.

        Returns:
            Pending event records ordered by created_at.
        """

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero."
            )

        events: list[Record] = []
        last_evaluated_key = None

        while len(events) < limit:
            remaining = limit - len(events)

            query_options: dict[str, Any] = {
                "IndexName": self.PENDING_INDEX,
                "KeyConditionExpression": (
                    Key("status").eq("pending")
                ),
                "ScanIndexForward": True,
                "Limit": remaining,
            }

            if last_evaluated_key is not None:
                query_options["ExclusiveStartKey"] = (
                    last_evaluated_key
                )

            response = self.table.query(**query_options)

            events.extend(
                _from_dynamodb(item)
                for item in response.get("Items", [])
            )

            last_evaluated_key = response.get(
                "LastEvaluatedKey"
            )

            if last_evaluated_key is None:
                break

        return events

    def list_expired_processing(
        self,
        now: str,
        limit: int = 100,
    ) -> list[Record]:
        """
        Retrieve processing events whose leases have expired.

        The status-created_at GSI is queried for processing events.
        A filter selects only events whose lease expiry is at or
        before the supplied UTC ISO timestamp.

        Pagination is important because DynamoDB applies filters
        after evaluating each query page. A page may contain no
        matching items while still returning a LastEvaluatedKey.
        """

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero."
            )

        events: list[Record] = []
        last_evaluated_key = None

        while len(events) < limit:
            remaining = limit - len(events)

            query_options: dict[str, Any] = {
                "IndexName": self.PENDING_INDEX,
                "KeyConditionExpression": (
                    Key("status").eq("processing")
                ),
                "FilterExpression": (
                    Attr("lease_expires_at").lte(now)
                ),
                "ScanIndexForward": True,
                "Limit": remaining,
            }

            if last_evaluated_key is not None:
                query_options["ExclusiveStartKey"] = (
                    last_evaluated_key
                )

            response = self.table.query(**query_options)

            events.extend(
                _from_dynamodb(item)
                for item in response.get("Items", [])
            )

            last_evaluated_key = response.get(
                "LastEvaluatedKey"
            )

            if last_evaluated_key is None:
                break

        return events

    def claim_event(
        self,
        event_id: str,
        lease_owner: str,
        lease_expires_at: str,
        now: str,
    ) -> Record | None:
        """
        Atomically claim a pending or expired processing event.

        Only one competing worker can successfully claim the event.
        Each successful claim increments its attempts counter.

        Returns the claimed event, or None if another worker owns
        the active lease or the event is no longer claimable.
        """

        if not lease_owner.strip():
            raise ValueError(
                "lease_owner must not be empty."
            )

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :processing, "
                    "lease_owner = :owner, "
                    "lease_expires_at = :expires, "
                    "attempts = if_not_exists(attempts, :zero) "
                    "+ :one"
                ),
                ConditionExpression=(
                    "#status = :pending OR "
                    "(#status = :processing "
                    "AND lease_expires_at <= :now)"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":owner": lease_owner,
                    ":expires": lease_expires_at,
                    ":now": now,
                    ":zero": 0,
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])

    def release_claim(
        self,
        event_id: str,
        lease_owner: str,
    ) -> Record | None:
        """
        Return a claimed event to pending after a failed send.

        Only the worker holding the current lease can release it.
        """

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :pending "
                    "REMOVE lease_owner, lease_expires_at"
                ),
                ConditionExpression=(
                    "#status = :processing "
                    "AND lease_owner = :owner"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":owner": lease_owner,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])

    def mark_claimed_delivered(
        self,
        event_id: str,
        lease_owner: str,
        delivered_at: str,
    ) -> Record | None:
        """
        Mark an event delivered if the caller still owns its lease.

        The lease fields are removed after successful delivery.
        """

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :delivered, "
                    "delivered_at = :delivered_at "
                    "REMOVE lease_owner, lease_expires_at"
                ),
                ConditionExpression=(
                    "#status = :processing "
                    "AND lease_owner = :owner"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":processing": "processing",
                    ":delivered": "delivered",
                    ":owner": lease_owner,
                    ":delivered_at": delivered_at,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])

    def mark_delivered(
        self,
        event_id: str,
        delivered_at: str,
    ) -> Record | None:
        """
        Mark a pending event as delivered.

        The conditional update prevents an event that is already
        delivered from being marked delivered again.

        Returns:
            Updated event, or None if it is missing or no longer pending.
        """

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :delivered, "
                    "delivered_at = :delivered_at"
                ),
                ConditionExpression="#status = :pending",
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":delivered": "delivered",
                    ":delivered_at": delivered_at,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])


# =============================================================
# PROCESSED EVENTS REPOSITORY
# =============================================================

class DynamoDBProcessedEventsRepository:
    """
    Tracks asynchronous event processing and prevents duplicate work.

    An event can be claimed when it is new, pending, or has an
    expired processing lease. A processed event cannot be claimed
    again.

    The event_id is the idempotency key.
    """

    def __init__(self, table: Any) -> None:
        self.table = table

    def get_by_id(self, event_id: str) -> Record | None:
        """Retrieve an event using a strongly consistent read."""

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must not be empty")

        response = self.table.get_item(
            Key={
                "event_id": event_id,
            },
            ConsistentRead=True,
        )

        item = response.get("Item")

        if item is None:
            return None

        return _from_dynamodb(item)

    def claim_event(
        self,
        event_id: str,
        lease_owner: str,
        lease_expires_at: str,
        now: str,
    ) -> Record | None:
        """
        Atomically claim an event for processing.

        A claim succeeds when:
            - The event does not exist yet.
            - The event is pending.
            - The previous processing lease has expired.

        A processed event or an event with an active lease
        cannot be claimed.

        Returns:
            Updated event when claimed, otherwise None.
        """

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must not be empty")

        if (
            not isinstance(lease_owner, str)
            or not lease_owner.strip()
        ):
            raise ValueError("lease_owner must not be empty")

        if not isinstance(lease_expires_at, str) or not lease_expires_at:
            raise ValueError("lease_expires_at must not be empty")

        if not isinstance(now, str) or not now:
            raise ValueError("now must not be empty")

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :processing, "
                    "lease_owner = :owner, "
                    "lease_expires_at = :expires, "
                    "attempts = if_not_exists(attempts, :zero) + :one"
                ),
                ConditionExpression=(
                    "attribute_not_exists(event_id) "
                    "OR #status = :pending "
                    "OR ("
                    "#status = :processing "
                    "AND lease_expires_at <= :now"
                    ")"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":processing": "processing",
                    ":pending": "pending",
                    ":owner": lease_owner,
                    ":expires": lease_expires_at,
                    ":now": now,
                    ":zero": 0,
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])

    def release_claim(
        self,
        event_id: str,
        lease_owner: str,
    ) -> Record | None:
        """
        Release a claim after processing fails.

        Only the worker holding the current lease can release it.
        The event becomes pending so another invocation can retry
        it without waiting for lease expiration.
        """

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must not be empty")

        if (
            not isinstance(lease_owner, str)
            or not lease_owner.strip()
        ):
            raise ValueError("lease_owner must not be empty")

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :pending "
                    "REMOVE lease_owner, lease_expires_at"
                ),
                ConditionExpression=(
                    "#status = :processing "
                    "AND lease_owner = :owner"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":owner": lease_owner,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])

    def mark_processed(
        self,
        event_id: str,
        lease_owner: str,
        processed_at: str,
    ) -> Record | None:
        """
        Mark an event processed if the caller still owns its lease.

        The lease fields are removed after successful processing.
        A processed event cannot be claimed again.
        """

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must not be empty")

        if (
            not isinstance(lease_owner, str)
            or not lease_owner.strip()
        ):
            raise ValueError("lease_owner must not be empty")

        if not isinstance(processed_at, str) or not processed_at:
            raise ValueError("processed_at must not be empty")

        try:
            response = self.table.update_item(
                Key={
                    "event_id": event_id,
                },
                UpdateExpression=(
                    "SET #status = :processed, "
                    "processed_at = :processed_at "
                    "REMOVE lease_owner, lease_expires_at"
                ),
                ConditionExpression=(
                    "#status = :processing "
                    "AND lease_owner = :owner"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":processing": "processing",
                    ":processed": "processed",
                    ":owner": lease_owner,
                    ":processed_at": processed_at,
                },
                ReturnValues="ALL_NEW",
            )

        except ClientError as error:
            if _is_conditional_failure(error):
                return None

            raise

        return _from_dynamodb(response["Attributes"])


# =============================================================
# DOCTOR ACCOUNT PROVISIONER
# =============================================================

class DynamoDBDoctorAccountProvisioner:
    """
    Creates a doctor login account and links the doctor profile
    using one atomic DynamoDB transaction.

    Both writes succeed together or neither write is committed.
    """

    def __init__(
        self,
        users_table: Any,
        doctors_table: Any,
    ) -> None:
        self.users_table = users_table
        self.doctors_table = doctors_table

        # Use the client attached to the DynamoDB resource.
        self.client = users_table.meta.client

    def provision_doctor_account(
        self,
        doctor_id: str,
        user: Record,
    ) -> Record:
        # Validate doctor profile.
        doctor = self.doctors_table.get_item(
            Key={
                "doctor_id": doctor_id,
            },
            ConsistentRead=True,
        ).get("Item")

        if doctor is None:
            raise ValueError("Doctor not found")

        # Validate email uniqueness.
        email = user["email"]

        existing_user = self.users_table.get_item(
            Key={
                "email": email,
            },
            ConsistentRead=True,
        ).get("Item")

        if existing_user is not None:
            raise ValueError(
                "An account with this email already exists"
            )

        # Validate profile linkage.
        if doctor.get("account_email"):
            raise ValueError(
                "This doctor already has a login account"
            )

        if user.get("doctor_id") != doctor_id:
            raise ValueError(
                "Doctor account is not linked to the correct profile"
            )

        # Convert floats to Decimal. Do not manually serialize
        # AttributeValues: the resource-connected client handles it.
        transaction_user = _to_dynamodb(user)

        try:
            self.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self.users_table.name,
                            "Item": transaction_user,
                            "ConditionExpression": (
                                "attribute_not_exists(email)"
                            ),
                        }
                    },
                    {
                        "Update": {
                            "TableName": self.doctors_table.name,
                            "Key": {
                                "doctor_id": doctor_id,
                            },
                            "UpdateExpression": (
                                "SET account_email = :email"
                            ),
                            "ConditionExpression": (
                                "attribute_not_exists(account_email)"
                            ),
                            "ExpressionAttributeValues": {
                                ":email": email,
                            },
                        }
                    },
                ]
            )

        except ClientError as error:
            if _is_transaction_conditional_failure(error):
                raise ValueError(
                    "Doctor account could not be provisioned. "
                    "The email may already be in use or the doctor "
                    "profile may already be linked to an account."
                ) from error

            raise

        return user
