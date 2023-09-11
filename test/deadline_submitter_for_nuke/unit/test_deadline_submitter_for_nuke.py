# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import List

import pytest

import dataclasses
import json
from json import JSONDecodeError
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import nuke

from deadline.nuke_submitter.deadline_submitter_for_nuke import (
    _get_sticky_settings_file,
    _load_sticky_settings,
    _save_sticky_settings,
    get_nuke_version,
    _get_write_node,
    _get_job_template,
    _get_parameter_values,
)
from deadline.nuke_submitter.data_classes.submission import (
    RenderSubmitterSettings,
    RenderSubmitterUISettings,
)
from .test_template_output.expected_job_template_output import EXPECTED_NUKE_JOB_TEMPLATE
from .test_template_output.expected_job_template_with_wheel_output import (
    EXPECTED_NUKE_JOB_TEMPLATE_WITH_WHEEL,
)

TEST_NUKE_VERSION = "13.2v1"
TEST_NUKE_SCRIPT_FILE_PATH = "/some/path.nk"
REZ_PACKAGE_DEFAULT = "nuke-13 deadline_cloud_for_nuke"


@pytest.fixture
def mock_nuke_file_path():
    with patch(
        "deadline.nuke_submitter.deadline_submitter_for_nuke.get_nuke_script_file",
        return_value=TEST_NUKE_SCRIPT_FILE_PATH,
    ) as m:
        yield m


@pytest.fixture
def mock_sticky_file_path():
    with patch(
        "deadline.nuke_submitter.deadline_submitter_for_nuke._get_sticky_settings_file",
        return_value=Path("/some/path.deadline_settings.json"),
    ) as m:
        yield m


@pytest.fixture
def mock_is_file():
    with patch("pathlib.Path.is_file", return_value=True) as m:
        yield m


@pytest.fixture
def mock_is_dir():
    with patch("pathlib.Path.is_dir", return_value=True) as m:
        yield m


@pytest.fixture
def mock_nuke_version():
    with patch(
        "deadline.nuke_submitter.deadline_submitter_for_nuke.get_nuke_version",
        return_value=TEST_NUKE_VERSION,
    ) as m:
        yield m


def _get_customized_settings() -> RenderSubmitterSettings:
    return RenderSubmitterSettings(
        name="TestName",
        description="TestDescription",
        override_rez_packages=False,
        rez_packages="",
        override_frame_range=True,
        frame_list="1-10:2",
        write_node_selection="TestWriteNode",
        view_selection="TestView",
        is_proxy_mode=True,
        initial_status="PAUSED",
        max_failed_tasks_count=0,
        max_retries_per_task=0,
        priority=51,
        input_directories=["/path/to/input"],
        output_directories=["/path/to/output"],
        input_filenames=["myrender.exr"],
        include_adaptor_wheels=False,
    )


@pytest.fixture
def base_parameters() -> List[dict]:
    return [
        {"name": "deadline:priority", "value": 51},
        {"name": "deadline:targetTaskRunStatus", "value": "PAUSED"},
        {"name": "deadline:maxFailedTasksCount", "value": 0},
        {"name": "deadline:maxRetriesPerTask", "value": 0},
    ]


@pytest.fixture
def customized_settings() -> RenderSubmitterSettings:
    return _get_customized_settings()


@pytest.fixture()
def mock_write_node():
    mock_write_node = MagicMock()
    mock_write_node.fullName.return_value = "TestWriteNode"
    mock_write_node.frameRange.return_value = "1-5"
    return mock_write_node


@pytest.fixture
def customized_ui_settings(mock_write_node) -> RenderSubmitterUISettings:
    settings = _get_customized_settings()
    ui_settings = RenderSubmitterUISettings(name="TestName")
    ui_settings.apply_saved_settings(settings)
    ui_settings.write_node_selection = mock_write_node
    return ui_settings


@pytest.fixture
def customized_ui_settings_no_write_node() -> RenderSubmitterUISettings:
    settings = _get_customized_settings()
    ui_settings = RenderSubmitterUISettings(name="TestName")
    ui_settings.apply_saved_settings(settings)
    ui_settings.write_node_selection = None
    return ui_settings


@pytest.fixture
def customized_ui_settings_root() -> RenderSubmitterUISettings:
    settings = _get_customized_settings()
    ui_settings = RenderSubmitterUISettings(name="TestName")
    ui_settings.apply_saved_settings(settings)
    ui_settings.write_node_selection = nuke.root()
    return ui_settings


@pytest.fixture
def mock_read_data(customized_settings) -> str:
    return json.dumps(dataclasses.asdict(customized_settings))


def test_get_sticky_settings_file(mock_nuke_file_path, mock_is_file):
    # This is a dummy test that just adds coverage, there are probably better ways to mock a file or create a test .nk
    # GIVEN
    expected_path = Path("/some/path.deadline_settings.json")

    # WHEN
    result = _get_sticky_settings_file()

    # THEN
    assert result == expected_path


@patch("deadline.nuke_submitter.deadline_submitter_for_nuke.get_nuke_script_file", return_value="")
def test_get_sticky_settings_file_no_script(mock_no_nuke_script_file):
    # THEN
    assert _get_sticky_settings_file() is None


@patch("pathlib.Path.is_file", return_value=False)
def test_get_sticky_settings_file_not_file(mock_path_is_not_file, mock_nuke_file_path):
    # THEN
    assert _get_sticky_settings_file() is None


def test_load_sticky_settings(mock_sticky_file_path, mock_is_file, customized_settings):
    # GIVEN
    read_data = json.dumps(dataclasses.asdict(customized_settings))

    # WHEN
    with patch("builtins.open", mock_open(read_data=read_data)):
        loaded_settings = _load_sticky_settings()

    # THEN
    assert loaded_settings is not None
    assert loaded_settings == customized_settings


@patch(
    "deadline.nuke_submitter.deadline_submitter_for_nuke._get_sticky_settings_file",
    return_value=None,
)
def test_load_sticky_settings_no_setting_file(mock_no_sticky_setting):
    # THEN
    assert _load_sticky_settings() is None


@patch("pathlib.Path.is_file", return_value=False)
def test_load_sticky_settings_not_file(mock_is_not_file, mock_sticky_file_path):
    # THEN
    assert _load_sticky_settings() is None


@patch("builtins.open", new_callable=mock_open)
def test_load_sticky_settings_os_error(mock_file, mock_sticky_file_path, mock_is_file):
    # GIVEN
    mock_file.side_effect = OSError()

    # THEN
    with pytest.raises(RuntimeError) as exc_info:
        _load_sticky_settings()

    assert str(exc_info.value) == "Failed to read from settings file"


@patch("builtins.open", new_callable=mock_open)
def test_load_sticky_settings_json_decode_error(mock_file, mock_sticky_file_path, mock_is_file):
    # GIVEN
    mock_file.side_effect = JSONDecodeError(msg="msg", doc="doc", pos=0)

    # THEN
    with pytest.raises(RuntimeError) as exc_info:
        _load_sticky_settings()

    assert str(exc_info.value) == "Failed to parse JSON from settings file"


@patch("builtins.open", new_callable=mock_open)
def test_load_sticky_settings_json_type_error(mock_file, mock_sticky_file_path, mock_is_file):
    # GIVEN
    mock_file.side_effect = TypeError()

    # THEN
    with pytest.raises(RuntimeError) as exc_info:
        _load_sticky_settings()

    assert str(exc_info.value) == "Failed to deserialize settings data"


def test_save_sticky_settings(mock_sticky_file_path, customized_ui_settings):
    # GIVEN
    expected_write_data = json.dumps(
        dataclasses.asdict(customized_ui_settings.to_render_submitter_settings()), indent=2
    )
    with patch("builtins.open", mock_open()) as mock_file:
        _save_sticky_settings(customized_ui_settings)
        mock_file.assert_called_with(
            Path("/some/path.deadline_settings.json"), "w", encoding="utf8"
        )
        handle = mock_file()
        handle.write.assert_called_with(expected_write_data)


@patch(
    "deadline.nuke_submitter.deadline_submitter_for_nuke._get_sticky_settings_file",
    return_value=None,
)
def test_save_sticky_settings_no_setting_file(mock_no_sticky_setting, customized_ui_settings):
    # THEN
    _save_sticky_settings(customized_ui_settings)
    mock_no_sticky_setting.assert_called_once()


@patch("builtins.open", new_callable=mock_open)
def test_save_sticky_settings_os_error(mock_file, mock_sticky_file_path, customized_ui_settings):
    # GIVEN
    mock_file.side_effect = OSError()

    # THEN
    with pytest.raises(RuntimeError) as exc_info:
        _save_sticky_settings(customized_ui_settings)

    assert str(exc_info.value) == "Failed to write to settings file"


def test_get_nuke_version():
    assert nuke.env["NukeVersionString"] == get_nuke_version()


def test_get_write_node_node_is_not_root(customized_ui_settings):
    result = _get_write_node(customized_ui_settings)
    assert "TestWriteNode" == result[1]


def test_get_write_node_node_is_root(customized_ui_settings_root):
    # WHEN
    result = _get_write_node(customized_ui_settings_root)

    # THEN
    assert "" == result[1]
    assert nuke.root() == result[0]


def test_get_write_node_node_is_none(customized_ui_settings_no_write_node):
    # WHEN
    result = _get_write_node(customized_ui_settings_no_write_node)

    # THEN
    assert "" == result[1]
    assert nuke.root() == result[0]


@patch(
    "deadline.nuke_submitter.deadline_submitter_for_nuke.find_all_write_nodes", return_value=set()
)
def test_get_job_template(mock_fall_all_node, mock_is_dir, customized_ui_settings):
    assert EXPECTED_NUKE_JOB_TEMPLATE == _get_job_template(customized_ui_settings)


@patch(
    "os.listdir",
    return_value=["openjd-wheel.whl", "deadline-wheel.whl", "deadline_cloud_for_nuke-wheel.whl"],
)
@patch(
    "deadline.nuke_submitter.deadline_submitter_for_nuke.find_all_write_nodes", return_value=set()
)
def test_get_job_template_with_wheel(
    mock_fall_all_node, mock_listdir, mock_is_dir, customized_ui_settings
):
    # GIVEN
    customized_ui_settings.include_adaptor_wheels = True

    # WHEN
    result = _get_job_template(customized_ui_settings)

    # override the default wheel directory filepath from the result for comparison since each os/workstation will
    # generate different path, and regex is too expensive for this comparison.
    result["parameterDefinitions"]
    for param in result["parameterDefinitions"]:
        if param["name"] == "AdaptorWheels":
            param["default"] = "/test/directory/deadline-cloud-for-nuke/wheels"

    # THEN
    assert EXPECTED_NUKE_JOB_TEMPLATE_WITH_WHEEL == result


def test_get_job_template_with_no_wheel_directories(customized_ui_settings):
    expected_info = "The Developer Option 'Include Adaptor Wheels' is enabled, but the wheels directory does not exist:"
    customized_ui_settings.include_adaptor_wheels = True

    # WHEN
    with pytest.raises(RuntimeError) as exc_info:
        _get_job_template(customized_ui_settings)

    # THEN
    assert expected_info in str(exc_info.value)


@patch("os.listdir", return_value=["openjd-wheel.whl"])
def test_get_job_template_with_missing_wheel_directories(
    mock_listdir, mock_is_dir, customized_ui_settings
):
    customized_ui_settings.include_adaptor_wheels = True

    # WHEN
    with pytest.raises(RuntimeError) as exc_info:
        _get_job_template(customized_ui_settings)

    # THEN
    assert str(exc_info.value) == (
        "The Developer Option 'Include Adaptor Wheels' is enabled, "
        "but the wheels directory contains the wrong wheels:\n"
        "Expected: openjd, deadline, and deadline_cloud_for_nuke\n"
        "Actual: {'openjd'}"
    )


def test_get_parameter_values(
    base_parameters, mock_nuke_file_path, mock_nuke_version, customized_ui_settings
):
    # GIVEN
    expected_parameter_values = base_parameters
    expected_parameter_values.append({"name": "Frames", "value": "1-10:2"})
    expected_parameter_values.append(
        {"name": "NukeScriptFile", "value": TEST_NUKE_SCRIPT_FILE_PATH}
    )
    expected_parameter_values.append({"name": "WriteNode", "value": "TestWriteNode"})
    expected_parameter_values.append({"name": "View", "value": "TestView"})
    expected_parameter_values.append({"name": "ProxyMode", "value": "true"})
    expected_parameter_values.append({"name": "NukeVersion", "value": TEST_NUKE_VERSION})

    expected_parameter_dict = {"parameterValues": expected_parameter_values}

    # WHEN
    result = _get_parameter_values(customized_ui_settings)

    # THEN
    assert expected_parameter_dict == result


def test_get_parameter_values_override_frame_range_false(
    base_parameters, mock_nuke_file_path, mock_nuke_version, customized_ui_settings
):
    expected_parameter_values = base_parameters
    expected_parameter_values.append({"name": "Frames", "value": "1-5"})
    expected_parameter_values.append(
        {"name": "NukeScriptFile", "value": TEST_NUKE_SCRIPT_FILE_PATH}
    )
    expected_parameter_values.append({"name": "WriteNode", "value": "TestWriteNode"})
    expected_parameter_values.append({"name": "View", "value": "TestView"})
    expected_parameter_values.append({"name": "ProxyMode", "value": "true"})
    expected_parameter_values.append({"name": "NukeVersion", "value": TEST_NUKE_VERSION})

    expected_parameter_dict = {"parameterValues": expected_parameter_values}

    settings = customized_ui_settings
    settings.override_frame_range = False

    # WHEN
    result = _get_parameter_values(settings)

    # THEN
    assert expected_parameter_dict == result


def test_get_parameter_values_no_write_node_name(
    base_parameters, mock_nuke_file_path, mock_nuke_version, customized_ui_settings_no_write_node
):
    expected_parameter_values = base_parameters
    expected_parameter_values.append({"name": "Frames", "value": "1-10:2"})
    expected_parameter_values.append(
        {"name": "NukeScriptFile", "value": TEST_NUKE_SCRIPT_FILE_PATH}
    )
    expected_parameter_values.append({"name": "View", "value": "TestView"})
    expected_parameter_values.append({"name": "ProxyMode", "value": "true"})
    expected_parameter_values.append({"name": "NukeVersion", "value": TEST_NUKE_VERSION})

    expected_parameter_dict = {"parameterValues": expected_parameter_values}

    # WHEN
    result = _get_parameter_values(customized_ui_settings_no_write_node)

    # THEN
    assert expected_parameter_dict == result


def test_get_parameter_values_no_view_selection(
    base_parameters, mock_nuke_file_path, mock_nuke_version, customized_ui_settings
):
    expected_parameter_values = base_parameters
    expected_parameter_values.append({"name": "Frames", "value": "1-10:2"})
    expected_parameter_values.append(
        {"name": "NukeScriptFile", "value": TEST_NUKE_SCRIPT_FILE_PATH}
    )
    expected_parameter_values.append({"name": "WriteNode", "value": "TestWriteNode"})
    expected_parameter_values.append({"name": "ProxyMode", "value": "true"})
    expected_parameter_values.append({"name": "NukeVersion", "value": TEST_NUKE_VERSION})

    expected_parameter_dict = {"parameterValues": expected_parameter_values}

    settings = customized_ui_settings
    settings.view_selection = None

    # WHEN
    result = _get_parameter_values(settings)

    # THEN
    assert expected_parameter_dict == result


def test_get_parameter_values_override_rez_packages(
    base_parameters, mock_nuke_file_path, mock_nuke_version, customized_ui_settings
):
    expected_parameter_values = base_parameters
    expected_parameter_values.append({"name": "Frames", "value": "1-10:2"})
    expected_parameter_values.append(
        {"name": "NukeScriptFile", "value": TEST_NUKE_SCRIPT_FILE_PATH}
    )
    expected_parameter_values.append({"name": "WriteNode", "value": "TestWriteNode"})
    expected_parameter_values.append({"name": "View", "value": "TestView"})
    expected_parameter_values.append({"name": "ProxyMode", "value": "true"})
    expected_parameter_values.append({"name": "NukeVersion", "value": TEST_NUKE_VERSION})
    expected_parameter_values.append({"name": "RezPackages", "value": REZ_PACKAGE_DEFAULT})

    expected_parameter_dict = {"parameterValues": expected_parameter_values}

    settings = customized_ui_settings
    settings.override_rez_packages = True
    settings.rez_packages = REZ_PACKAGE_DEFAULT

    # WHEN
    result = _get_parameter_values(settings)

    # THEN
    assert expected_parameter_dict == result
