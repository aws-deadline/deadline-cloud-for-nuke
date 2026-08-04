# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import nuke
import yaml  # type: ignore[import]
from deadline.client.api import get_deadline_cloud_library_telemetry_client
from deadline.client.config import get_setting, str2bool
from deadline.client.job_bundle import deadline_yaml_dump
from deadline.client.ui import gui_error_handler
import deadline.nuke_submitter.copycat_adaptor as copycat_adaptor_module
from deadline.client.ui.dialogs.submit_job_to_deadline_dialog import (  # type: ignore
    JobBundlePurpose,
    SubmitJobToDeadlineDialog,
)
from deadline.client.ui.pre_gui_hooks import (  # type: ignore
    PreGuiHookContext,
    apply_pre_gui_output,
    qt_hook_confirmation,
    run_pre_gui_hooks,
)

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

from deadline.client.exceptions import DeadlineOperationCanceled, DeadlineOperationError
from deadline.client.job_bundle.submission import AssetReferences

from ._version import version
from ._version import version_tuple as adaptor_version_tuple
from .update_utils import check_and_show_update_dialog
from .assets import (
    get_nuke_script_file,
    get_scene_asset_references,
)
from .data_classes import (
    JobType,
    RenderSettings,
    CopyCatTrainingSettings,
    SubmitterUISettings,
)
from .submitter import (
    NukeSubmitter,
    NukeSubmitterSettings,
    _set_timeouts,
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


def _ui_settings_to_submitter_settings(
    ui_settings: SubmitterUISettings,
) -> NukeSubmitterSettings:
    """Adapt the GUI's RENDER SubmitterUISettings to the headless NukeSubmitterSettings.

    The mirror of the old ``_to_native_settings`` (now inverted): the render
    builders consume :class:`NukeSubmitterSettings` directly, so the GUI settings
    are converted at the submission boundary. ``name`` -> ``job_name``; the
    render-specific fields live on ``jobtype_specific_settings`` (a
    ``RenderSettings``) and are flattened onto the unified settings.

    Only valid for RENDER submissions — CopyCat training keeps its own path.
    """
    render = ui_settings.jobtype_specific_settings
    assert isinstance(render, RenderSettings)
    return NukeSubmitterSettings(
        job_name=ui_settings.name,
        description=ui_settings.description,
        frame_list=render.frame_list,
        override_frame_range=render.override_frame_range,
        input_filenames=list(ui_settings.input_filenames),
        input_directories=list(ui_settings.input_directories),
        output_directories=list(ui_settings.output_directories),
        write_node_selection=render.write_node_selection,
        view_selection=render.view_selection,
        is_proxy_mode=render.is_proxy_mode,
        continue_on_error=render.continue_on_error,
        chunk_size=render.chunk_size,
        target_chunk_duration=render.target_chunk_duration,
        include_gizmos_in_job_bundle=ui_settings.include_gizmos_in_job_bundle,
        include_adaptor_wheels=ui_settings.include_adaptor_wheels,
        timeouts_enabled=ui_settings.timeouts_enabled,
        on_run_timeout_seconds=ui_settings.on_run_timeout_seconds,
        on_enter_timeout_seconds=ui_settings.on_enter_timeout_seconds,
        on_exit_timeout_seconds=ui_settings.on_exit_timeout_seconds,
    )


def _get_copycat_job_template(settings: SubmitterUISettings) -> dict[str, Any]:
    """Build the OpenJD job template for a CopyCat training submission.

    CopyCat training is a GUI-only job type and is not expressed through the
    unified NukeSubmitter (which is render-only), so its small template builder
    stays here. Timeout patching is shared with the render engine via
    ``_set_timeouts``.
    """
    with open(Path(__file__).parent / "copycat_job_template.yaml") as f:
        job_template = yaml.safe_load(f)

    # Set the job's name and description
    job_template["name"] = settings.name
    if settings.description:
        job_template["description"] = settings.description

    # Set the timeouts for each action:
    _set_timeouts(job_template, settings)

    return job_template


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


def _pre_gui_hook_confirm_callback(parent):
    """Choose the confirmation callback for pre-GUI hooks based on the auto_accept setting.

    Returns ``None`` (run hooks without prompting) when ``settings.auto_accept`` is enabled,
    otherwise the standard Qt confirmation dialog from ``qt_hook_confirmation``. Kept as a small
    helper so the auto_accept branch can be unit-tested headlessly.
    """
    if str2bool(get_setting("settings.auto_accept")):
        return None
    return qt_hook_confirmation(parent)


def _show_nuke_render_submitter(
    parent, job_type: JobType, f=Qt.WindowFlags()
) -> Optional[SubmitJobToDeadlineDialog]:
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

        # Render goes through the unified NukeSubmitter engine, so the GUI and
        # the headless API build the render bundle through one code path.
        # CopyCat training is GUI-only and keeps its own small builder.
        if settings.get_job_type() == JobType.RENDER:
            submitter = NukeSubmitter()
            nuke_settings = _ui_settings_to_submitter_settings(settings)
            # get_job_template injects host_requirements into every step.
            job_template = submitter.get_job_template(nuke_settings, host_requirements)
            parameter_values = submitter.get_parameter_values(nuke_settings, queue_parameters)
        else:
            job_template = _get_copycat_job_template(settings)
            # If "HostRequirements" is provided, inject it into each of the "Step"
            if host_requirements:
                for step in job_template["steps"]:
                    step["hostRequirements"] = host_requirements
            parameter_values = _get_copycat_training_parameter_values(settings, queue_parameters)

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

        shared_parameter_values = {
            "RezPackages": rez_packages,
            "CondaPackages": conda_packages,
        }

        # Run pre-GUI hooks so studios can pre-populate dialog fields before it opens. Nuke has
        # no on-disk job bundle at this point, so hooks are sourced from DEADLINE_HOOKS_DIR only
        # (bundle_dir=None), gated by settings.allow_environment_hooks. The confirmation prompt is
        # skipped when auto_accept is set; otherwise the standard dialog is shown.
        #
        # This runs once per Nuke session, on first open: the dialog is cached in the
        # g_*_submitter_dialog globals and reused via refresh() on later opens (see the else
        # branch below), so hooks are not re-run on every open. This is intentional and mirrors
        # the Maya submitter; re-running hooks per open would require threading the merged
        # parameters through refresh(), which does not accept initial_shared_parameter_values.
        try:
            pre_gui_output = run_pre_gui_hooks(
                PreGuiHookContext(
                    bundle_dir=None,
                    job_name=render_settings.name,
                    submitter_name="nuke",
                    parameters=dict(shared_parameter_values),
                ),
                confirm_callback=_pre_gui_hook_confirm_callback(parent),
            )
        except DeadlineOperationCanceled:
            # The user declined the hook confirmation prompt. This is a normal cancellation, not
            # an error, so abort opening the dialog silently. Without this, the exception would
            # propagate to the outer gui_error_handler and surface a spurious "Error opening AWS
            # Deadline Cloud Submitter" dialog for what is a deliberate "No" click.
            return None
        # run_pre_gui_hooks returns {} when no hooks run and raises DeadlineOperationCanceled if
        # the user declines; `or {}` is defensive against any future contract change so the
        # common no-hooks path can never pass a falsy value into apply_pre_gui_output.
        apply_pre_gui_output(pre_gui_output or {}, render_settings, shared_parameter_values)

        submitter_dialog = SubmitJobToDeadlineDialog(
            job_setup_widget_type=SceneSettingsWidget,
            initial_job_settings=render_settings,
            initial_shared_parameter_values=shared_parameter_values,
            auto_detected_attachments=asset_references_parsing_outcome.asset_references,
            attachments=attachments,
            on_create_job_bundle_callback=on_create_job_bundle_callback,  # type: ignore
            parent=parent,
            f=f,
            show_host_requirements_tab=True,
            use_deadline_cloud_v2_channel=True,
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
