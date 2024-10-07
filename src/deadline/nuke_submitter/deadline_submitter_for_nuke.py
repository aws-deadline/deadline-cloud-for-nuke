# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional
import yaml  # type: ignore[import]

import nuke
from deadline.client.api import get_deadline_cloud_library_telemetry_client
from deadline.client.job_bundle import deadline_yaml_dump
from deadline.client.ui import gui_error_handler
from deadline.client.ui.dialogs.submit_job_to_deadline_dialog import (  # type: ignore
    SubmitJobToDeadlineDialog,
    JobBundlePurpose,
)
from deadline.nuke_util import ocio as nuke_ocio
from nuke import Node
from PySide2.QtCore import Qt  # pylint: disable=import-error
from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
    QApplication,
    QMainWindow,
    QMessageBox,
)

from ._version import version, version_tuple as adaptor_version_tuple
from .assets import (
    get_nuke_script_file,
    get_scene_asset_references,
    find_all_write_nodes,
)
from .data_classes import RenderSubmitterUISettings
from .ui.components.scene_settings_tab import SceneSettingsWidget
from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.exceptions import DeadlineOperationError

g_submitter_dialog = None


def show_nuke_render_submitter_noargs() -> "SubmitJobToDeadlineDialog":
    with gui_error_handler("Error opening AWS Deadline Cloud Submitter", None):
        # Get the main Nuke window so we can parent the submitter to it
        app = QApplication.instance()
        mainwin = [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]
    with gui_error_handler("Error opening AWS Deadline Cloud Submitter", mainwin):
        return show_nuke_render_submitter(mainwin, f=Qt.Tool)


def _get_write_node(settings: RenderSubmitterUISettings) -> tuple[Node, str]:
    if settings.write_node_selection:
        write_node = nuke.toNode(settings.write_node_selection)
    else:
        write_node = nuke.root()
    return write_node, settings.write_node_selection


def _set_timeouts(template: dict[str, Any], settings: RenderSubmitterUISettings) -> None:
    """
    Timeouts are an OpenJD field applicable to actions but for specification 2023-09, timeouts must
    be hard-coded in the job template. There are three types of actions: OnRun, onEnter, and onExit.
    This function does an in-place modification of timeout values for each action in the template.
    """

    def _handle_environment(environment: dict):
        if "script" in environment:
            actions = environment["script"]["actions"]
            actions["onEnter"]["timeout"] = settings.on_enter_timeout_seconds
            if "onExit" in actions:
                actions["onExit"]["timeout"] = settings.on_exit_timeout_seconds

    def _handle_step(step: dict):
        for environment in step.get("stepEnvironments", []):
            _handle_environment(environment)

        step["script"]["actions"]["onRun"]["timeout"] = settings.on_run_timeout_seconds

    for environment in template.get("jobEnvironments", []):
        _handle_environment(environment)

    for step in template.get("steps", []):
        _handle_step(step)


def _remove_gizmo_dir_from_job_template(job_template: dict[str, Any]) -> None:
    for index, param in enumerate(job_template["parameterDefinitions"]):
        if param["name"] == "GizmoDir":
            job_template["parameterDefinitions"].pop(index)
            break


def _add_gizmo_dir_to_job_template(job_template: dict[str, Any]) -> None:
    if "jobEnvironments" not in job_template:
        job_template["jobEnvironments"] = []

    # This needs to be prepended rather than appended
    # as it must run before the "Nuke" environment.
    job_template["jobEnvironments"].insert(
        0,
        {
            "name": "Add Gizmos to NUKE_PATH",
            "script": {
                "actions": {"onEnter": {"command": "{{Env.File.Enter}}"}},
                "embeddedFiles": [
                    {
                        "name": "Enter",
                        "type": "TEXT",
                        "runnable": True,
                        "data": """#!/bin/bash
    echo 'openjd_env: NUKE_PATH=$NUKE_PATH:{{Param.GizmoDir}}'
    """,
                    }
                ],
            },
        },
    )


def _add_ocio_path_to_job_template(job_template: dict[str, Any]) -> None:
    if "jobEnvironments" not in job_template:
        job_template["jobEnvironments"] = []

    # This needs to be prepended rather than appended
    # as it must run before the "Nuke" environment.
    job_template["jobEnvironments"].insert(
        0,
        {
            "name": "Add OCIO Path to Environment Variable",
            "variables": {"OCIO": "{{Param.OCIOConfigPath}}"},
        },
    )


def _remove_ocio_path_from_job_template(job_template: dict[str, Any]) -> None:
    for index, param in enumerate(job_template["parameterDefinitions"]):
        if param["name"] == "OCIOConfigPath":
            job_template["parameterDefinitions"].pop(index)
            break


def _get_job_template(settings: RenderSubmitterUISettings) -> dict[str, Any]:
    # Load the default Nuke job template, and then fill in scene-specific
    # values it needs.
    with open(Path(__file__).parent / "default_nuke_job_template.yaml") as f:
        job_template = yaml.safe_load(f)

    # Set the job's name and description
    job_template["name"] = settings.name
    if settings.description:
        job_template["description"] = settings.description

    # Set the timeouts for each action:
    _set_timeouts(job_template, settings)

    # Add Gizmo directory to NUKE_PATH if we copied
    # any gizmos to the job bundle.
    if settings.include_gizmos_in_job_bundle:
        _add_gizmo_dir_to_job_template(job_template)
    else:
        _remove_gizmo_dir_from_job_template(job_template)

    # Get a map of the parameter definitions for easier lookup
    parameter_def_map = {param["name"]: param for param in job_template["parameterDefinitions"]}

    # Set the WriteNode parameter allowed values
    parameter_def_map["WriteNode"]["allowedValues"].extend(
        sorted(node.fullName() for node in find_all_write_nodes())
    )

    # Set the View parameter allowed values
    parameter_def_map["View"]["allowedValues"] = ["All Views"] + sorted(nuke.views())

    # if OCIO is disabled, remove OCIO path from the template
    if nuke_ocio.is_OCIO_enabled():
        _add_ocio_path_to_job_template(job_template)
    else:
        _remove_ocio_path_from_job_template(job_template)

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

    # Determine whether this is a movie render. If it is, we want to ensure that the entire Nuke
    # evaluation is placed on one task.
    write_node, write_node_name = _get_write_node(settings)
    movie_render = "file_type" in write_node.knobs() and write_node["file_type"].value() in [
        "mov",
        "mxf",
    ]
    if movie_render:
        frame_list = _get_frame_list(settings, write_node, write_node_name)
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
            step["script"]["embeddedFiles"][0]["data"] = f"frameRange: {start_frame}-{end_frame}\n"

    return job_template


def _get_parameter_values(
    settings: RenderSubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parameter_values: list[dict[str, Any]] = []

    write_node, write_node_name = _get_write_node(settings)

    # Set the Frames parameter value
    parameter_values.append(
        {"name": "Frames", "value": _get_frame_list(settings, write_node, write_node_name)}
    )

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

    # Set the OCIO config path value
    if nuke_ocio.is_OCIO_enabled():
        ocio_config_path = nuke_ocio.get_ocio_config_path()
        if ocio_config_path:
            parameter_values.append({"name": "OCIOConfigPath", "value": ocio_config_path})
        else:
            raise DeadlineOperationError(
                "OCIO is enabled but OCIO config file is not specified. Please check and update the config file before proceeding."
            )
    if settings.include_adaptor_wheels:
        wheels_path = str(Path(__file__).parent.parent.parent.parent / "wheels")
        parameter_values.append({"name": "AdaptorWheels", "value": wheels_path})

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

    # If we're overriding the adaptor with wheels, remove the adaptor from the Packages parameters
    if settings.include_adaptor_wheels:
        rez_param = {}
        conda_param = {}
        # Find the Packages parameter definition
        for param in queue_parameters:
            if param["name"] == "RezPackages":
                rez_param = param
            if param["name"] == "CondaPackages":
                conda_param = param
        # Remove the deadline_cloud_for_nuke/nuke-openjd package
        if rez_param:
            rez_param["value"] = " ".join(
                pkg
                for pkg in rez_param["value"].split()
                if not pkg.startswith("deadline_cloud_for_nuke")
            )
        if conda_param:
            conda_param["value"] = " ".join(
                pkg for pkg in conda_param["value"].split() if not pkg.startswith("nuke-openjd")
            )

    parameter_values.extend(
        {"name": param["name"], "value": param["value"]} for param in queue_parameters
    )

    return parameter_values


def _get_frame_list(
    settings: RenderSubmitterUISettings,
    write_node: Node,
    write_node_name: Optional[str],
) -> str:
    # Set the Frames parameter value
    if settings.override_frame_range:
        frame_list = settings.frame_list
    else:
        # frame range from project setting
        frame_list = str(nuke.root().frameRange())
        if write_node_name and write_node.knob("use_limit").value():
            first_frame = int(write_node.knob("first").value())
            last_frame = int(write_node.knob("last").value())
            frame_list = f"{first_frame}-{last_frame}"
    return frame_list


def show_nuke_render_submitter(parent, f=Qt.WindowFlags()) -> "SubmitJobToDeadlineDialog":
    global g_submitter_dialog

    # Initialize telemetry client, opt-out is respected
    get_deadline_cloud_library_telemetry_client().update_common_details(
        {
            "deadline-cloud-for-nuke-submitter-version": version,
            "nuke-version": nuke.env["NukeVersionString"],
        }
    )
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
        purpose: JobBundlePurpose = JobBundlePurpose.SUBMISSION,
    ) -> None:
        # if submitting, warn if the current scene has been modified
        root = nuke.root()
        if root is not None and root.modified() and purpose == JobBundlePurpose.SUBMISSION:
            message = "Save script to %s before submitting?" % nuke.scriptName()
            result = QMessageBox.question(
                widget,
                "Warning: Script not saved",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result == QMessageBox.Yes:
                nuke.scriptSave()

        if settings.timeouts_enabled:
            message = "The following timeout value(s) must be greater than 0: \n"
            zero_timeouts = []
            if not settings.on_run_timeout_seconds:
                zero_timeouts.append("Render Timeout")
            if not settings.on_enter_timeout_seconds:
                zero_timeouts.append("Setup Timeout")
            if not settings.on_exit_timeout_seconds:
                zero_timeouts.append("Teardown Timeout")
            if zero_timeouts:
                message += ", ".join(zero_timeouts)
                message += "\n\nPlease configure these value(s) in the 'Job-Specific Settings' tab."
                raise DeadlineOperationError(message)

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
        adaptor_version = ".".join(str(v) for v in adaptor_version_tuple[:2])

        # Need Nuke and the Nuke OpenJD application interface adaptor
        rez_packages = f"nuke-{nuke_version} deadline_cloud_for_nuke"
        conda_packages = f"nuke={nuke_version}.* nuke-openjd={adaptor_version}.*"

        g_submitter_dialog = SubmitJobToDeadlineDialog(
            job_setup_widget_type=SceneSettingsWidget,
            initial_job_settings=render_settings,
            initial_shared_parameter_values={
                "RezPackages": rez_packages,
                "CondaPackages": conda_packages,
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

    g_submitter_dialog.show()
    return g_submitter_dialog
