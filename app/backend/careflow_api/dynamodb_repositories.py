
"""
CareFlow DynamoDB repository implementations.

These adapters implement the same repository contracts as the
in-memory implementations.

DynamoDB partition keys:
    Users:        email
    Doctors:      doctor_id
    Appointments: appointment_id

The application continues to use "id" for doctor and appointment
records. DynamoDB-specific partition keys are kept internal.
"""

from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from careflow_api.repository_contracts import Record


def _to_dynamodb(value: Any) -> Any:
    """Convert Python values into DynamoDB-compatible values."""

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

    error_code = error.response.get("Error", {}).get("Code")

    if error_code != "TransactionCanceledException":
        return False

    cancellation_reasons = (
        error.response.get("CancellationReasons") or []
    )

    return any(
        reason.get("Code") == "ConditionalCheckFailed"
        for reason in cancellation_reasons
    )


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


class DynamoDBAppointmentRepository:
    """DynamoDB implementation of AppointmentRepository."""

    PATIENT_INDEX = "patient_email-scheduled_at-index"
    DOCTOR_INDEX = "doctor_id-scheduled_at-index"

    def __init__(self, table: Any) -> None:
        self.table = table

    def create_appointment(self, appointment: Record) -> Record:
        item = _to_dynamodb(appointment)

        # Map application "id" to the DynamoDB partition key.
        item["appointment_id"] = appointment["id"]

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
