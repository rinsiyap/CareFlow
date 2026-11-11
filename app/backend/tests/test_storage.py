
import pytest

from careflow_api import storage as storage_module
from careflow_api.repositories import (
    appointments as memory_appointments,
    doctor_account_provisioner as memory_provisioner,
    doctors as memory_doctors,
    users as memory_users,
)


def test_default_storage_uses_memory_backend(monkeypatch):
    monkeypatch.delenv("CARE_FLOW_STORAGE_BACKEND", raising=False)

    storage = storage_module.create_storage()

    assert storage.users is memory_users
    assert storage.doctors is memory_doctors
    assert storage.appointments is memory_appointments
    assert storage.doctor_account_provisioner is memory_provisioner


def test_explicit_memory_backend():
    storage = storage_module.create_storage(backend="memory")

    assert storage.users is memory_users
    assert storage.doctors is memory_doctors
    assert storage.appointments is memory_appointments


def test_backend_selection_is_case_insensitive():
    storage = storage_module.create_storage(backend="MEMORY")

    assert storage.users is memory_users


def test_invalid_backend_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported"):
        storage_module.create_storage(backend="postgres")


def test_environment_selects_memory_backend(monkeypatch):
    monkeypatch.setenv("CARE_FLOW_STORAGE_BACKEND", "memory")

    storage = storage_module.create_storage()

    assert storage.users is memory_users


def test_memory_storage_health_check():
    storage = storage_module.create_storage(backend="memory")

    result = storage.health_check()

    assert result == {
        "status": "connected",
        "backend": "memory",
    }


def test_memory_storage_reports_backend():
    storage = storage_module.create_storage(backend="memory")

    assert storage.backend == "memory"
    