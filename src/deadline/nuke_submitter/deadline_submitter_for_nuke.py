# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional
import yaml  # type: ignore[import]

import nuke
from deadline.client.api import get_deadline_cloud_library_telemetry_client, TelemetryClient
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
from .data_classes import RenderSubmitterUISettings
from .ui.components.scene_settings_tab import SceneSettingsWidget
from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.exceptions import DeadlineOperationError

g_submitter_dialog = None


def show_nuke_render_submitter_noargs() -> "SubmitJobToDeadlineDialog":
    with gui_error_handler("Error opening Amazon Deadline Cloud Submitter", None):
        # Get the main Nuke window so we can parent the submitter to it
        app = QApplication.instance()
        mainwin = [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]
    with gui_error_handler("Error opening Amazon Deadline Cloud Submitter", mainwin):
        return show_nuke_render_submitter(mainwin)


def _get_deadline_telemetry_client() -> TelemetryClient:
    """
    Wrapper around the Deadline Client Library telemetry client, in order to set package-specific information
    """
    return get_deadline_cloud_library_telemetry_client()


def _get_write_node(settings: RenderSubmitterUISettings) -> tuple[Node, str]:
    if settings.write_node_selection:
        write_node = nuke.toNode(settings.write_node_selection)
    else:
        write_node = nuke.root()
    return write_node, settings.write_node_selection


def _get_job_template(settings: RenderSubmitterUISettings) -> dict[str, Any]:
    # Load the default Nuke job template, and then fill in scene-specific
    # values it needs.
    with open(Path(__file__).parent / "default_nuke_job_template.yaml") as f:
        job_template = yaml.safe_load(f)

    # Set the job's name
    job_template["name"] = settings.name

    # Get a map of the parameter definitions for easier lookup
    parameter_def_map = {param["name"]: param for param in job_template["parameterDefinitions"]}

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
        if not wheels_path.is_dir():
            raise RuntimeError(
                "The Developer Option 'Include Adaptor Wheels' is enabled, but the wheels directory does not exist:\n"
                + str(wheels_path)
            )
        wheels_path_package_names = {
            path.split("-", 1)[0] for path in os.listdir(wheels_path) if path.endswith(".whl")
        }
        if wheels_path_package_names != {
            "openjd_adaptor_runtime",
            "deadline",
            "deadline_cloud_for_nuke",
        }:
            raise RuntimeError(
                "The Developer Option 'Include Adaptor Wheels' is enabled, but the wheels directory contains the wrong wheels:\n"
                + "Expected: openjd_adaptor_runtime, deadline, and deadline_cloud_for_nuke\n"
                + f"Actual: {wheels_path_package_names}"
            )

        adaptor_wheels_param = [
            param
            for param in override_environment["parameterDefinitions"]
            if param["name"] == "AdaptorWheels"
        ][0]
        adaptor_wheels_param["default"] = str(wheels_path)
        override_adaptor_name_param = [
            param
            for param in override_environment["parameterDefinitions"]
            if param["name"] == "OverrideAdaptorName"
        ][0]
        override_adaptor_name_param["default"] = "NukeAdaptor"

        # There are no parameter conflicts between these two templates, so this works
        job_template["parameterDefinitions"].extend(override_environment["parameterDefinitions"])

        # Add the environment to the end of the template's job environments
        if "jobEnvironments" not in job_template:
            job_template["jobEnvironments"] = []
        job_template["jobEnvironments"].append(override_environment["environment"])

        # Determine whether this is a MOV render. If it is, we want to ensure that the entire Nuke
        # evaluation is placed on one task.
        write_node, _ = _get_write_node(settings)
        mov_render = "file_type" in write_node.knobs() and write_node["file_type"].value() == "mov"
        if mov_render:
            frame_list = (
                settings.frame_list
                if settings.override_frame_range
                else str(write_node.frameRange())
            )
            match = re.match(r"(\d+)-(\d+)", frame_list)
            if not match:
                raise DeadlineOperationError(
                    f"Invalid frame range {frame_list} for evaluating a MOV render. Frame range must follow the format 'startFrame - endFrame'"
                )

            start_frame = match.group(1)
            end_frame = match.group(2)

            # Remove the Frame parameter space and update the script data with the desired start and end frame
            for step in job_template["steps"]:
                del step["parameterSpace"]
                step["script"]["embeddedFiles"][0][
                    "data"
                ] = f"frameRange: {start_frame}-{end_frame}\n"

    return job_template


def _get_parameter_values(
    settings: RenderSubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parameter_values: list[dict[str, Any]] = []

    write_node, write_node_name = _get_write_node(settings)

    # Set the Frames parameter value
    if settings.override_frame_range:
        frame_list = settings.frame_list
    else:
        frame_list = str(write_node.frameRange())
    parameter_values.append({"name": "Frames", "value": frame_list})

    # Set the Nuke script file value
    parameter_values.append({"name": "NukeScriptFile", "value": get_nuke_script_file()})

    # Set the TelemetryOptOut parameter value
    parameter_values.append(
        {"name": "TelemetryOptOut", "value": "true" if settings.is_telemetry_opted_out else "false"}
    )

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

    # Check for any overlap between the job parameters we've defined and the
    # queue parameters. This is an error, as we weren't synchronizing the values
    # between the two different tabs where they came from.
    parameter_names = {param["name"] for param in parameter_values}
    queue_parameter_names = {param["name"] for param in queue_parameters}
    parameter_overlap = parameter_names.intersection(queue_parameter_names)
    if parameter_overlap:
        raise DeadlineOperationError(
            "The following queue parameters conflict with the Nuke job parameters:\n"
            + f"{', '.join(parameter_overlap)}"
        )

    # If we're overriding the adaptor with wheels, remove deadline_cloud_for_nuke from the RezPackages
    if settings.include_adaptor_wheels:
        rez_param = {}
        # Find the RezPackages parameter definition
        for param in queue_parameters:
            if param["name"] == "RezPackages":
                rez_param = param
                break
        # Remove the deadline_cloud_for_nuke rez package
        if rez_param:
            rez_param["value"] = " ".join(
                pkg
                for pkg in rez_param["value"].split()
                if not pkg.startswith("deadline_cloud_for_nuke")
            )

    parameter_values.extend(
        {"name": param["name"], "value": param["value"]} for param in queue_parameters
    )

    return parameter_values


def show_nuke_render_submitter(parent, f=Qt.WindowFlags()) -> "SubmitJobToDeadlineDialog":
    global g_submitter_dialog

    render_settings = RenderSubmitterUISettings()

    # Set the setting defaults that come from the scene
    render_settings.name = Path(get_nuke_script_file()).name
    render_settings.frame_list = str(nuke.root().frameRange())
    render_settings.is_proxy_mode = nuke.root().proxy()
    render_settings.is_telemetry_opted_out = _get_deadline_telemetry_client().telemetry_opted_out

    script_path = get_nuke_script_file()
    if not script_path:
        raise DeadlineOperationError(
            "The Nuke Script is not saved to disk. Please save it before opening the submitter dialog."
        )

    if nuke.root().modified():
        raise DeadlineOperationError(
            "The Nuke Script has unsaved changes. Please save it before opening the submitter dialog."
        )

    render_settings = RenderSubmitterUISettings()

    # Set the setting defaults that come from the scene
    render_settings.name = Path(script_path).name
    render_settings.frame_list = str(nuke.root().frameRange())
    render_settings.is_proxy_mode = nuke.root().proxy()

    # Load the sticky settings
    render_settings.load_sticky_settings(script_path)

    def on_create_job_bundle_callback(
        widget: SubmitJobToDeadlineDialog,
        job_bundle_dir: str,
        settings: RenderSubmitterUISettings,
        queue_parameters: list[dict[str, Any]],
        asset_references: AssetReferences,
        host_requirements: Optional[dict[str, Any]] = None,
    ) -> None:
        job_bundle_path = Path(job_bundle_dir)
        job_template = _get_job_template(settings)

        # If "HostRequirements" is provided, inject it into each of the "Step"
        if host_requirements:
            # for each step in the template, append the same host requirements.
            for step in job_template["steps"]:
                step["hostRequirements"] = host_requirements

        parameter_values = _get_parameter_values(settings, queue_parameters)

        with open(job_bundle_path / "template.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(job_template, f, indent=1)

        with open(job_bundle_path / "parameter_values.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump({"parameterValues": parameter_values}, f, indent=1)

        with open(job_bundle_path / "asset_references.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(asset_references.to_dict(), f, indent=1)

        # Save Sticky Settings
        attachments: AssetReferences = widget.job_attachments.attachments
        settings.input_filenames = sorted(attachments.input_filenames)
        settings.input_directories = sorted(attachments.input_directories)
        settings.output_directories = sorted(attachments.output_directories)

        settings.save_sticky_settings(get_nuke_script_file())

    auto_detected_attachments = get_scene_asset_references()
    if render_settings:
        attachments = AssetReferences(
            input_filenames=set(render_settings.input_filenames),
            input_directories=set(render_settings.input_directories),
            output_directories=set(render_settings.output_directories),
        )
    else:
        attachments = AssetReferences()

    if not g_submitter_dialog:
        nuke_version = nuke.env["NukeVersionMajor"]
        g_submitter_dialog = SubmitJobToDeadlineDialog(
            job_setup_widget_type=SceneSettingsWidget,
            initial_job_settings=render_settings,
            initial_shared_parameter_values={
                "RezPackages": f"nuke-{nuke_version} deadline_cloud_for_nuke"
            },
            auto_detected_attachments=auto_detected_attachments,
            attachments=attachments,
            on_create_job_bundle_callback=on_create_job_bundle_callback,
            parent=parent,
            f=f,
            show_host_requirements_tab=True,
        )
    else:
        g_submitter_dialog.refresh(
            job_settings=render_settings,
            auto_detected_attachments=auto_detected_attachments,
            attachments=attachments,
        )

    _get_deadline_telemetry_client().record_event(
        "com.amazon.rum.deadline.submitter.window", {"submitter_name": "Nuke"}
    )

    g_submitter_dialog.show()
    return g_submitter_dialog
