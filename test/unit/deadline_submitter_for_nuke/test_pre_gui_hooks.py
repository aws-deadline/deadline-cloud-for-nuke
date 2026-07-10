# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Unit tests for the Nuke submitter's pre-GUI hook integration.

``_show_nuke_render_submitter`` calls deadline-cloud's ``run_pre_gui_hooks`` (env-only, since
Nuke has no on-disk bundle) and then applies the merged output with deadline-cloud's generic
``apply_pre_gui_output``. The full submitter needs a running Nuke, so it is exercised in the
integration suite; here we verify the DCC-relevant contract headless: Nuke's
``SubmitterUISettings`` has no ``.parameters`` list, so every hook parameter must flow to the
dialog's shared parameter values (name/description land on the settings object). The nuke / Qt
modules are stubbed by ``test/unit/__init__`` so the module imports.
"""

from typing import Optional

from deadline.client.ui.pre_gui_hooks import apply_pre_gui_output

from deadline.nuke_submitter.data_classes import SubmitterUISettings


def _settings() -> SubmitterUISettings:
    s = SubmitterUISettings()
    s.name = "Original"
    s.description = ""
    return s


def test_name_and_description_applied_to_settings():
    """A hook's name/description overwrite the settings fields (Nuke has no .parameters list,
    so these land directly on the dataclass)."""
    settings = _settings()
    shared = {"RezPackages": "nuke-15 deadline_cloud_for_nuke"}

    apply_pre_gui_output({"name": "PREGUI RAN", "description": "from pipeline"}, settings, shared)

    assert settings.name == "PREGUI RAN"
    assert settings.description == "from pipeline"


def test_hook_parameters_flow_to_shared_values():
    """Nuke's SubmitterUISettings has no .parameters list, so every hook parameter (queue
    params, deadline: properties) lands in the shared values the dialog is seeded with,
    overriding the Nuke-computed defaults on key collision."""
    settings = _settings()
    shared = {"RezPackages": "nuke-15 deadline_cloud_for_nuke", "CondaPackages": "nuke=15.*"}

    apply_pre_gui_output(
        {
            "parameters": {
                "deadline:priority": 88,
                "RezPackages": "nuke-15 custom_pkg",  # overrides the default
            }
        },
        settings,
        shared,
    )

    assert shared["deadline:priority"] == 88
    assert shared["RezPackages"] == "nuke-15 custom_pkg"
    assert shared["CondaPackages"] == "nuke=15.*"  # untouched keys preserved


def test_empty_output_is_a_noop():
    """No pre-GUI hook output leaves the settings and shared values unchanged."""
    settings = _settings()
    shared = {"RezPackages": "pkg"}

    apply_pre_gui_output({}, settings, shared)

    assert settings.name == "Original"
    assert settings.description == ""
    assert shared == {"RezPackages": "pkg"}


def test_partial_output_only_touches_present_keys():
    """Only the keys present in the output are applied; others keep their prior values."""
    settings = _settings()
    settings.description = "keep me"
    shared: dict = {}

    apply_pre_gui_output({"name": "NewName"}, settings, shared)

    assert settings.name == "NewName"
    assert settings.description == "keep me"  # not overwritten
    assert shared == {}  # no parameters in output


def test_falsy_output_is_a_noop():
    """The submitter passes ``pre_gui_output or {}`` into apply_pre_gui_output, so the values
    run_pre_gui_hooks can actually produce for the no-hooks path — ``{}`` today, or ``None`` if
    the contract ever changed — must both be safe no-ops that leave settings/shared untouched."""
    falsy_values: list[Optional[dict]] = [{}, None]
    for falsy in falsy_values:
        settings = _settings()
        shared = {"RezPackages": "nuke-15 deadline_cloud_for_nuke"}

        # Mirror the submitter call site: `pre_gui_output or {}`.
        apply_pre_gui_output(falsy or {}, settings, shared)

        assert settings.name == "Original"
        assert settings.description == ""
        assert shared == {"RezPackages": "nuke-15 deadline_cloud_for_nuke"}
