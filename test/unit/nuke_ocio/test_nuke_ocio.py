# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import MagicMock, call, patch

import os
import nuke
import pytest

from deadline import nuke_ocio

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
def custom_ocio_config_path_knob() -> MockKnob:
    return MockKnob("/this/ocio_configs/config.ocio")


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


@pytest.fixture(autouse=True)
def setup_nuke(root_node: MockNode) -> None:
    nuke.root.return_value = root_node


def test_is_custom_ocio_config_enabled() -> None:
    # GIVEN
    expected = True

    # WHEN
    actual = nuke_ocio.is_custom_ocio_config_enabled()

    # THEN
    assert expected == actual

    # GIVEN
    nuke.root().knob("colorManagement").setValue("Nuke")
    expected = False

    # WHEN
    actual = nuke_ocio.is_custom_ocio_config_enabled()

    # THEN
    assert expected == actual

    # GIVEN
    nuke.root().knob("colorManagement").setValue("OCIO")
    nuke.root().knob("OCIO_config").setValue("nuke-default")
    expected = False

    # WHEN
    actual = nuke_ocio.is_custom_ocio_config_enabled()

    # THEN
    assert expected == actual


def test_get_custom_ocio_config_path(custom_ocio_config_path_knob: MockKnob) -> None:
    # GIVEN
    expected = custom_ocio_config_path_knob.getEvaluatedValue()

    # WHEN
    actual = nuke_ocio.get_custom_ocio_config_path()

    # THEN
    assert expected == actual


@patch("PyOpenColorIO.Config.CreateFromFile")
def test_get_custom_ocio_config(
    create_from_file: MagicMock, custom_ocio_config_path_knob: MockKnob
) -> None:
    # GIVEN
    custom_ocio_config_path = custom_ocio_config_path_knob.getEvaluatedValue()

    # WHEN
    nuke_ocio.get_custom_ocio_config()

    # ACTUAL
    create_from_file.assert_called_once_with(custom_ocio_config_path)


def test_get_ocio_config_absolute_search_paths(ocio_config: MockOCIOConfig) -> None:
    # GIVEN
    expected = [
        os.path.join(ocio_config.getWorkingDir(), search_path)
        for search_path in ocio_config.getSearchPaths()
    ]

    # WHEN
    actual = nuke_ocio.get_ocio_config_absolute_search_paths(ocio_config)

    # THEN
    assert expected == actual
