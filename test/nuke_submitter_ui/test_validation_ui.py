# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Validation feedback and recovery through the real Nuke submitter dialog."""

import yaml
from deadline_test_fixtures.job_bundle import (
    assert_valid_job_bundle,
    find_complete_job_bundle,
)


def test_empty_frame_override_validation_and_recovery(interactive_submitter) -> None:
    """Reject a blank override, then export the corrected range from the same dialog."""
    dialog, export_dir, _scene_file = interactive_submitter

    dialog.switch_to_job_specific_tab()
    dialog.set_frame_range("")
    assert dialog.override_frame_range_enabled()
    dialog.export_bundle_expect_error(
        "Frame range override is enabled but no frame range was provided. "
        "Enter a frame range or disable the override."
    )

    assert find_complete_job_bundle(export_dir) is None
    assert list(export_dir.iterdir()) == [], "Validation failure left exported files behind"

    # Keeping the same dialog exercises recovery after dismissing the validation error.
    dialog.switch_to_job_specific_tab()
    dialog.set_frame_range("7-9")
    dialog.export_bundle()

    bundle = find_complete_job_bundle(export_dir)
    assert bundle is not None, f"No complete corrected bundle under {export_dir}"
    assert list(export_dir.rglob("template.yaml")) == [
        bundle / "template.yaml"
    ], "Expected exactly one exported bundle after recovery"
    assert_valid_job_bundle(bundle / "template.yaml")

    with (bundle / "parameter_values.yaml").open(encoding="utf-8") as stream:
        parameter_values = yaml.safe_load(stream)["parameterValues"]
    frames = [parameter["value"] for parameter in parameter_values if parameter["name"] == "Frames"]
    assert frames == ["7-9"], f"Corrected frame range was not exported: {frames}"
