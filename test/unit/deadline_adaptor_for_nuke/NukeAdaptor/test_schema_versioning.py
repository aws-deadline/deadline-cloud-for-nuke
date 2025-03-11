# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deadline.nuke_adaptor.NukeAdaptor.adaptor import NukeAdaptor


@pytest.fixture
def init_data():
    """Fixture providing basic init data for the adaptor"""
    return {"script_file": "test.nk"}


def test_schema_matches_reference_version(init_data):
    """
    Test to validate that the schema matches the reference version.
    When schemas are modified, both the reference schemas AND the expected version
    should be updated together in this test.
    """
    # Define reference schemas that represent the current expected state
    REFERENCE_INIT_DATA_SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "continue_on_error": {"type": "boolean"},
            "proxy": {"type": "boolean"},
            "write_nodes": {"type": "array", "items": {"type": "string"}},
            "views": {"type": "array", "items": {"type": "string"}},
            "telemetry_opt_out": {"type": "boolean"},
            "script_file": {"type": "string"},
        },
        "required": ["script_file"],
    }

    REFERENCE_RUN_DATA_SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"frame": {"type": "number"}, "frameRange": {"type": "string"}},
        "optional": ["frameRange", "frame"],
    }

    # Expected version for these reference schemas
    EXPECTED_MAJOR = 0
    EXPECTED_MINOR = 1

    # Get the current version from the adaptor
    adaptor = NukeAdaptor(init_data)
    semantic_version = adaptor.integration_data_interface_version

    # Load current schemas
    root_directory_path = Path(__file__).parent.parent.parent.parent.parent
    schema_path = root_directory_path.joinpath(
        "src", "deadline", "nuke_adaptor", "NukeAdaptor", "schemas"
    )
    init_data_path = schema_path.joinpath("init_data.schema.json")
    run_data_path = schema_path.joinpath("run_data.schema.json")

    with init_data_path.open() as init_data_schema_file:
        current_init_data_schema = json.load(init_data_schema_file)

    with run_data_path.open() as run_data_schema_file:
        current_run_data_schema = json.load(run_data_schema_file)

    # Assert that the current schemas match the reference schemas
    assert current_init_data_schema == REFERENCE_INIT_DATA_SCHEMA, (
        "The init_data schema has changed. If this is intentional, please update both the "
        "reference schema in this test AND bump the integration_data_interface_version."
    )

    assert current_run_data_schema == REFERENCE_RUN_DATA_SCHEMA, (
        "The run_data schema has changed. If this is intentional, please update both the "
        "reference schema in this test AND bump the integration_data_interface_version."
    )

    # Assert that the version matches the expected version
    assert semantic_version.major == EXPECTED_MAJOR and semantic_version.minor == EXPECTED_MINOR, (
        f"Expected version {EXPECTED_MAJOR}.{EXPECTED_MINOR} but got "
        f"{semantic_version.major}.{semantic_version.minor}. When updating schemas, "
        "both the reference schemas AND the expected version should be updated together."
    )
