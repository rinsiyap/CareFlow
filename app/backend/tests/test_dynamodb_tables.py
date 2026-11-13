
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
        "outbox",
        "processed_events",
    }

    assert tables["users"].table_name == "CareFlow-Users"
    assert tables["doctors"].table_name == "CareFlow-Doctors"
    assert tables["appointments"].table_name == "CareFlow-Appointments"
    assert tables["outbox"].table_name == "CareFlow-Outbox"
    assert (
        tables["processed_events"].table_name
        == "CareFlow-ProcessedEvents"
    )


def test_users_table_has_email_partition_key(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    assert tables["users"].table_status == "ACTIVE"
    assert tables["users"].key_schema == [
        {"AttributeName": "email", "KeyType": "HASH"}
    ]


def test_doctors_table_has_doctor_id_partition_key(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    assert tables["doctors"].table_status == "ACTIVE"
    assert tables["doctors"].key_schema == [
        {"AttributeName": "doctor_id", "KeyType": "HASH"}
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


def test_outbox_table_has_event_id_partition_key(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    assert tables["outbox"].table_status == "ACTIVE"
    assert tables["outbox"].key_schema == [
        {"AttributeName": "event_id", "KeyType": "HASH"}
    ]


def test_outbox_table_has_status_created_at_index(dynamodb_resource):
    tables = create_dynamodb_tables(dynamodb_resource)

    indexes = tables["outbox"].global_secondary_indexes

    assert len(indexes) == 1

    index = indexes[0]

    assert index["IndexName"] == "status-created_at-index"
    assert index["KeySchema"] == [
        {"AttributeName": "status", "KeyType": "HASH"},
        {"AttributeName": "created_at", "KeyType": "RANGE"},
    ]
    assert index["Projection"]["ProjectionType"] == "ALL"


def test_processed_events_table_has_event_id_partition_key(
    dynamodb_resource,
):
    tables = create_dynamodb_tables(dynamodb_resource)

    table = tables["processed_events"]

    assert table.table_status == "ACTIVE"
    assert table.key_schema == [
        {"AttributeName": "event_id", "KeyType": "HASH"}
    ]
    assert table.global_secondary_indexes == []


def test_processed_events_table_uses_on_demand_billing(
    dynamodb_resource,
):
    tables = create_dynamodb_tables(dynamodb_resource)

    description = dynamodb_resource.meta.client.describe_table(
        TableName=tables["processed_events"].table_name,
    )

    assert description["Table"]["BillingModeSummary"]["BillingMode"] == (
        "PAY_PER_REQUEST"
    )


def test_table_creation_is_idempotent(dynamodb_resource):
    first = create_dynamodb_tables(dynamodb_resource)
    second = create_dynamodb_tables(dynamodb_resource)

    for key in DEFAULT_TABLE_NAMES:
        assert first[key].table_name == second[key].table_name


def test_custom_table_names_are_supported(dynamodb_resource):
    custom_names = {
        "users": "Test-CareFlow-Users",
        "doctors": "Test-CareFlow-Doctors",
        "appointments": "Test-CareFlow-Appointments",
        "outbox": "Test-CareFlow-Outbox",
        "processed_events": "Test-CareFlow-ProcessedEvents",
    }

    tables = create_dynamodb_tables(
        dynamodb_resource,
        table_names=custom_names,
    )

    for key, expected_name in custom_names.items():
        assert tables[key].table_name == expected_name


def test_default_table_names_are_defined():
    assert DEFAULT_TABLE_NAMES == {
        "users": "CareFlow-Users",
        "doctors": "CareFlow-Doctors",
        "appointments": "CareFlow-Appointments",
        "outbox": "CareFlow-Outbox",
        "processed_events": "CareFlow-ProcessedEvents",
    }
