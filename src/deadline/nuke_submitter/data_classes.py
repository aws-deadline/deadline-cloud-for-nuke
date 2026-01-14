# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, is_dataclass
import json
from pathlib import Path
from typing import Union, Dict, Any
from enum import Enum

RENDER_SUBMITTER_SETTINGS_FILE_EXT = ".deadline_render_settings.json"
COPYCAT_SUBMITTER_SETTINGS_FILE_EXT = ".deadline_copycat_settings.json"


class JobType(Enum):
    RENDER = "render"
    COPYCAT_TRAINING = "copycat_training"


@dataclass
class RenderSettings:
    override_frame_range: bool = field(default=False, metadata={"sticky": True})
    frame_list: str = field(default="", metadata={"sticky": True})
    write_node_selection: str = field(default="", metadata={"sticky": True})
    view_selection: str = field(default="", metadata={"sticky": True})
    is_proxy_mode: bool = field(default=False, metadata={"sticky": True})
    continue_on_error: bool = field(default=False, metadata={"sticky": True})


@dataclass
class CopyCatTrainingSettings:
    copycat_node: str = field(default="", metadata={"sticky": True})


@dataclass
class SubmitterUISettings:  # pylint: disable=too-many-instance-attributes
    """
    Settings that the submitter UI will use
    """

    submitter_name: str = field(default="Nuke")

    name: str = field(default="", metadata={"sticky": True})
    description: str = field(default="", metadata={"sticky": True})

    jobtype_specific_settings: Union[CopyCatTrainingSettings, RenderSettings] = field(
        default_factory=RenderSettings, metadata={"sticky": True}
    )

    input_filenames: list[str] = field(default_factory=list, metadata={"sticky": True})
    input_directories: list[str] = field(default_factory=list, metadata={"sticky": True})
    output_directories: list[str] = field(default_factory=list, metadata={"sticky": True})

    timeouts_enabled: bool = field(default=True, metadata={"sticky": True})
    on_run_timeout_seconds: int = field(default=518400, metadata={"sticky": True})  # 6 days
    on_enter_timeout_seconds: int = field(default=86400, metadata={"sticky": True})  # 1 day
    on_exit_timeout_seconds: int = field(default=3600, metadata={"sticky": True})  # 1 hour

    include_gizmos_in_job_bundle: bool = field(default=False, metadata={"sticky": True})

    # developer options
    include_adaptor_wheels: bool = field(default=False, metadata={"sticky": True})

    def get_job_type(self):
        return (
            JobType.RENDER
            if type(self.jobtype_specific_settings) is RenderSettings
            else JobType.COPYCAT_TRAINING
        )

    def _load_sticky_settings_from_dict(self, sticky_settings: dict):
        if isinstance(sticky_settings, dict):
            sticky_fields = {
                field.name: field
                for field in dataclasses.fields(self)
                if field.metadata.get("sticky")
            }
            jobtype_specific_sticky_fields = {
                field.name: field
                for field in dataclasses.fields(self.jobtype_specific_settings)
                if field.metadata.get("sticky")
            }
            for name, value in sticky_settings.items():
                # Only set fields that are defined in the dataclass
                if name in sticky_fields:
                    setattr(self, name, value)
                if name in jobtype_specific_sticky_fields:
                    setattr(self.jobtype_specific_settings, name, value)

    def load_sticky_settings(self, scene_filename: str):
        sticky_settings_filename = Path(scene_filename).with_suffix(
            RENDER_SUBMITTER_SETTINGS_FILE_EXT
            if self.get_job_type() == JobType.RENDER
            else COPYCAT_SUBMITTER_SETTINGS_FILE_EXT
        )
        if sticky_settings_filename.exists() and sticky_settings_filename.is_file():
            try:
                with open(sticky_settings_filename, encoding="utf8") as fh:
                    sticky_settings = json.load(fh)
                self._load_sticky_settings_from_dict(sticky_settings)
            except (OSError, json.JSONDecodeError):
                # If something bad happened to the sticky settings file,
                # just use the defaults instead of producing an error.
                import traceback

                traceback.print_exc()
                print(
                    f"WARNING: Failed to load sticky settings file {sticky_settings_filename}, reverting to the default settings."
                )

    def _get_sticky_settings_dict(self) -> Dict[str, Any]:
        # flattening makes this more complicated, but is necessary for backwards compatibility
        def get_flat_dict_of_sticky_attributes(obj) -> Dict[str, Any]:
            output = {}

            for attr_field in dataclasses.fields(obj):
                if not attr_field.metadata.get("sticky"):
                    continue

                attr = getattr(obj, attr_field.name)
                if is_dataclass(attr):
                    flattened = get_flat_dict_of_sticky_attributes(attr)
                    for k, v in flattened.items():
                        output[k] = v
                else:
                    output[attr_field.name] = attr

            return output

        return get_flat_dict_of_sticky_attributes(self)

    def save_sticky_settings(self, scene_filename: str):
        sticky_settings_filename = Path(scene_filename).with_suffix(
            RENDER_SUBMITTER_SETTINGS_FILE_EXT
            if self.get_job_type() == JobType.RENDER
            else COPYCAT_SUBMITTER_SETTINGS_FILE_EXT
        )

        with open(sticky_settings_filename, "w", encoding="utf8") as fh:
            obj = self._get_sticky_settings_dict()
            json.dump(obj, fh, indent=1)
