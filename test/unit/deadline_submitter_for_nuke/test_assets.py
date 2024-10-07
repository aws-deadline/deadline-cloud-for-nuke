# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

import nuke
import pytest

from deadline.client.exceptions import DeadlineOperationError
from deadline.nuke_submitter.assets import (
    find_all_write_nodes,
    get_node_file_knob_paths,
    get_node_filenames,
    get_scene_asset_references,
)


def _activated_reading_write_node_knobs(knob_name: str):
    """Side effect function to allow knob() to return different values
    based on the knob name
    """
    false_knob = MagicMock()
    false_knob.value.return_value = False
    true_knob = MagicMock()
    true_knob.value.return_value = True
    knobs = {"disable": false_knob, "reading": true_knob}

    return knobs[knob_name]


@patch("os.path.isfile", return_value=True)
@patch("deadline.nuke_submitter.assets.get_nuke_script_file", return_value="/this/scriptfile.nk")
@patch(
    "deadline.nuke_submitter.assets.get_node_filenames",
    return_value=["/one/asset.png", "/two/asset.png"],
)
@patch("deadline.nuke_util.ocio.is_custom_config_enabled", return_value=False)
@patch("deadline.nuke_util.ocio.is_stock_config_enabled", return_value=False)
@patch("deadline.nuke_util.ocio.is_OCIO_enabled", return_value=False)
@patch(
    "deadline.nuke_util.ocio.get_custom_config_path",
    return_value="/this/ocio_configs/config.ocio",
)
@patch(
    "deadline.nuke_util.ocio.get_config_absolute_search_paths",
    return_value=["/this/ocio_configs/luts"],
)
def test_get_scene_asset_references(
    mock_get_config_absolute_search_paths: Mock,
    mock_get_custom_config_path: Mock,
    mock_is_OCIO_enabled: Mock,
    mock_is_stock_config_enabled: Mock,
    mock_is_custom_config_enabled: Mock,
    mock_get_node_filenames: Mock,
    mock_get_nuke_script_file: Mock,
    mock_path_isfile: Mock,
):
    # GIVEN
    expected_assets = mock_get_node_filenames.return_value
    expected_script_file = mock_get_nuke_script_file.return_value
    nuke.allNodes.return_value = []

    # WHEN
    results = get_scene_asset_references()

    # THEN
    assert results.input_filenames == {expected_script_file}
    assert results.input_directories == set()
    assert results.output_directories == set()

    # GIVEN
    deactivated_node = MagicMock()
    deactivated_node.knob("disable").value.return_value = True
    write_node = MagicMock()
    write_node.Class.return_value = "DeepWrite"
    write_node.knob("reading").value.return_value = False
    read_write_node = MagicMock()
    read_write_node.Class.return_value = "Write"
    read_write_node.knob.side_effect = _activated_reading_write_node_knobs

    nuke.allNodes.return_value = [
        deactivated_node,
        write_node,
        read_write_node,
    ]

    # WHEN
    results = get_scene_asset_references()

    # THEN
    assert expected_script_file in results.input_filenames
    assert all(asset in results.input_filenames for asset in expected_assets)

    # GIVEN
    expected_ocio_config_path = mock_get_custom_config_path.return_value
    expected_ocio_config_search_paths = mock_get_config_absolute_search_paths.return_value

    nuke.allNodes.return_value = []
    mock_is_custom_config_enabled.return_value = True
    mock_is_OCIO_enabled.return_value = True
    mock_is_stock_config_enabled.return_value = False

    # WHEN
    results = get_scene_asset_references()
    # THEN
    assert expected_script_file in results.input_filenames
    assert expected_ocio_config_path in results.input_filenames
    assert all(
        search_path in expected_ocio_config_search_paths
        for search_path in results.input_directories
    )


@patch("os.path.isfile", return_value=False)
@patch("deadline.nuke_submitter.assets.get_nuke_script_file", return_value="/this/scriptfile.nk")
def test_get_scene_asset_references_script_not_saved(
    mock_get_nuke_script_file: Mock, mock_path_isfile: Mock
):
    # GIVEN
    nuke.allNodes.return_value = []

    # WHEN
    with pytest.raises(DeadlineOperationError) as exc_info:
        get_scene_asset_references()

    # THEN
    error_msg = (
        "The Nuke Script is not saved to disk. Please save it before opening the submitter dialog."
    )
    assert str(exc_info.value) == error_msg


def test_find_all_write_nodes():
    # GIVEN
    nuke.allNodes.return_value = []
    # WHEN
    results = find_all_write_nodes()
    # THEN
    assert results == set()

    # GIVEN
    non_write_node = MagicMock()
    non_write_node.Class.return_value = "Not a Write Node Class"
    deactivated_write_node = MagicMock()
    deactivated_write_node.Class.return_value = "DeepWrite"
    deactivated_write_node.knob("disable").value.return_value = True
    read_node_disguised_as_write_node = MagicMock()
    read_node_disguised_as_write_node.Class.return_value = "Write"
    read_node_disguised_as_write_node.knob.side_effect = _activated_reading_write_node_knobs
    write_node = MagicMock()
    write_node.Class.return_value = "WriteGeo"
    write_node.knob("disable").value.return_value = False
    write_node.knob("reading").value.return_value = False

    nuke.allNodes.return_value = [
        non_write_node,
        deactivated_write_node,
        read_node_disguised_as_write_node,
        write_node,
    ]

    # WHEN
    results = find_all_write_nodes()

    # THEN
    assert all(
        node not in results
        for node in (non_write_node, deactivated_write_node, read_node_disguised_as_write_node)
    )
    assert write_node in results


@pytest.mark.parametrize(
    "asset_path,formatted_paths",
    [
        ("/path/to/file_with_no_frames.png", {"/path/to/file_with_no_frames.png"}),
        (
            "/path/to/file.####.hash",
            {
                "/path/to/file.0000.hash",
                "/path/to/file.0001.hash",
                "/path/to/file.0002.hash",
                "/path/to/file.0100.hash",
            },
        ),
        (
            "/path/to/file.#.hash",
            {
                "/path/to/file.0.hash",
                "/path/to/file.1.hash",
                "/path/to/file.2.hash",
                "/path/to/file.100.hash",
            },
        ),
        (
            r"/path/to/file.%04d.formatting",
            {
                "/path/to/file.0000.formatting",
                "/path/to/file.0001.formatting",
                "/path/to/file.0002.formatting",
                "/path/to/file.0100.formatting",
            },
        ),
        (
            r"/path/to/file.%d.formatting",
            {
                "/path/to/file.0.formatting",
                "/path/to/file.1.formatting",
                "/path/to/file.2.formatting",
                "/path/to/file.100.formatting",
            },
        ),
    ],
)
@patch("deadline.nuke_submitter.assets.get_node_file_knob_paths")
def test_get_node_filenames(mock_get_node_file_knob_paths: Mock, asset_path, formatted_paths):
    # GIVEN
    node_filepaths = [asset_path]
    mock_get_node_file_knob_paths.side_effect = lambda node: (path for path in node_filepaths)
    node = MagicMock()
    node.frameRange.return_value = [0, 1, 2, 100]

    # WHEN
    results = get_node_filenames(node)

    # THEN
    assert results == formatted_paths


@patch("deadline.nuke_submitter.assets.get_project_path")
def test_get_node_file_knob_paths(mock_project_path: Mock):
    # GIVEN
    mock_project_path.return_value = os.path.join("project", "path")
    mock_other_knob = MagicMock()
    mock_other_knob.Class.return_value = "NotAFileKnob"

    mock_tcl_file_knob = MagicMock()
    mock_tcl_file_knob.Class.return_value = "File_Knob"
    mock_tcl_file_knob.value.return_value = "[this is a tcl expression]"
    mock_tcl_file_knob.getEvaluatedValue.return_value = os.path.join("evaluated", "tcl", "path")

    mock_file_knob = MagicMock()
    mock_file_knob.Class.return_value = "File_Knob"
    mock_file_knob.value.return_value = os.path.join("this", "is", "a", "path")
    mock_node = MagicMock()
    mock_node.allKnobs.return_value = []

    # WHEN
    results = get_node_file_knob_paths(mock_node)
    # THEN
    with pytest.raises(StopIteration):
        next(results)

    # GIVEN
    mock_node.allKnobs.return_value = [
        mock_other_knob,
        mock_tcl_file_knob,
        mock_file_knob,
    ]
    mock_node.reset_mock()

    # WHEN
    results = get_node_file_knob_paths(mock_node)

    # THEN
    assert next(results) == os.path.join(
        mock_project_path(), mock_tcl_file_knob.getEvaluatedValue()
    )
    assert next(results) == os.path.join(mock_project_path(), mock_file_knob.value())
