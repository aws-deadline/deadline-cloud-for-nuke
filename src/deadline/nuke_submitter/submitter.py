# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, cast

import nuke  # type: ignore[import]
import yaml  # type: ignore[import]
from nuke import Node

from deadline.client.api import BaseSubmitter, BaseSubmitterSettings
from deadline.client.exceptions import DeadlineOperationError
from deadline.client.job_bundle.submission import AssetReferences

from deadline.nuke_util import ocio as nuke_ocio

from .assets import (
    find_all_write_nodes,
    get_nuke_script_file,
    get_project_path,
    get_scene_asset_references,
)

_logger = logging.getLogger(__name__)


@dataclass
class NukeSubmitterSettings(BaseSubmitterSettings):
    """Nuke-specific submission settings.

    Extends the DCC-agnostic :class:`BaseSubmitterSettings` with the render
    fields the Nuke job-template/parameter builders consume directly, so the
    builders read a single flat settings object without a native-settings
    translation step. This mirrors ``MayaSubmitterSettings``.

    This is a render-only contract: CopyCat training is a GUI-only job type and
    is not expressed through the unified submitter (see the copycat path in
    ``deadline_submitter_for_nuke.py``).
    """

    write_node_selection: str = ""
    view_selection: str = ""
    is_proxy_mode: bool = False
    continue_on_error: bool = False
    chunk_size: int = 1
    target_chunk_duration: int = 0
    include_gizmos_in_job_bundle: bool = False

    # developer option
    include_adaptor_wheels: bool = False

    timeouts_enabled: bool = True
    on_run_timeout_seconds: int = 518400
    on_enter_timeout_seconds: int = 86400
    on_exit_timeout_seconds: int = 3600


class _SupportsTimeouts(Protocol):
    """Structural type for _set_timeouts: the GUI's SubmitterUISettings and the
    unified NukeSubmitterSettings both expose these three fields, so the shared
    helper can serve the render engine and the copycat path without coupling to
    either concrete class."""

    on_run_timeout_seconds: int
    on_enter_timeout_seconds: int
    on_exit_timeout_seconds: int


def _set_timeouts(template: dict[str, Any], settings: _SupportsTimeouts) -> None:
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


def _get_write_node(settings: NukeSubmitterSettings) -> tuple[Node, str]:
    if settings.write_node_selection:
        write_node = nuke.toNode(settings.write_node_selection)
    else:
        write_node = nuke.root()
    return write_node, settings.write_node_selection


def _get_frame_list(
    settings: NukeSubmitterSettings,
    write_node: Node,
    write_node_name: Optional[str],
) -> str:
    # Set the Frames parameter value
    if settings.override_frame_range:
        # The caller explicitly opted into overriding the range, so honor their
        # value. An empty frame_list here is contradictory input (override on,
        # nothing supplied): fail fast with a clear message rather than silently
        # falling back to the whole scene range, which would render frames the
        # user did not ask for. (The Frames job parameter also has minLength: 1,
        # so an empty value would otherwise be rejected server-side at CreateJob.)
        if not settings.frame_list:
            raise DeadlineOperationError(
                "Frame range override is enabled but no frame range was provided. "
                "Enter a frame range or disable the override."
            )
        return settings.frame_list

    # Override off (the UI default): use the scene's frame range, or a selected
    # Write node's own use_limit/first/last range when it defines one.
    frame_list = str(nuke.root().frameRange())
    if write_node_name and write_node.knob("use_limit").value():
        first_frame = int(write_node.knob("first").value())
        last_frame = int(write_node.knob("last").value())
        frame_list = f"{first_frame}-{last_frame}"
    return frame_list


class NukeSubmitter(BaseSubmitter):
    """BaseSubmitter implementation for Nuke render submissions.

    Headless (no Qt/UI dependency): this is the render submission engine. The
    GUI submitter (``deadline_submitter_for_nuke.py``) adapts its
    ``SubmitterUISettings`` to :class:`NukeSubmitterSettings` and drives these
    same methods, so both the unified API and the GUI produce the job bundle
    through one code path — matching the Maya submitter's layout.

    ``get_job_template``/``get_parameter_values`` are the builders themselves
    (they are the whole render-bundle logic); they narrow the base-typed
    ``settings`` to :class:`NukeSubmitterSettings` and, unlike Maya, need no
    separate staticmethod builder because there is no cached-scene-context
    orchestration layer to keep out of them.
    """

    def get_settings(self) -> NukeSubmitterSettings:
        script_file = get_nuke_script_file()
        # frame_list records the scene range, but override_frame_range is left at
        # its default (False): _get_frame_list honors that flag as-is, so the native
        # fallback to a Write node's own use_limit/first/last (the UI default) is
        # preserved unless a caller explicitly opts into overriding with the scene range.
        return NukeSubmitterSettings(
            job_name=Path(script_file).name if script_file else "Untitled",
            project_path=get_project_path(),
            frame_list=str(nuke.root().frameRange()),
            is_proxy_mode=nuke.root().proxy(),
            input_filenames=[script_file] if script_file else [],
        )

    def get_job_template(
        self,
        settings: BaseSubmitterSettings,
        host_requirements: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = cast("NukeSubmitterSettings", settings)

        # Load the default Nuke render job template, and then fill in
        # scene-specific values it needs.
        with open(Path(__file__).parent / "default_nuke_job_template.yaml") as f:
            job_template = yaml.safe_load(f)

        # Set the job's name and description
        job_template["name"] = settings.job_name
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

        # If "HostRequirements" is provided, inject it into each of the "Step"s.
        if host_requirements:
            for step in job_template.get("steps", []):
                step["hostRequirements"] = host_requirements

        return job_template

    def get_parameter_values(
        self,
        settings: BaseSubmitterSettings,
        queue_parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        settings = cast("NukeSubmitterSettings", settings)

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
            {
                "name": "ProxyMode",
                "value": "true" if settings.is_proxy_mode else "false",
            }
        )

        # Set the ContinueOnError parameter default
        parameter_values.append(
            {
                "name": "ContinueOnError",
                "value": "true" if settings.continue_on_error else "false",
            }
        )

        # Set chunking parameter values
        parameter_values.append(
            {
                "name": "ChunkSize",
                "value": settings.chunk_size,
            }
        )
        parameter_values.append(
            {
                "name": "TargetChunkDuration",
                "value": settings.target_chunk_duration,
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

    def get_asset_references(self, settings: BaseSubmitterSettings) -> AssetReferences:
        outcome = get_scene_asset_references()
        # The UI path surfaces scan problems in a warning dialog so the user can
        # decide whether to proceed. There is no dialog here, so log the same
        # diagnostics rather than silently returning an incomplete reference set
        # (which would submit a job with missing input/output assets).
        if outcome.encountered_exception():
            if outcome.high_level_exception:
                _logger.warning(
                    "Asset reference scan raised an error; the returned "
                    "references may be incomplete: %s",
                    outcome.high_level_exception,
                )
            for node_name, tb in outcome.failed_to_parse_nodes.items():
                _logger.warning(
                    "Failed to parse asset references from node '%s': %s",
                    node_name,
                    tb,
                )
        # Merge the caller's explicit references (per the BaseSubmitterSettings
        # contract: input_filenames/input_directories/output_directories are
        # "merged with scene-detected inputs in get_asset_references") with the
        # scanned ones, mirroring the Maya submitter. get_settings() populates
        # input_filenames with the scene file, so this also ensures that is
        # retained. The GUI path is unaffected — it builds its own AssetReferences
        # from the submit dialog rather than calling this method.
        explicit_references = AssetReferences(
            input_filenames=set(settings.input_filenames),
            input_directories=set(settings.input_directories),
            output_directories=set(settings.output_directories),
        )
        # Return the typed AssetReferences per the BaseSubmitter contract; callers
        # (e.g. the GUI callback / job-bundle writer) call .to_dict() at the
        # serialization boundary.
        return outcome.asset_references.union(explicit_references)
