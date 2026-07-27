# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the unified NukeSubmitter (deadline.nuke_submitter.submitter).

`nuke` and related modules are mocked in this package's __init__.py.

This module imports ``BaseSubmitter`` at load (via the submitter engine). Per the
Maya reference implementation (deadline-cloud-for-maya #435) it is deliberately
NOT skip-guarded, so it fails until a ``deadline`` release carrying
``BaseSubmitter`` (aws-deadline/deadline-cloud#1245) is installed, and passes once
it is.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import nuke
import pytest

from deadline.client.exceptions import DeadlineOperationError
from deadline.nuke_submitter.submitter import (
    NukeSubmitter,
    NukeSubmitterSettings,
)


@pytest.fixture(autouse=True)
def _reset_nuke_root():
    """Give nuke.root() sane return values for each test."""
    root = MagicMock()
    root.frameRange.return_value = "1-10"
    root.proxy.return_value = False
    nuke.root = MagicMock(return_value=root)
    yield


# ---------------------------------------------------------------------------
# get_settings — scene initialization
# ---------------------------------------------------------------------------


@patch(
    "deadline.nuke_submitter.submitter.get_nuke_script_file",
    return_value="/proj/scene.nk",
)
@patch(
    "deadline.nuke_submitter.submitter.get_project_path",
    return_value="/proj",
)
def test_get_settings_populates_from_scene(mock_project, mock_script):
    api = NukeSubmitter()

    settings = api.get_settings()

    assert isinstance(settings, NukeSubmitterSettings)
    assert settings.job_name == "scene.nk"
    assert settings.project_path == "/proj"
    # frame_list records the scene range, but override stays off by default so
    # the native path can fall back to a Write node's own use_limit range.
    assert settings.frame_list == "1-10"
    assert settings.override_frame_range is False
    assert settings.is_proxy_mode is False
    assert settings.input_filenames == ["/proj/scene.nk"]


@patch(
    "deadline.nuke_submitter.submitter.get_nuke_script_file",
    return_value="",
)
@patch(
    "deadline.nuke_submitter.submitter.get_project_path",
    return_value="",
)
def test_get_settings_untitled_when_no_script(mock_project, mock_script):
    api = NukeSubmitter()

    settings = api.get_settings()

    assert settings.job_name == "Untitled"
    assert settings.input_filenames == []


# ---------------------------------------------------------------------------
# get_job_template — builds the real template and injects host requirements.
# The builder is the public method itself (no separate staticmethod), so these
# run it end-to-end under the nuke/ocio mocks rather than mocking a builder.
# ---------------------------------------------------------------------------


@patch("deadline.nuke_submitter.submitter.nuke")
@patch("deadline.nuke_submitter.submitter.nuke_ocio")
@patch("deadline.nuke_submitter.submitter.find_all_write_nodes", return_value=[])
def test_get_job_template_without_host_requirements(mock_writes, mock_ocio, mock_nuke):
    mock_ocio.is_OCIO_enabled.return_value = False
    mock_nuke.views.return_value = []
    mock_nuke.root.return_value = MagicMock()

    template = NukeSubmitter().get_job_template(NukeSubmitterSettings())

    assert template["steps"]
    for step in template["steps"]:
        assert "hostRequirements" not in step


@patch("deadline.nuke_submitter.submitter.nuke")
@patch("deadline.nuke_submitter.submitter.nuke_ocio")
@patch("deadline.nuke_submitter.submitter.find_all_write_nodes", return_value=[])
def test_get_job_template_applies_host_requirements(mock_writes, mock_ocio, mock_nuke):
    mock_ocio.is_OCIO_enabled.return_value = False
    mock_nuke.views.return_value = []
    mock_nuke.root.return_value = MagicMock()
    host_req = {"attributes": [{"name": "attr.worker.os.family", "anyOf": ["linux"]}]}

    template = NukeSubmitter().get_job_template(NukeSubmitterSettings(), host_requirements=host_req)

    assert template["steps"]
    for step in template["steps"]:
        assert step["hostRequirements"] == host_req


# ---------------------------------------------------------------------------
# get_asset_references — returns the typed AssetReferences + scan diagnostics
# ---------------------------------------------------------------------------


@patch("deadline.nuke_submitter.submitter.get_scene_asset_references")
def test_get_asset_references_returns_typed_asset_references(mock_refs):
    from deadline.client.job_bundle.submission import AssetReferences

    scanned = AssetReferences(input_filenames={"/proj/scene.nk"})
    outcome = MagicMock()
    outcome.encountered_exception.return_value = False
    outcome.asset_references = scanned
    mock_refs.return_value = outcome

    api = NukeSubmitter()
    refs = api.get_asset_references(NukeSubmitterSettings())

    # Per the BaseSubmitter contract the method returns the typed object (not a
    # dict); the caller serializes with .to_dict() at the job-bundle boundary.
    assert isinstance(refs, AssetReferences)
    # With no explicit references on the settings, the scanned inputs pass through.
    assert refs.to_dict()["assetReferences"]["inputs"]["filenames"] == ["/proj/scene.nk"]


@patch("deadline.nuke_submitter.submitter.get_scene_asset_references")
def test_get_asset_references_merges_explicit_settings_references(mock_refs):
    from deadline.client.job_bundle.submission import AssetReferences

    # The scene scan finds the .nk file; the caller also supplies explicit
    # inputs/outputs on the settings (per the BaseSubmitterSettings contract).
    scanned = AssetReferences(input_filenames={"/proj/scene.nk"})
    outcome = MagicMock()
    outcome.encountered_exception.return_value = False
    outcome.asset_references = scanned
    mock_refs.return_value = outcome

    settings = NukeSubmitterSettings(
        input_filenames=["/proj/extra_input.exr"],
        input_directories=["/proj/textures"],
        output_directories=["/proj/renders"],
    )

    refs = NukeSubmitter().get_asset_references(settings)

    assert isinstance(refs, AssetReferences)
    inputs = refs.to_dict()["assetReferences"]["inputs"]
    outputs = refs.to_dict()["assetReferences"]["outputs"]
    # Scanned + explicit inputs are unioned (not dropped).
    assert set(inputs["filenames"]) == {"/proj/scene.nk", "/proj/extra_input.exr"}
    assert set(inputs["directories"]) == {"/proj/textures"}
    assert set(outputs["directories"]) == {"/proj/renders"}


@patch("deadline.nuke_submitter.submitter.get_scene_asset_references")
def test_get_asset_references_logs_scan_diagnostics(mock_refs, caplog):
    # A scan that hit problems must be surfaced (logged), not silently dropped.
    outcome = MagicMock()
    outcome.encountered_exception.return_value = True
    outcome.high_level_exception = "boom"
    outcome.failed_to_parse_nodes = {"Read1": "traceback..."}
    mock_refs.return_value = outcome

    api = NukeSubmitter()
    with caplog.at_level("WARNING"):
        api.get_asset_references(NukeSubmitterSettings())

    text = caplog.text
    assert "boom" in text
    assert "Read1" in text


# ---------------------------------------------------------------------------
# get_parameter_values consumes NukeSubmitterSettings directly (the inverted
# flow). These exercise the render logic that used to live in the GUI module.
# ---------------------------------------------------------------------------


@patch("deadline.nuke_submitter.submitter.nuke")
@patch("deadline.nuke_submitter.submitter.nuke_ocio")
@patch("deadline.nuke_submitter.submitter.get_nuke_script_file", return_value="/proj/scene.nk")
def test_parameter_values_from_settings(mock_script, mock_ocio, mock_nuke):
    mock_ocio.is_OCIO_enabled.return_value = False
    mock_nuke.root.return_value = MagicMock()
    mock_nuke.root.return_value.frameRange.return_value = "1-100"

    settings = NukeSubmitterSettings(
        override_frame_range=True,
        frame_list="1-50",
        view_selection="left",
        is_proxy_mode=True,
        continue_on_error=True,
    )

    values = NukeSubmitter().get_parameter_values(settings, queue_parameters=[])
    param_map = {p["name"]: p["value"] for p in values}

    assert param_map["Frames"] == "1-50"
    assert param_map["NukeScriptFile"] == "/proj/scene.nk"
    assert param_map["View"] == "left"
    assert param_map["ProxyMode"] == "true"
    assert param_map["ContinueOnError"] == "true"


@patch("deadline.nuke_submitter.submitter.nuke")
@patch("deadline.nuke_submitter.submitter.nuke_ocio")
@patch("deadline.nuke_submitter.submitter.get_nuke_script_file", return_value="/proj/scene.nk")
def test_parameter_values_queue_param_conflict_raises(mock_script, mock_ocio, mock_nuke):
    mock_ocio.is_OCIO_enabled.return_value = False
    mock_nuke.root.return_value = MagicMock()
    mock_nuke.root.return_value.frameRange.return_value = "1-100"

    settings = NukeSubmitterSettings(override_frame_range=True, frame_list="1")

    # "Frames" is a Nuke job parameter; a queue parameter of the same name must
    # raise rather than silently collide.
    with pytest.raises(DeadlineOperationError, match="conflict"):
        NukeSubmitter().get_parameter_values(
            settings, queue_parameters=[{"name": "Frames", "value": "1-5"}]
        )


@patch("deadline.nuke_submitter.submitter.nuke")
def test_get_frame_list_falls_back_to_write_node_use_limit(mock_nuke):
    from deadline.nuke_submitter.submitter import _get_frame_list

    mock_nuke.root.return_value.frameRange.return_value = "1-100"
    write_node = MagicMock()
    # use_limit on; first/last read as ints
    knobs = {"use_limit": MagicMock(), "first": MagicMock(), "last": MagicMock()}
    knobs["use_limit"].value.return_value = True
    knobs["first"].value.return_value = 5
    knobs["last"].value.return_value = 20
    write_node.knob.side_effect = lambda name: knobs[name]

    settings = NukeSubmitterSettings()  # override off
    result = _get_frame_list(settings, write_node, "Write1")

    # Write node use_limit range wins over the scene range when override is off.
    assert result == "5-20"


@patch("deadline.nuke_submitter.submitter.nuke")
def test_get_frame_list_honors_override_value(mock_nuke):
    from deadline.nuke_submitter.submitter import _get_frame_list

    mock_nuke.root.return_value.frameRange.return_value = "1-100"
    write_node = MagicMock()

    # Override on with an explicit range: the caller's value is used verbatim,
    # regardless of the scene / write-node range.
    settings = NukeSubmitterSettings(override_frame_range=True, frame_list="7-13")
    result = _get_frame_list(settings, write_node, "Write1")

    assert result == "7-13"


@patch("deadline.nuke_submitter.submitter.nuke")
def test_get_frame_list_override_on_but_empty_raises(mock_nuke):
    from deadline.nuke_submitter.submitter import _get_frame_list

    mock_nuke.root.return_value.frameRange.return_value = "1-100"
    write_node = MagicMock()

    # Override enabled but no range supplied is contradictory input: fail fast
    # with a clear error rather than silently rendering the whole scene range.
    settings = NukeSubmitterSettings(override_frame_range=True, frame_list="")
    with pytest.raises(DeadlineOperationError, match="Frame range override is enabled"):
        _get_frame_list(settings, write_node, "Write1")
