
import boto3
import pytest

from moto import mock_aws

from careflow_api.dynamodb_tables import (
    DEFAULT_TABLE_NAMES,
    create_dynamodb_tables,
)


@pytest.fixture
def dynamodb_resource():
    with mock_aws():
        resource = boto3.resource(
            "dynamodb",
            region_name="us-east-2",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        yield resource


def test_create_all_careflow_tables(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    assert set(tables.keys()) == {
        "users",
        "doctors",
        "appointments",
    }

    assert tables["users"].table_name == "CareFlow-Users"
    assert tables["doctors"].table_name == "CareFlow-Doctors"
    assert tables["appointments"].table_name == "CareFlow-Appointments"


def test_users_table_has_email_partition_key(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    description = tables["users"].table_status
    key_schema = tables["users"].key_schema

    assert description == "ACTIVE"
    assert key_schema == [
        {"AttributeName": "email", "KeyType": "HASH"},
    ]


def test_doctors_table_has_doctor_id_partition_key(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    assert tables["doctors"].table_status == "ACTIVE"
    assert tables["doctors"].key_schema == [
        {"AttributeName": "doctor_id", "KeyType": "HASH"},
    ]


def test_appointments_table_has_both_global_secondary_indexes(
    dynamodb_resource,
):
    tables = create_dynamodb_tables(dynamodb_resource)

    index_names = {
        index["IndexName"]
        for index in tables["appointments"].global_secondary_indexes
    }

    assert index_names == {
        "patient_email-scheduled_at-index",
        "doctor_id-scheduled_at-index",
    }


def test_table_creation_is_idempotent(dynamodb_resource):
    first = create_dynamodb_tables(dynamodb_resource)
    second = create_dynamodb_tables(dynamodb_resource)

    assert first["users"].table_name == second["users"].table_name
    assert first["doctors"].table_name == second["doctors"].table_name
    assert (
        first["appointments"].table_name
        == second["appointments"].table_name
    )


def test_custom_table_names_are_supported(dynamodb_resource):
    custom_names = {
        "users": "Test-CareFlow-Users",
        "doctors": "Test-CareFlow-Doctors",
        "appointments": "Test-CareFlow-Appointments",
    }

    tables = create_dynamodb_tables(
        dynamodb_resource,
        table_names=custom_names,
    )

    assert tables["users"].table_name == custom_names["users"]
    assert tables["doctors"].table_name == custom_names["doctors"]
    assert tables["appointments"].table_name == custom_names["appointments"]


def test_default_table_names_are_defined():
    assert DEFAULT_TABLE_NAMES == {
        "users": "CareFlow-Users",
        "doctors": "CareFlow-Doctors",
        "appointments": "CareFlow-Appointments",
    }
