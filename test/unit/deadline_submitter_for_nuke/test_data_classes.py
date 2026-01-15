# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from deadline.nuke_submitter.data_classes import (
    SubmitterUISettings,
    RenderSettings,
    CopyCatTrainingSettings,
)


class TestSubmitterUISettings:
    @pytest.mark.parametrize(
        "job_type,settings_class,specific_settings",
        [
            (
                "render",
                RenderSettings,
                {
                    "override_frame_range": True,
                    "frame_list": "1-10",
                    "write_node_selection": "",
                    "view_selection": "",
                    "is_proxy_mode": False,
                    "continue_on_error": False,
                },
            ),
            (
                "copycat",
                CopyCatTrainingSettings,
                {
                    "copycat_node": "test_node",
                },
            ),
        ],
    )
    def test_get_sticky_settings_dict(self, job_type, settings_class, specific_settings):
        """Test that sticky settings are correctly serialized to a dictionary."""
        settings = SubmitterUISettings()
        settings.jobtype_specific_settings = settings_class()
        settings.name = "test_job"
        settings.description = "test description"

        # Set job-specific settings
        for key, value in specific_settings.items():
            setattr(settings.jobtype_specific_settings, key, value)

        result = settings._get_sticky_settings_dict()

        # Common settings should always be present
        assert result["name"] == "test_job"
        assert result["description"] == "test description"
        assert result["input_filenames"] == []
        assert result["input_directories"] == []
        assert result["output_directories"] == []
        assert result["timeouts_enabled"] is True
        assert result["on_run_timeout_seconds"] == 518400
        assert result["on_enter_timeout_seconds"] == 86400
        assert result["on_exit_timeout_seconds"] == 3600
        assert result["include_gizmos_in_job_bundle"] is False
        assert result["include_adaptor_wheels"] is False

        # Job-specific settings should be present
        for key, value in specific_settings.items():
            assert result[key] == value

    @pytest.mark.parametrize(
        "job_type,settings_class,sticky_data",
        [
            (
                "render",
                RenderSettings,
                {
                    "name": "loaded_job",
                    "description": "loaded description",
                    "override_frame_range": True,
                    "frame_list": "5-15",
                    "timeouts_enabled": False,
                    "include_gizmos_in_job_bundle": True,
                },
            ),
            (
                "copycat",
                CopyCatTrainingSettings,
                {
                    "name": "copycat_job",
                    "description": "copycat description",
                    "copycat_node": "test_copycat_node",
                    "timeouts_enabled": False,
                },
            ),
        ],
    )
    def test_load_sticky_settings_from_dict(self, job_type, settings_class, sticky_data):
        """Test that sticky settings are correctly loaded from a dictionary."""
        settings = SubmitterUISettings()
        settings.jobtype_specific_settings = settings_class()

        settings._load_sticky_settings_from_dict(sticky_data)

        # Check common settings
        for key in ["name", "description", "timeouts_enabled", "include_gizmos_in_job_bundle"]:
            if key in sticky_data:
                assert getattr(settings, key) == sticky_data[key]

        # Check job-specific settings
        for key in sticky_data:
            if hasattr(settings.jobtype_specific_settings, key):
                assert getattr(settings.jobtype_specific_settings, key) == sticky_data[key]

    def test_load_sticky_settings_ignores_non_sticky_fields(self):
        """Test that non-sticky fields are ignored when loading from dictionary."""
        settings = SubmitterUISettings()
        original_submitter_name = settings.submitter_name

        sticky_data = {
            "name": "test_job",
            "submitter_name": "should_be_ignored",  # non-sticky field
            "unknown_field": "should_be_ignored",  # unknown field
        }

        settings._load_sticky_settings_from_dict(sticky_data)

        assert settings.name == "test_job"
        assert settings.submitter_name == original_submitter_name  # unchanged

    def test_get_sticky_settings_dict_excludes_non_sticky_fields(self):
        """Test that non-sticky fields are excluded from the settings dictionary."""
        settings = SubmitterUISettings()
        settings.submitter_name = "CustomSubmitter"  # non-sticky field
        settings.name = "test_job"  # sticky field

        result = settings._get_sticky_settings_dict()

        assert "name" in result
        assert "submitter_name" not in result
