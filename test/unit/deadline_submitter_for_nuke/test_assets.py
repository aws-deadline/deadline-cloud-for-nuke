# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import nuke
import pytest

from deadline.client.exceptions import DeadlineOperationError
from deadline.nuke_submitter.assets import (
    find_all_write_nodes,
    get_input_paths_for_filenode,
    get_output_paths_for_filenode,
    IOPath,
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


@patch("deadline.nuke_submitter.assets.isfile", return_value=True)
@patch("deadline.nuke_submitter.assets.get_nuke_script_file", return_value="/this/scriptfile.nk")
@patch(
    "deadline.nuke_submitter.assets.get_input_paths_for_filenode",
    return_value=[
        IOPath(path="/one/asset.png", is_file=True),
        IOPath(path="/two/asset.png", is_file=True),
    ],
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
    expected_assets = [result.path for result in mock_get_node_filenames.return_value]
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
        (
            "path/to/file_with_no_frames.png",
            {IOPath(path="/project_path/path/to/file_with_no_frames.png", is_file=True)},
        ),
        (
            "path/to/file.####.hash",
            {
                IOPath(path="/project_path/path/to/file.0001.hash", is_file=True),
                IOPath(path="/project_path/path/to/file.0002.hash", is_file=True),
                IOPath(path="/project_path/path/to/file.0003.hash", is_file=True),
            },
        ),
        (
            "/path/to/frame.####/frame.png",
            {
                IOPath(path="/path/to/frame.0001/frame.png", is_file=True),
                IOPath(path="/path/to/frame.0002/frame.png", is_file=True),
                IOPath(path="/path/to/frame.0003/frame.png", is_file=True),
            },
        ),
        (
            "[some_tcl_expression of [stuff]]/path/to/frame.####/frame.png",
            {
                IOPath(path="/tcl_returned_path/path/to/frame.0001/frame.png", is_file=True),
                IOPath(path="/tcl_returned_path/path/to/frame.0002/frame.png", is_file=True),
                IOPath(path="/tcl_returned_path/path/to/frame.0003/frame.png", is_file=True),
            },
        ),
    ],
)
@patch("deadline.nuke_submitter.assets.nuke")
@patch("deadline.nuke_submitter.assets.get_project_path")
def test_get_input_paths_for_filenode(
    mock_get_project_path: Mock, mock_nuke: Mock, asset_path, formatted_paths
):
    # GIVEN
    mock_get_project_path.return_value = "/project_path"

    output_context = MagicMock()

    def update_frame(frame):
        output_context.frame = frame

    output_context.setFrame.side_effect = update_frame

    mock_nuke.OutputContext.return_value = output_context
    mock_nuke.views.return_value = "main"

    node = MagicMock()
    node.frameRange.return_value = [1, 2, 3]
    mock_path_knob = MagicMock()
    mock_path_knob.Class.return_value = "File_Knob"

    def evaluate_path(context):
        tcl_subbed = asset_path.replace("[some_tcl_expression of [stuff]]", "/tcl_returned_path")
        return tcl_subbed.replace("####", str(context.frame).zfill(4))

    mock_path_knob.getEvaluatedValue.side_effect = evaluate_path
    node.allKnobs.return_value = [mock_path_knob]

    # WHEN
    results = get_input_paths_for_filenode(node)

    results = {
        # fix windows pathing
        IOPath(path=result.path.replace("\\", "/"), is_file=result.is_file)
        for result in results
    }

    # THEN
    assert results == formatted_paths


@pytest.mark.parametrize(
    "asset_path,formatted_paths",
    [
        (
            "path/to/file_with_no_frames.png",
            {IOPath(path="/project_path/path/to/file_with_no_frames.png", is_file=True)},
        ),
        (
            "path/to/file.####.hash",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            "path/to/frame.##/frame.png",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            "./path/to/frame.##/frame.png",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            "path/views/%v/to/frame.##/frame.png",
            {IOPath(path="/project_path/path/views", is_file=False)},
        ),
        (
            "path/views/%V/to/frame.##/frame.png",
            {IOPath(path="/project_path/path/views", is_file=False)},
        ),
        (
            "path/to/frame_%05d/views/%v/frame.png",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            "[some_tcl_expression of [stuff]]/path/to/frame.##/frame.png",
            {IOPath(path="/tcl_returned_path/path/to", is_file=False)},
        ),
        (
            "path/to/frame.##/frame.png",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            r"path/to/file.%04d.formatting",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
        (
            r"path/to/file.%d.formatting",
            {IOPath(path="/project_path/path/to", is_file=False)},
        ),
    ],
)
@patch("deadline.nuke_submitter.assets.nuke")
@patch("deadline.nuke_submitter.assets.get_project_path")
def test_get_output_paths_for_filenode(
    mock_get_project_path: Mock, mock_nuke: Mock, asset_path, formatted_paths
):
    # GIVEN
    mock_get_project_path.return_value = "/project_path"

    mock_tcl = MagicMock()
    mock_tcl.return_value = "/tcl_returned_path"
    mock_nuke.tcl.return_value = mock_tcl()

    def sub_hashes(path):
        # mimicking that node.value() will replace hashes with equivalent %0nd syntax for frame subs
        return path.replace("####", "%04d").replace("##", "%02d")

    node = MagicMock()
    mock_path_knob = MagicMock()
    mock_path_knob.Class.return_value = "File_Knob"
    mock_path_knob.value.return_value = sub_hashes(asset_path)
    node.allKnobs.return_value = [mock_path_knob]

    # WHEN
    results = get_output_paths_for_filenode(node)

    results = {
        IOPath(path=result.path.replace("\\", "/"), is_file=result.is_file) for result in results
    }  # fix windows pathing

    # THEN
    assert results == formatted_paths
