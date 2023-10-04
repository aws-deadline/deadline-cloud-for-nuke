# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from unittest.mock import patch

from deadline.nuke_submitter.job_bundle_output_test_runner import (
    _get_dcc_scene_file_extension,
    _open_dcc_scene_file,
    _close_dcc_scene_file,
)


def test_get_dcc_main_window():
    assert ".nk" == _get_dcc_scene_file_extension()


@patch("nuke.scriptOpen")
def test_open_dcc_scene_file(mock_script_open):
    # GIVEN
    test_file_name = "sample.nk"

    # WHEN
    _open_dcc_scene_file(test_file_name)

    # THEN
    mock_script_open.assert_called_once_with(test_file_name)


@patch("nuke.scriptClose")
def test_close_dcc_scene_file(mock_script_close):
    # WHEN
    _close_dcc_scene_file()

    # THEN
    mock_script_close.assert_called_once()
