
from collections.abc import Iterator, MutableMapping
from typing import Any

from careflow_api.repository_contracts import (
    AppointmentRepository,
    DoctorAccountProvisioner,
    DoctorRepository,
    UserRepository,
)


Record = dict[str, Any]


class InMemoryRepository(MutableMapping[str, Record]):
    """
    Dictionary-compatible in-memory storage.

    Provides generic operations while preserving compatibility
    with existing tests and local development.
    """

    def __init__(self) -> None:
        self._items: dict[str, Record] = {}

    # ---------------------------------------------------------
    # Dictionary compatibility
    # ---------------------------------------------------------

    def __getitem__(self, key: str) -> Record:
        return self._items[key]

    def __setitem__(self, key: str, value: Record) -> None:
        self._items[key] = value

    def __delitem__(self, key: str) -> None:
        del self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    # ---------------------------------------------------------
    # Generic storage operations
    # ---------------------------------------------------------

    def get_record(self, record_id: str) -> Record | None:
        return self._items.get(record_id)

    def create_record(self, record_id: str, record: Record) -> Record:
        if record_id in self._items:
            raise ValueError(f"Record already exists: {record_id}")

        self._items[record_id] = record
        return record

    def list_records(self) -> list[Record]:
        return list(self._items.values())

    def find_one_by_field(
        self,
        field: str,
        value: Any,
    ) -> Record | None:
        return next(
            (
                record
                for record in self._items.values()
                if record.get(field) == value
            ),
            None,
        )

    def find_many_by_field(
        self,
        field: str,
        value: Any,
    ) -> list[Record]:
        return [
            record
            for record in self._items.values()
            if record.get(field) == value
        ]

    def update_record_field(
        self,
        record_id: str,
        field: str,
        value: Any,
    ) -> Record | None:
        record = self._items.get(record_id)

        if record is None:
            return None

        record[field] = value
        return record


# =============================================================
# USER REPOSITORY
# =============================================================

class InMemoryUserRepository(InMemoryRepository):
    """In-memory implementation of UserRepository."""

    def get_by_email(self, email: str) -> Record | None:
        return self.get_record(email)

    def create_user(self, user: Record) -> Record:
        email = user["email"]
        return self.create_record(email, user)


# =============================================================
# DOCTOR REPOSITORY
# =============================================================

class InMemoryDoctorRepository(InMemoryRepository):
    """In-memory implementation of DoctorRepository."""

    def get_by_id(self, doctor_id: str) -> Record | None:
        return self.get_record(doctor_id)

    def create_doctor(self, doctor: Record) -> Record:
        doctor_id = doctor["id"]
        return self.create_record(doctor_id, doctor)

    def list_available(self) -> list[Record]:
        return [
            doctor
            for doctor in self.list_records()
            if doctor.get("available", False)
        ]


# =============================================================
# APPOINTMENT REPOSITORY
# =============================================================

class InMemoryAppointmentRepository(InMemoryRepository):
    """In-memory implementation of AppointmentRepository."""

    def create_appointment(self, appointment: Record) -> Record:
        appointment_id = appointment["id"]
        return self.create_record(appointment_id, appointment)

    def get_by_id(self, appointment_id: str) -> Record | None:
        return self.get_record(appointment_id)

    def list_for_patient(self, patient_email: str) -> list[Record]:
        return self.find_many_by_field(
            "patient_email",
            patient_email,
        )

    def list_for_doctor(self, doctor_id: str) -> list[Record]:
        return self.find_many_by_field(
            "doctor_id",
            doctor_id,
        )

    def list_all(self) -> list[Record]:
        return self.list_records()

    def transition_status(
        self,
        appointment_id: str,
        expected_status: str,
        new_status: str,
    ) -> Record | None:
        """
        Update status only if the current status matches
        the expected status.

        This mirrors the conditional-update behavior that
        will be implemented using DynamoDB condition expressions.
        """

        appointment = self.get_by_id(appointment_id)

        if appointment is None:
            return None

        if appointment["status"] != expected_status:
            return None

        appointment["status"] = new_status
        return appointment


# =============================================================
# DOCTOR ACCOUNT PROVISIONER
# =============================================================

class InMemoryDoctorAccountProvisioner:
    """
    In-memory implementation of DoctorAccountProvisioner.

    Creates a doctor login account and links its email to
    the doctor profile.

    This operation is synchronous and executes without an
    asynchronous interruption in the local implementation.
    The DynamoDB implementation will use TransactWriteItems
    to provide atomicity across both records.
    """

    def __init__(
        self,
        users: InMemoryUserRepository,
        doctors: InMemoryDoctorRepository,
    ) -> None:
        self.users = users
        self.doctors = doctors

    def provision_doctor_account(
        self,
        doctor_id: str,
        user: Record,
    ) -> Record:

        doctor = self.doctors.get_by_id(doctor_id)

        if doctor is None:
            raise ValueError("Doctor not found")

        email = user["email"]

        if self.users.get_by_email(email) is not None:
            raise ValueError(
                "An account with this email already exists"
            )

        if doctor.get("account_email"):
            raise ValueError(
                "This doctor already has a login account"
            )

        if user.get("doctor_id") != doctor_id:
            raise ValueError(
                "Doctor account is not linked to the correct profile"
            )

        self.users.create_user(user)
        doctor["account_email"] = email

        return user


# =============================================================
# LOCAL REPOSITORY INSTANCES
# =============================================================

users = InMemoryUserRepository()
doctors = InMemoryDoctorRepository()
appointments = InMemoryAppointmentRepository()

doctor_account_provisioner = InMemoryDoctorAccountProvisioner(
    users=users,
    doctors=doctors,
)
