# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import dataclasses
import json
import traceback
from pathlib import Path
from typing import Any, Optional
import yaml  # type: ignore[import]

import nuke
from deadline.client.job_bundle import deadline_yaml_dump
from deadline.client.ui import gui_error_handler
from deadline.client.ui.dialogs.submit_job_to_deadline_dialog import (  # type: ignore
    SubmitJobToDeadlineDialog,
)
from nuke import Node
from PySide2.QtCore import Qt  # pylint: disable=import-error
from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
    QApplication,
    QMainWindow,
)

from .assets import get_nuke_script_file, get_scene_asset_references, find_all_write_nodes
from .data_classes.submission import RenderSubmitterSettings, RenderSubmitterUISettings
from .ui.components.scene_settings_tab import SceneSettingsWidget
from deadline.client.job_bundle.submission import FlatAssetReferences


def _get_sticky_settings_file() -> Optional[Path]:
    script_file_str = get_nuke_script_file()
    if not script_file_str:
        return None
    script_file = Path(script_file_str)
    if script_file.is_file():
        return script_file.with_suffix(".deadline_settings.json")
    return None


def _load_sticky_settings() -> Optional[RenderSubmitterSettings]:
    settings_file = _get_sticky_settings_file()
    if settings_file is None:
        return None
    if not settings_file.is_file():
        return None
    try:
        with open(settings_file, "r", encoding="utf8") as f:
            contents: str = f.read()
            return RenderSubmitterSettings(**json.loads(contents))
    except OSError as exc:
        raise RuntimeError("Failed to read from settings file") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to parse JSON from settings file") from exc
    except TypeError as exc:
        raise RuntimeError("Failed to deserialize settings data") from exc


def _save_sticky_settings(ui_settings: RenderSubmitterUISettings) -> None:
    settings_file = _get_sticky_settings_file()
    if settings_file is None:
        return
    settings = ui_settings.to_render_submitter_settings()
    try:
        with open(settings_file, "w", encoding="utf8") as f:
            f.write(json.dumps(dataclasses.asdict(settings), indent=2))
    except OSError as exc:
        raise RuntimeError("Failed to write to settings file") from exc


def get_nuke_version() -> str:
    """
    Grabs the current Nuke version string.

    Example:
        13.2v1

    :return: Nuke version string
    """
    return nuke.env["NukeVersionString"]


def show_nuke_render_submitter_noargs() -> "SubmitJobToDeadlineDialog":
    with gui_error_handler("Error opening Amazon Deadline Cloud Submitter", None):
        # Get the main Nuke window so we can parent the submitter to it
        app = QApplication.instance()
        mainwin = [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]
    with gui_error_handler("Error opening Amazon Deadline Cloud Submitter", mainwin):
        return show_nuke_render_submitter(mainwin, RenderSubmitterUISettings())


def _get_write_node(settings: RenderSubmitterUISettings) -> tuple[Node, str]:
    node_name = ""
    write_node = settings.write_node_selection
    if write_node is None:
        write_node = nuke.root()
    if write_node != nuke.root():
        node_name = settings.write_node_selection.fullName()
    return write_node, node_name


def _get_job_template(settings: RenderSubmitterUISettings) -> dict[str, Any]:
    # Load the default Nuke job template, and then fill in scene-specific
    # values it needs.
    with open(Path(__file__).parent / "default_nuke_job_template.yaml") as f:
        job_template = yaml.safe_load(f)

    # Set the job's name
    job_template["name"] = settings.name

    # Get a map of the parameter definitions for easier lookup
    parameter_def_map = {param["name"]: param for param in job_template["parameters"]}

    # Set the WriteNode parameter allowed values
    parameter_def_map["WriteNode"]["allowedValues"].extend(
        sorted(node.fullName() for node in find_all_write_nodes())
    )

    # Set the View parameter allowed values
    parameter_def_map["View"]["allowedValues"] = ["All Views"] + sorted(nuke.views())

    # If this developer option is enabled, merge the adaptor_override_environment
    if settings.include_adaptor_wheels:
        with open(Path(__file__).parent / "adaptor_override_environment.yaml") as f:
            override_environment = yaml.safe_load(f)

        # Read DEVELOPMENT.md for instructions to create the wheels directory.
        wheels_path = Path(__file__).parent.parent.parent.parent / "wheels"
        if not wheels_path.exists() and wheels_path.is_dir():
            raise RuntimeError(
                "The Developer Option 'Include Adaptor Wheels' is enabled, but the wheels directory does not exist:\n"
                + str(wheels_path)
            )
        wheels_path_package_names = {
            path.split("-", 1)[0] for path in os.listdir(wheels_path) if path.endswith(".whl")
        }
        if wheels_path_package_names != {"openjobio", "deadline", "deadline_cloud_for_nuke"}:
            raise RuntimeError(
                "The Developer Option 'Include Adaptor Wheels' is enabled, but the wheels directory contains the wrong wheels:\n"
                + "Expected: openjobio, deadline, and deadline_cloud_for_nuke\n"
                + f"Actual: {wheels_path_package_names}"
            )

        adaptor_wheels_param = [
            param
            for param in override_environment["parameters"]
            if param["name"] == "AdaptorWheels"
        ][0]
        adaptor_wheels_param["default"] = str(wheels_path)
        override_adaptor_name_param = [
            param
            for param in override_environment["parameters"]
            if param["name"] == "OverrideAdaptorName"
        ][0]
        override_adaptor_name_param["default"] = "NukeAdaptor"

        # There are no parameter conflicts between these two templates, so this works
        job_template["parameters"].extend(override_environment["parameters"])

        # Add the environment to the end of the template's job environments
        if "environments" not in job_template:
            job_template["environments"] = []
        job_template["environments"].append(override_environment["environment"])

    return job_template


def _get_parameter_values(settings: RenderSubmitterUISettings) -> dict[str, Any]:
    parameter_values = [
        {"name": "deadline:priority", "value": settings.priority},
        {"name": "deadline:targetTaskRunStatus", "value": settings.initial_status},
        {"name": "deadline:maxFailedTasksCount", "value": settings.max_failed_tasks_count},
        {"name": "deadline:maxRetriesPerTask", "value": settings.max_retries_per_task},
    ]
    write_node, write_node_name = _get_write_node(settings)

    # Set the Frames parameter value
    if settings.override_frame_range:
        frame_list = settings.frame_list
    else:
        frame_list = str(write_node.frameRange())
    parameter_values.append({"name": "Frames", "value": frame_list})

    # Set the Nuke script file value
    parameter_values.append({"name": "NukeScriptFile", "value": get_nuke_script_file()})

    # Set the WriteNode parameter value
    if write_node_name:
        parameter_values.append({"name": "WriteNode", "value": write_node_name})

    # Set the View parameter value
    if settings.view_selection:
        parameter_values.append({"name": "View", "value": settings.view_selection})

    # Set the ProxyMode parameter default
    parameter_values.append(
        {"name": "ProxyMode", "value": "true" if settings.is_proxy_mode else "false"}
    )

    # Set the NukeVersion parameter default
    parameter_values.append({"name": "NukeVersion", "value": get_nuke_version()})

    # Set the RezPackages parameter default
    if settings.override_rez_packages:
        parameter_values.append({"name": "RezPackages", "value": settings.rez_packages})

    return {"parameterValues": parameter_values}


def show_nuke_render_submitter(
    parent, render_settings: RenderSubmitterUISettings, f=Qt.WindowFlags()
) -> "SubmitJobToDeadlineDialog":
    def job_bundle_callback(
        widget: SubmitJobToDeadlineDialog,
        settings: RenderSubmitterUISettings,
        job_bundle_dir: str,
        asset_references: FlatAssetReferences,
    ) -> None:
        job_bundle_path = Path(job_bundle_dir)
        job_template = _get_job_template(settings)
        parameter_values = _get_parameter_values(settings)

        with open(job_bundle_path / "template.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(job_template, f, indent=1)

        with open(job_bundle_path / "parameter_values.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(parameter_values, f, indent=1)

        with open(job_bundle_path / "asset_references.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(asset_references.to_dict(), f, indent=1)

        # Save Sticky Settings
        attachments: FlatAssetReferences = widget.job_attachments.attachments
        settings.input_filenames = sorted(attachments.input_filenames)
        settings.input_directories = sorted(attachments.input_directories)
        settings.output_directories = sorted(attachments.output_directories)

        try:
            _save_sticky_settings(settings)
        except RuntimeError:
            nuke.tprint("Failed to save sticky settings:")
            nuke.tprint(traceback.format_exc())

    # Try to load sticky settings
    settings = None
    try:
        settings = _load_sticky_settings()
    except RuntimeError:
        nuke.tprint("Failed to load sticky settings:")
        nuke.tprint(traceback.format_exc())
    if settings is not None:
        render_settings.apply_saved_settings(settings)

    auto_detected_attachments = get_scene_asset_references()
    if settings:
        attachments = FlatAssetReferences(
            input_filenames=set(settings.input_filenames),
            input_directories=set(settings.input_directories),
            output_directories=set(settings.output_directories),
        )
    else:
        attachments = FlatAssetReferences()

    submitter_dialog = SubmitJobToDeadlineDialog(
        SceneSettingsWidget,
        render_settings,
        auto_detected_attachments,
        attachments,
        job_bundle_callback,
        parent=parent,
        f=f,
    )

    submitter_dialog.show()
    return submitter_dialog
