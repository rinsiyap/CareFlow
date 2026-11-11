
"""
Central storage entry point for CareFlow.

The application currently uses in-memory repositories.
A configurable DynamoDB implementation will be introduced
without changing the API's business logic.
"""

from careflow_api.repositories import (
    appointments,
    doctor_account_provisioner,
    doctors,
    users,
)

__all__ = [
    "users",
    "doctors",
    "appointments",
    "doctor_account_provisioner",
]
