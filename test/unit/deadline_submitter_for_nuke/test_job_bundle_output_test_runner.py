# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import pytest
from unittest.mock import patch

from deadline.nuke_submitter.job_bundle_output_test_runner import (
    _get_dcc_scene_file_extension,
    _open_dcc_scene_file,
    _close_dcc_scene_file,
    _sort,
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


test_sort_params = [
    ({}, []),
    ({"list": ["n2", "n1", "n3"]}, [("list", ["n1", "n2", "n3"])]),
    (
        {"name": "test_name", "list": ["n2", "n1", "n3"]},
        [("list", ["n1", "n2", "n3"]), ("name", "test_name")],
    ),
]


@pytest.mark.parametrize("test_dict, expected_dict", test_sort_params)
def test_sort(test_dict, expected_dict):
    # WHEN
    result = _sort(test_dict)

    # THEN
    assert expected_dict == result
