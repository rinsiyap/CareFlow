
"""
Central storage entry point for CareFlow.

Supported backends:
    memory   - In-memory repositories (default)
    dynamodb - DynamoDB repositories

Select the backend with CARE_FLOW_STORAGE_BACKEND.
DynamoDB initialization happens only when explicitly selected.
"""

import os
from types import SimpleNamespace
from typing import Any


def _memory_storage() -> SimpleNamespace:
    """Return the shared in-memory repository instances."""

    from careflow_api.repositories import (
        appointments,
        doctor_account_provisioner,
        doctors,
        users,
    )

    def health_check() -> dict[str, Any]:
        """Check the in-memory storage backend."""

        return {
            "status": "connected",
            "backend": "memory",
        }

    return SimpleNamespace(
        users=users,
        doctors=doctors,
        appointments=appointments,
        doctor_account_provisioner=doctor_account_provisioner,
        backend="memory",
        health_check=health_check,
    )


def _dynamodb_storage(
    dynamodb_resource: Any | None = None,
    table_names: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Create DynamoDB repositories using a supplied or new resource."""

    if dynamodb_resource is None:
        import boto3

        region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
        endpoint_url = os.getenv("CARE_FLOW_DYNAMODB_ENDPOINT_URL")

        resource_options: dict[str, Any] = {
            "region_name": region,
        }

        if endpoint_url:
            resource_options["endpoint_url"] = endpoint_url

            # DynamoDB Local requires credentials, but does not validate
            # their values. Never inject dummy credentials for AWS.
            resource_options["aws_access_key_id"] = os.getenv(
                "AWS_ACCESS_KEY_ID",
                "local",
            )
            resource_options["aws_secret_access_key"] = os.getenv(
                "AWS_SECRET_ACCESS_KEY",
                "local",
            )

        dynamodb_resource = boto3.resource(
            "dynamodb",
            **resource_options,
        )

    from careflow_api.dynamodb_repositories import (
        DynamoDBAppointmentRepository,
        DynamoDBDoctorAccountProvisioner,
        DynamoDBDoctorRepository,
        DynamoDBUserRepository,
    )
    from careflow_api.dynamodb_tables import create_dynamodb_tables

    if table_names is None:
        table_names = {
            key: os.environ[environment_variable]
            for key, environment_variable in {
                "users": "CARE_FLOW_USERS_TABLE",
                "doctors": "CARE_FLOW_DOCTORS_TABLE",
                "appointments": "CARE_FLOW_APPOINTMENTS_TABLE",
            }.items()
            if os.getenv(environment_variable)
        }

    tables = create_dynamodb_tables(
        dynamodb_resource,
        table_names=table_names,
    )

    users = DynamoDBUserRepository(tables["users"])
    doctors = DynamoDBDoctorRepository(tables["doctors"])
    appointments = DynamoDBAppointmentRepository(
        tables["appointments"]
    )

    doctor_account_provisioner = DynamoDBDoctorAccountProvisioner(
        users_table=tables["users"],
        doctors_table=tables["doctors"],
    )

    def health_check() -> dict[str, Any]:
        """
        Verify that all required DynamoDB tables are accessible.

        Table.load() performs a DescribeTable request.
        An exception means that readiness cannot be confirmed.
        """

        for table_name, table in tables.items():
            table.load()

        return {
            "status": "connected",
            "backend": "dynamodb",
            "tables": list(tables.keys()),
        }

    return SimpleNamespace(
        users=users,
        doctors=doctors,
        appointments=appointments,
        doctor_account_provisioner=doctor_account_provisioner,
        backend="dynamodb",
        health_check=health_check,
    )


def create_storage(
    backend: str | None = None,
    dynamodb_resource: Any | None = None,
    table_names: dict[str, str] | None = None,
) -> SimpleNamespace:
    """
    Build the configured repository collection.

    Args:
        backend: Optional backend override. Defaults to the environment.
        dynamodb_resource: Optional boto3 DynamoDB resource, useful for tests.
        table_names: Optional DynamoDB table-name overrides.

    Returns:
        An object containing repositories, backend information,
        and a health_check function.
    """

    selected_backend = (
        backend or os.getenv("CARE_FLOW_STORAGE_BACKEND", "memory")
    ).strip().lower()

    if selected_backend == "memory":
        return _memory_storage()

    if selected_backend == "dynamodb":
        return _dynamodb_storage(
            dynamodb_resource=dynamodb_resource,
            table_names=table_names,
        )

    raise ValueError(
        f"Unsupported CARE_FLOW_STORAGE_BACKEND: "
        f"{selected_backend!r}. Supported values: memory, dynamodb."
    )


# Initialize the application repositories once at import time.
storage = create_storage()

users = storage.users
doctors = storage.doctors
appointments = storage.appointments
doctor_account_provisioner = storage.doctor_account_provisioner


__all__ = [
    "storage",
    "users",
    "doctors",
    "appointments",
    "doctor_account_provisioner",
    "create_storage",
]
