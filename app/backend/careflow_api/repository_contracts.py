
from typing import Any, Protocol, runtime_checkable


Record = dict[str, Any]


@runtime_checkable
class UserRepository(Protocol):
    """Storage contract for user accounts."""

    def get_by_email(self, email: str) -> Record | None:
        ...

    def create_user(self, user: Record) -> Record:
        ...


@runtime_checkable
class DoctorRepository(Protocol):
    """Storage contract for doctor profiles."""

    def get_by_id(self, doctor_id: str) -> Record | None:
        ...

    def create_doctor(self, doctor: Record) -> Record:
        ...

    def list_available(self) -> list[Record]:
        ...


@runtime_checkable
class AppointmentRepository(Protocol):
    """Storage contract for clinic appointments."""

    def create_appointment(self, appointment: Record) -> Record:
        ...

    def get_by_id(self, appointment_id: str) -> Record | None:
        ...

    def list_for_patient(self, patient_email: str) -> list[Record]:
        ...

    def list_for_doctor(self, doctor_id: str) -> list[Record]:
        ...

    def list_all(self) -> list[Record]:
        ...

    def transition_status(
        self,
        appointment_id: str,
        expected_status: str,
        new_status: str,
    ) -> Record | None:
        ...


@runtime_checkable
class DoctorAccountProvisioner(Protocol):
    """Contract for atomically linking a doctor profile to a login account."""

    def provision_doctor_account(
        self,
        doctor_id: str,
        user: Record,
    ) -> Record:
        ...
