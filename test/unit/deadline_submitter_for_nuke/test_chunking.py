# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml  # type: ignore[import]

from deadline.nuke_submitter.data_classes import (
    RenderSettings,
    SubmitterUISettings,
)


class TestChunkingDataClasses:
    """Tests for chunking fields in RenderSettings and sticky settings."""

    def test_render_settings_chunking_defaults(self):
        settings = RenderSettings()
        assert settings.chunk_size == 1
        assert settings.target_chunk_duration == 0

    def test_sticky_settings_include_chunking_fields(self):
        settings = SubmitterUISettings()
        settings.jobtype_specific_settings = RenderSettings(
            chunk_size=25,
            target_chunk_duration=600,
        )

        result = settings._get_sticky_settings_dict()

        assert result["chunk_size"] == 25
        assert result["target_chunk_duration"] == 600

    def test_load_sticky_settings_with_chunking(self):
        settings = SubmitterUISettings()
        settings.jobtype_specific_settings = RenderSettings()

        settings._load_sticky_settings_from_dict(
            {
                "chunk_size": 50,
                "target_chunk_duration": 900,
            }
        )

        assert settings.jobtype_specific_settings.chunk_size == 50
        assert settings.jobtype_specific_settings.target_chunk_duration == 900

    def test_load_sticky_settings_without_chunking_keeps_defaults(self):
        settings = SubmitterUISettings()
        settings.jobtype_specific_settings = RenderSettings()

        settings._load_sticky_settings_from_dict({"name": "test"})

        assert settings.jobtype_specific_settings.chunk_size == 1
        assert settings.jobtype_specific_settings.target_chunk_duration == 0


class TestJobTemplate:
    """Tests for the job template with TASK_CHUNKING."""

    @pytest.fixture
    def template(self):
        template_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "deadline"
            / "nuke_submitter"
            / "default_nuke_job_template.yaml"
        )
        with open(template_path) as f:
            return yaml.safe_load(f)

    def test_template_has_task_chunking_extension(self, template):
        assert "TASK_CHUNKING" in template["extensions"]

    def test_template_has_chunk_int_frame_param(self, template):
        step = template["steps"][0]
        frame_param = step["parameterSpace"]["taskParameterDefinitions"][0]
        assert frame_param["name"] == "Frame"
        assert frame_param["type"] == "CHUNK[INT]"

    def test_template_has_contiguous_range_constraint(self, template):
        step = template["steps"][0]
        frame_param = step["parameterSpace"]["taskParameterDefinitions"][0]
        assert frame_param["chunks"]["rangeConstraint"] == "CONTIGUOUS"

    def test_template_has_chunking_params(self, template):
        param_names = [p["name"] for p in template["parameterDefinitions"]]
        assert "ChunkSize" in param_names
        assert "TargetChunkDuration" in param_names

    def test_template_chunk_size_defaults_to_1(self, template):
        chunk_size = next(p for p in template["parameterDefinitions"] if p["name"] == "ChunkSize")
        assert chunk_size["default"] == 1
        assert chunk_size["minValue"] == 1

    def test_template_target_duration_defaults_to_0(self, template):
        target = next(
            p for p in template["parameterDefinitions"] if p["name"] == "TargetChunkDuration"
        )
        assert target["default"] == 0
        assert target["minValue"] == 0

    def test_template_passes_frame_range_to_adaptor(self, template):
        step = template["steps"][0]
        run_data = step["script"]["embeddedFiles"][0]["data"]
        assert 'frameRange: "{{Task.Param.Frame}}"' in run_data


class TestSubmitterLogic:
    """Tests for parameter values with chunking."""

    @patch("deadline.nuke_submitter.submitter.get_project_path", return_value="/proj")
    @patch("deadline.nuke_submitter.submitter.nuke")
    @patch("deadline.nuke_submitter.submitter.nuke_ocio")
    @patch("deadline.nuke_submitter.submitter.get_nuke_script_file", return_value="/proj/scene.nk")
    def test_parameter_values_include_chunking(
        self, mock_script_file, mock_ocio, mock_nuke, mock_project
    ):
        from deadline.nuke_submitter.submitter import NukeSubmitter

        mock_ocio.is_OCIO_enabled.return_value = False
        mock_nuke.root.return_value = MagicMock()
        mock_nuke.root.return_value.frameRange.return_value = "1-100"

        # Drive the real settings the submitter produces, then set the chunking
        # fields the user would configure, rather than constructing settings by hand.
        submitter = NukeSubmitter()
        settings = submitter.get_settings()
        settings.chunk_size = 25
        settings.target_chunk_duration = 600

        param_values = submitter.get_parameter_values(settings, queue_parameters=[])

        param_map = {p["name"]: p["value"] for p in param_values}
        assert param_map["ChunkSize"] == 25
        assert param_map["TargetChunkDuration"] == 600

    @patch("deadline.nuke_submitter.submitter.nuke")
    @patch("deadline.nuke_submitter.submitter.nuke_ocio")
    @patch("deadline.nuke_submitter.submitter.get_nuke_script_file")
    def test_parameter_values_default_chunking(self, mock_script_file, mock_ocio, mock_nuke):
        """Default chunk_size=1 and target_chunk_duration=0 are always passed."""
        from deadline.nuke_submitter.submitter import NukeSubmitter, NukeSubmitterSettings

        mock_ocio.is_OCIO_enabled.return_value = False
        mock_nuke.root.return_value = MagicMock()
        mock_nuke.root.return_value.frameRange.return_value = "1-100"

        settings = NukeSubmitterSettings()

        param_values = NukeSubmitter().get_parameter_values(settings, queue_parameters=[])

        param_map = {p["name"]: p["value"] for p in param_values}
        assert param_map["ChunkSize"] == 1
        assert param_map["TargetChunkDuration"] == 0

    @patch("deadline.nuke_submitter.submitter.nuke")
    @patch("deadline.nuke_submitter.submitter.nuke_ocio")
    def test_get_job_template_has_task_chunking(self, mock_ocio, mock_nuke):
        """The single template should always have TASK_CHUNKING."""
        from deadline.nuke_submitter.submitter import NukeSubmitter, NukeSubmitterSettings

        mock_ocio.is_OCIO_enabled.return_value = False
        mock_nuke.views.return_value = []
        mock_nuke.root.return_value = MagicMock()

        settings = NukeSubmitterSettings()

        with patch(
            "deadline.nuke_submitter.submitter.find_all_write_nodes",
            return_value=[],
        ):
            template = NukeSubmitter().get_job_template(settings)

        assert "TASK_CHUNKING" in template.get("extensions", [])
