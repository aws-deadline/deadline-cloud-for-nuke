# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional, cast

import nuke
import yaml  # type: ignore[import]
from deadline.client.api import (
    get_deadline_cloud_library_telemetry_client,
    get_queue_parameter_definitions
)
from deadline.client.config import get_setting
from deadline.client.job_bundle import deadline_yaml_dump
from deadline.client.ui import gui_error_handler
import deadline.nuke_submitter.copycat_adaptor as copycat_adaptor_module
from deadline.client.ui.dialogs.submit_job_to_deadline_dialog import (  # type: ignore
    JobBundlePurpose,
    SubmitJobToDeadlineDialog,
)
from nuke import Node

from deadline.nuke_util import ocio as nuke_ocio

# Handle different Qt imports for different Nuke versions
try:
    # For Nuke 16+
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
except ImportError:
    # For Nuke 13-15
    from PySide2.QtCore import Qt  # pylint: disable=import-error
    from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
        QApplication,
        QMainWindow,
        QMessageBox,
    )

from deadline.client.exceptions import DeadlineOperationError
from deadline.client.job_bundle.submission import AssetReferences

from ._version import version
from ._version import version_tuple as adaptor_version_tuple
from .update_utils import check_and_show_update_dialog
from .assets import (
    find_all_write_nodes,
    get_nuke_script_file,
    get_scene_asset_references,
)
from .data_classes import (
    JobType,
    RenderSettings,
    CopyCatTrainingSettings,
    SubmitterUISettings,
)
from .ui.components.asset_scan_warning_dialog import AssetScanWarningDialog
from .ui.components.scene_settings_tab import SceneSettingsWidget

g_render_submitter_dialog = None
g_copycat_submitter_dialog = None


def show_nuke_render_submitter(job_type: JobType) -> Optional[SubmitJobToDeadlineDialog]:
    with gui_error_handler("Error opening AWS Deadline Cloud Submitter", None):
        # Get the main Nuke window so we can parent the submitter to it
        app = QApplication.instance()
        mainwin = [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]
    with gui_error_handler("Error opening AWS Deadline Cloud Submitter", mainwin):
        if check_and_show_update_dialog():
            return None
        return _show_nuke_render_submitter(mainwin, job_type=job_type, f=Qt.Tool)


def _get_write_node(settings: SubmitterUISettings) -> tuple[Node, str]:
    assert settings.get_job_type() == JobType.RENDER

    if settings.jobtype_specific_settings.write_node_selection:  # type: ignore[union-attr]
        write_node = nuke.toNode(settings.jobtype_specific_settings.write_node_selection)  # type: ignore[union-attr]
    else:
        write_node = nuke.root()
    return write_node, settings.jobtype_specific_settings.write_node_selection  # type: ignore[union-attr]


def _set_timeouts(template: dict[str, Any], settings: SubmitterUISettings) -> None:
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


def get_queue_parameters(
    farm_id: Optional[str] = None,
    queue_id: Optional[str] = None,
    initial_values: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Get queue parameters from Deadline Cloud for external API usage.

    This function retrieves queue parameter definitions from the Deadline Cloud API
    and optionally applies initial values. It can be used to construct queue_parameters
    for get_parameter_values_for_submission() without going through the UI.

    Args:
        farm_id: The farm ID. If not provided, uses the default from settings.
        queue_id: The queue ID. If not provided, uses the default from settings.
        initial_values: Optional dict of {parameter_name: value} to override
            default parameter values. For example:
            {"RezPackages": "maya-2024 deadline_cloud_for_maya"}

    Returns:
        A list of parameter definition dicts with "name" and "value" keys,
        suitable for passing to get_parameter_values_for_submission().

    Raises:
        DeadlineOperationError: If farm_id or queue_id are not configured.

    Example:
        >>> queue_params = get_queue_parameters(
        ...     initial_values={"RezPackages": "maya-2024"}
        ... )
        >>> param_values = get_parameter_values_for_submission(settings, queue_params)
    """
    if farm_id is None:
        farm_id = get_setting("defaults.farm_id")
    if queue_id is None:
        queue_id = get_setting("defaults.queue_id")

    if not farm_id or not queue_id:
        raise DeadlineOperationError(
            "Farm ID and Queue ID must be configured. "
            "Either provide them as arguments or configure them in Deadline Cloud settings."
        )

    # Fetch queue parameter definitions from the API
    queue_parameters = get_queue_parameter_definitions(farmId=farm_id, queueId=queue_id)

    # Apply initial values if provided
    if initial_values:
        for parameter in queue_parameters:
            if parameter["name"] in initial_values:
                parameter["value"] = initial_values[parameter["name"]]

    return cast(list[dict[str, Any]], queue_parameters)


def _normalize_queue_parameters(
    queue_parameters: list[dict[str, Any]],
    initial_values: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """    Ensure every queue parameter has a "value" field so downstream code can safely
    serialize {"name": ..., "value": ...} for submission.

    Args:
        queue_parameters (list[dict[str, Any]]): The list of queue parameters to normalize.
        initial_values (Optional[dict[str, Any]], optional): Initial values for the parameters.
            Defaults to None.

    Returns:
        list[dict[str, Any]]: The normalized list of queue parameters with "value" fields populated.
    """
    normalized: list[dict[str, Any]] = []

    for parameter in queue_parameters:
        name = parameter.get("name")
        if not name:
            # Skip malformed entries; alternatively raise if you prefer strict behavior.
            continue

        normalized_param = dict(parameter)

        # Priority: caller-provided initial_values > existing value > API default > empty string
        if initial_values and name in initial_values:
            normalized_param["value"] = initial_values[name]
        elif "value" not in normalized_param:
            if "default" in normalized_param:
                normalized_param["value"] = normalized_param["default"]
            else:
                normalized_param["value"] = ""

        normalized.append(normalized_param)

    return normalized


def get_job_template_for_submission(
    settings: SubmitterUISettings,
    host_requirements: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Generate the job template for Houdini render submissions.

    This function returns the job template in its final state, ready to be
    serialized to YAML. It can be used for external integrations.

    Args:
        settings: The render submitter UI settings.
        host_requirements: Optional host requirements to inject into job steps.

    Returns:
        The job template dictionary ready for serialization.
    """
    job_template = _get_job_template(settings)
    # If "HostRequirements" is provided, inject it into each of the "Step"
    if host_requirements:
        for step in job_template["steps"]:
            step["hostRequirements"] = host_requirements
    return job_template


def _get_job_template(settings: SubmitterUISettings) -> dict[str, Any]:
    job_type = settings.get_job_type()
    # Load the default Nuke job template, and then fill in scene-specific
    # values it needs.

    template_name = (
        "default_nuke_job_template.yaml"
        if job_type == JobType.RENDER
        else "copycat_job_template.yaml"
    )

    with open(Path(__file__).parent / template_name) as f:
        job_template = yaml.safe_load(f)

    # Set the job's name and description
    job_template["name"] = settings.name
    if settings.description:
        job_template["description"] = settings.description

    # Set the timeouts for each action:
    _set_timeouts(job_template, settings)

    if job_type == JobType.RENDER:
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
            job_template["parameterDefinitions"].extend(
                override_environment["parameterDefinitions"]
            )

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
                step["script"]["embeddedFiles"][0][
                    "data"
                ] = f"frameRange: {start_frame}-{end_frame}\n"

    return job_template


def get_asset_references_for_submission(
    asset_references: AssetReferences,
) -> dict[str, Any]:
    """Get the asset references in dictionary form for Houdini render submissions.

    This function returns the asset references in their final state, ready to be
    serialized to YAML. It can be used for external integrations.

    Args:
        asset_references: The asset references object.

    Returns:
        The asset references dictionary ready for serialization.
    """
    return asset_references.to_dict()


def get_parameter_values_for_submission(
    settings: SubmitterUISettings,
    queue_parameters: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Generate the parameter values for a job submission.

    This function returns the parameter values in their final state, ready to be
    included in the job bundle for submission. It can be used for external integrations.

    Args:
        settings: The render submitter UI settings.
        queue_parameters: Optional list of additional queue parameters to include.

    Returns:
        The list of parameter values to include in the job bundle.
    """
    if queue_parameters is None:
        queue_parameters = []
    queue_parameters = _normalize_queue_parameters(queue_parameters)
    return _get_parameter_values(settings, queue_parameters)


def _get_parameter_values(
    settings: SubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    job_type = settings.get_job_type()

    if job_type == JobType.RENDER:
        return _get_render_parameter_values(settings=settings, queue_parameters=queue_parameters)
    else:
        return _get_copycat_training_parameter_values(
            settings=settings, queue_parameters=queue_parameters
        )


def _get_copycat_training_parameter_values(
    settings: SubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parameter_values: list[dict[str, Any]] = []

    copycat_settings = settings.jobtype_specific_settings

    copycat_node = nuke.toNode(copycat_settings.copycat_node)  # type: ignore[union-attr]

    # Set the Nuke script file value
    parameter_values.append({"name": "NukeScriptFile", "value": get_nuke_script_file()})
    parameter_values.append({"name": "CopyCatNode", "value": copycat_settings.copycat_node})  # type: ignore[union-attr]
    parameter_values.append(
        {"name": "DataDir", "value": copycat_node.knob("dataDirectory").getEvaluatedValue()}
    )
    parameter_values.append(
        {
            "name": "CopyCatAdaptor",
            "value": copycat_adaptor_module.__file__,
        }
    )

    parameter_values.extend(
        {"name": param["name"], "value": param["value"]} for param in queue_parameters
    )

    return parameter_values


def _get_render_parameter_values(
    settings: SubmitterUISettings,
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
    if settings.jobtype_specific_settings.view_selection:  # type: ignore[union-attr]
        parameter_values.append(
            {"name": "View", "value": settings.jobtype_specific_settings.view_selection}  # type: ignore[union-attr]
        )

    # Set the ProxyMode parameter default
    parameter_values.append(
        {
            "name": "ProxyMode",
            "value": "true" if settings.jobtype_specific_settings.is_proxy_mode else "false",  # type: ignore[union-attr]
        }
    )

    # Set the ContinueOnError parameter default
    parameter_values.append(
        {
            "name": "ContinueOnError",
            "value": "true" if settings.jobtype_specific_settings.continue_on_error else "false",  # type: ignore[union-attr]
        }
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
            f"{', '.join(parameter_overlap)}"
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
    settings: SubmitterUISettings,
    write_node: Node,
    write_node_name: Optional[str],
) -> str:
    assert settings.get_job_type() == JobType.RENDER
    # Set the Frames parameter value
    if settings.jobtype_specific_settings.override_frame_range:  # type: ignore[union-attr]
        frame_list = settings.jobtype_specific_settings.frame_list  # type: ignore[union-attr]
    else:
        # frame range from project setting
        frame_list = str(nuke.root().frameRange())
        if write_node_name and write_node.knob("use_limit").value():
            first_frame = int(write_node.knob("first").value())
            last_frame = int(write_node.knob("last").value())
            frame_list = f"{first_frame}-{last_frame}"
    return frame_list


def _show_nuke_render_submitter(
    parent, job_type: JobType, f=Qt.WindowFlags()
) -> SubmitJobToDeadlineDialog:
    global g_render_submitter_dialog
    global g_copycat_submitter_dialog
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

    render_settings = SubmitterUISettings()

    # Set settings based on the job type
    if job_type == JobType.RENDER:
        render_settings.jobtype_specific_settings = RenderSettings()
    elif job_type == JobType.COPYCAT_TRAINING:
        render_settings.jobtype_specific_settings = CopyCatTrainingSettings()

    # Set the setting defaults that come from the scene
    render_settings.name = Path(script_path).name
    render_settings.jobtype_specific_settings.frame_list = str(nuke.root().frameRange())  # type: ignore[union-attr]
    render_settings.jobtype_specific_settings.is_proxy_mode = nuke.root().proxy()  # type: ignore[union-attr]

    # Load the sticky settings
    render_settings.load_sticky_settings(script_path)

    def on_create_job_bundle_callback(
        widget: SubmitJobToDeadlineDialog,
        job_bundle_dir: str,
        settings: SubmitterUISettings,
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
        asset_references_dict = get_asset_references_for_submission(asset_references)

        with open(job_bundle_path / "template.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(job_template, f, indent=1)

        with open(job_bundle_path / "parameter_values.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump({"parameterValues": parameter_values}, f, indent=1)

        with open(job_bundle_path / "asset_references.yaml", "w", encoding="utf8") as f:
            deadline_yaml_dump(asset_references_dict, f, indent=1)

        # Save Sticky Settings
        attachments: AssetReferences = widget.job_attachments.attachments
        settings.input_filenames = sorted(attachments.input_filenames)
        settings.input_directories = sorted(attachments.input_directories)
        settings.output_directories = sorted(attachments.output_directories)

        settings.save_sticky_settings(get_nuke_script_file())

    # Try to scan scene asset references
    asset_references_parsing_outcome = get_scene_asset_references()

    # If there was an error scanning for assets, show warning dialog
    if asset_references_parsing_outcome.encountered_exception():
        dialog = AssetScanWarningDialog(asset_references_parsing_outcome, parent)
        dialog.exec_()
        result = dialog.get_result()

        if not result.continue_submission:
            # User chose to cancel submission
            raise DeadlineOperationError(
                "Submission cancelled due to asset references scan failure."
            )

    if render_settings:
        attachments = AssetReferences(
            input_filenames=set(render_settings.input_filenames),
            input_directories=set(render_settings.input_directories),
            output_directories=set(render_settings.output_directories),
        )
    else:
        attachments = AssetReferences()

    submitter_dialog = (
        g_render_submitter_dialog if job_type == JobType.RENDER else g_copycat_submitter_dialog
    )

    if not submitter_dialog:
        nuke_version = nuke.env["NukeVersionMajor"]
        adaptor_version = ".".join(str(v) for v in adaptor_version_tuple[:2])

        # Need Nuke and the Nuke OpenJD application interface adaptor
        rez_packages = f"nuke-{nuke_version} deadline_cloud_for_nuke"
        conda_packages = f"nuke={nuke_version}.*"
        if job_type == JobType.RENDER:
            conda_packages += f" nuke-openjd={adaptor_version}.*"

        submitter_dialog = SubmitJobToDeadlineDialog(
            job_setup_widget_type=SceneSettingsWidget,
            initial_job_settings=render_settings,
            initial_shared_parameter_values={
                "RezPackages": rez_packages,
                "CondaPackages": conda_packages,
            },
            auto_detected_attachments=asset_references_parsing_outcome.asset_references,
            attachments=attachments,
            on_create_job_bundle_callback=on_create_job_bundle_callback,  # type: ignore
            parent=parent,
            f=f,
            show_host_requirements_tab=True,
        )

        if job_type == JobType.RENDER:
            submitter_dialog.setWindowTitle("Submit Rendering to AWS Deadline Cloud")
            g_render_submitter_dialog = submitter_dialog
        else:
            submitter_dialog.setWindowTitle("Submit CopyCat Training to AWS Deadline Cloud")
            g_copycat_submitter_dialog = submitter_dialog
    else:
        submitter_dialog.refresh(
            job_settings=render_settings,
            auto_detected_attachments=asset_references_parsing_outcome.asset_references,
            attachments=attachments,
        )

    submitter_dialog.show()
    return submitter_dialog
