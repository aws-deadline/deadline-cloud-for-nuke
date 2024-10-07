# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import MagicMock, patch

import os
import nuke
import pytest

from deadline.nuke_util import ocio as nuke_ocio

from test.unit.mock_stubs import MockKnob, MockNode, MockOCIOConfig


@pytest.fixture()
def ocio_config() -> MockOCIOConfig:
    return MockOCIOConfig(
        working_dir="/this/ocio_configs", search_paths=["luts", "/my/absolute/luts"]
    )


@pytest.fixture()
def color_management_knob() -> MockKnob:
    return MockKnob("OCIO")


@pytest.fixture()
def ocio_config_knob() -> MockKnob:
    return MockKnob("custom")


@pytest.fixture()
def ocio_default_config_knob() -> MockKnob:
    return MockKnob("nuke-default")


@pytest.fixture()
def custom_ocio_config_path_knob() -> MockKnob:
    return MockKnob("/this/ocio_configs/config.ocio")


@pytest.fixture()
def default_ocio_config_path_knob() -> MockKnob:
    return MockKnob("/this/ocio_configs/nuke-default/config.ocio")


@pytest.fixture()
def root_node(
    color_management_knob: MockKnob,
    ocio_config_knob: MockKnob,
    custom_ocio_config_path_knob: MockKnob,
):
    knobs = {
        "colorManagement": color_management_knob,
        "OCIO_config": ocio_config_knob,
        "customOCIOConfigPath": custom_ocio_config_path_knob,
    }
    return MockNode(name="root", knobs=knobs, class_name="Root")


@pytest.fixture()
def root_node_with_default_ocio(
    color_management_knob: MockKnob,
    ocio_default_config_knob: MockKnob,
    default_ocio_config_path_knob: MockKnob,
):
    knobs = {
        "colorManagement": color_management_knob,
        "OCIO_config": ocio_default_config_knob,
        "OCIOConfigPath": default_ocio_config_path_knob,
    }
    return MockNode(name="root", knobs=knobs, class_name="Root")


@pytest.fixture(autouse=False)
def setup_nuke(root_node: MockNode) -> None:
    nuke.root.return_value = root_node


def test_is_custom_config_enabled(setup_nuke) -> None:
    # GIVEN (custom OCIO enabled)
    expected = True

    # WHEN
    actual = nuke_ocio.is_custom_config_enabled()

    # THEN
    assert expected == actual

    # GIVEN (OCIO disabled)
    nuke.root().knob("colorManagement").setValue("Nuke")
    expected = False

    # WHEN
    actual = nuke_ocio.is_custom_config_enabled()

    # THEN
    assert expected == actual

    # GIVEN (built-in OCIO enabled)
    nuke.root().knob("colorManagement").setValue("OCIO")
    nuke.root().knob("OCIO_config").setValue("nuke-default")
    expected = False

    # WHEN
    actual = nuke_ocio.is_custom_config_enabled()

    # THEN
    assert expected == actual


def test_get_custom_config_path(setup_nuke, custom_ocio_config_path_knob: MockKnob) -> None:
    # GIVEN
    expected = custom_ocio_config_path_knob.getEvaluatedValue()

    # WHEN
    actual = nuke_ocio.get_custom_config_path()

    # THEN
    assert expected == actual


@patch("PyOpenColorIO.Config.CreateFromFile")
def test_create_config_from_file(
    create_from_file: MagicMock, custom_ocio_config_path_knob: MockKnob
) -> None:
    # GIVEN
    custom_ocio_config_path = custom_ocio_config_path_knob.getEvaluatedValue()

    # WHEN
    nuke_ocio.create_config_from_file(custom_ocio_config_path)

    # ACTUAL
    create_from_file.assert_called_once_with(custom_ocio_config_path)


def test_config_has_absolute_search_paths(ocio_config: MockOCIOConfig) -> None:
    # GIVEN
    expected = True

    # WHEN
    actual = nuke_ocio.config_has_absolute_search_paths(ocio_config)

    # THEN
    assert expected == actual

    # GIVEN
    expected = False

    # WHEN
    ocio_config._search_paths = ["luts"]
    actual = nuke_ocio.config_has_absolute_search_paths(ocio_config)

    # THEN
    assert expected == actual


def test_get_config_absolute_search_paths(ocio_config: MockOCIOConfig) -> None:
    # GIVEN
    expected = [
        os.path.join(ocio_config.getWorkingDir(), search_path)
        for search_path in ocio_config.getSearchPaths()
    ]

    # WHEN
    actual = nuke_ocio.get_config_absolute_search_paths(ocio_config=ocio_config)

    # THEN
    assert expected == actual


def test_update_config_search_paths(ocio_config: MockOCIOConfig) -> None:
    # GIVEN
    search_paths = ["relative/path/to/luts", "/absolute/path/to/luts"]

    # WHEN
    nuke_ocio.update_config_search_paths(ocio_config=ocio_config, search_paths=search_paths)

    # THEN
    assert search_paths == ocio_config._search_paths


def test_set_custom_config_path(setup_nuke, custom_ocio_config_path_knob: MockKnob) -> None:
    # GIVEN
    ocio_config_path = "/nuke_temp_dir/temp_ocio_config.ocio"

    # WHEN
    nuke_ocio.set_custom_config_path(ocio_config_path=ocio_config_path)

    # THEN
    assert ocio_config_path == custom_ocio_config_path_knob.getEvaluatedValue()


def test_is_env_config_enabled_and_get_env_config_path() -> None:
    os.environ["OCIO"] = "not-empty"
    assert nuke_ocio.is_env_config_enabled() is True
    assert "not-empty" == nuke_ocio.get_env_config_path()

    os.environ.pop("OCIO")
    assert nuke_ocio.is_env_config_enabled() is False


def test_is_stock_config_enabled(root_node_with_default_ocio) -> None:
    nuke.root.return_value = root_node_with_default_ocio

    # GIVEN (default OCIO enabled)
    expected = True

    # WHEN
    actual = nuke_ocio.is_stock_config_enabled()

    # THEN
    assert expected == actual

    assert "/this/ocio_configs/nuke-default/config.ocio" == nuke_ocio.get_stock_config_path()

    # GIVEN (custom OCIO enabled)
    nuke.root().knob("colorManagement").setValue("OCIO")
    nuke.root().knob("OCIO_config").setValue("custom")

    # WHEN
    actual = nuke_ocio.is_stock_config_enabled()
    expected = False

    # THEN
    assert expected == actual


def test_is_OCIO_enabled(root_node_with_default_ocio, root_node) -> None:
    expected = True

    nuke.root.return_value = root_node_with_default_ocio
    actual = nuke_ocio.is_OCIO_enabled()
    assert expected == actual

    nuke.root.return_value = root_node
    actual = nuke_ocio.is_OCIO_enabled()
    assert expected == actual

    os.environ["OCIO"] = "not-empty"
    actual = nuke_ocio.is_OCIO_enabled()
    assert expected == actual


@patch("deadline.nuke_util.ocio.is_env_config_enabled", return_value=True)
@patch("deadline.nuke_util.ocio.is_custom_config_enabled", return_value=False)
@patch("deadline.nuke_util.ocio.is_stock_config_enabled", return_value=False)
@patch(
    "deadline.nuke_util.ocio.get_env_config_path",
    return_value="/this/ocio_configs/env_variable_config.ocio",
)
@patch(
    "deadline.nuke_util.ocio.get_custom_config_path",
    return_value="/this/ocio_configs/custom_config.ocio",
)
@patch(
    "deadline.nuke_util.ocio.get_stock_config_path",
    return_value="/this/ocio_configs/stock_config.ocio",
)
def test_get_ocio_config_path(
    mock_get_stock_config_path,
    mock_get_custom_config_path,
    mock_get_env_config_path,
    mock_is_stock_config_enabled,
    mock_is_custom_enabled,
    mock_is_env_config_enabled,
):
    env_variable_ocio_path = nuke_ocio.get_ocio_config_path()
    assert env_variable_ocio_path == "/this/ocio_configs/env_variable_config.ocio"

    mock_is_env_config_enabled.return_value = False
    mock_is_custom_enabled.return_value = True
    custom_ocio_path = nuke_ocio.get_ocio_config_path()
    assert custom_ocio_path == "/this/ocio_configs/custom_config.ocio"

    mock_is_env_config_enabled.return_value = False
    mock_is_custom_enabled.return_value = False
    mock_is_stock_config_enabled.return_value = True
    stock_ocio_path = nuke_ocio.get_ocio_config_path()
    assert stock_ocio_path == "/this/ocio_configs/stock_config.ocio"
