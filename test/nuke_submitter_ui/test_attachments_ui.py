# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Manual attachment editing through the real GUI, verified in the export."""

from pathlib import Path

import yaml
from deadline_test_fixtures.job_bundle import (
    assert_valid_job_bundle,
    find_complete_job_bundle,
)


def test_manual_attachments_add_remove_and_export(interactive_submitter, tmp_path: Path) -> None:
    dialog, export_dir, scene_file = interactive_submitter
    manual_dir = tmp_path / "manual assets"
    manual_dir.mkdir()
    kept = manual_dir / "keep me.txt"
    removed = manual_dir / "remove me.txt"
    kept.write_text("Manually attached input\n", encoding="utf-8")
    removed.write_text("Removed before export\n", encoding="utf-8")
    output_dir = manual_dir / "output"
    output_dir.mkdir()

    dialog.add_input_file(kept)
    dialog.add_input_file(removed)
    dialog.remove_input_file(removed)
    dialog.add_output_directory(output_dir)
    dialog.export_bundle()

    bundle = find_complete_job_bundle(export_dir)
    assert bundle is not None, f"No complete bundle under {export_dir}"
    assert_valid_job_bundle(bundle / "template.yaml")
    references = yaml.safe_load((bundle / "asset_references.yaml").read_text(encoding="utf-8"))[
        "assetReferences"
    ]
    # Path objects tolerate native separators; the expected paths come from
    # real files created for this run, not hand-authored bundle goldens.
    assert {Path(path) for path in references["inputs"]["filenames"]} == {scene_file, kept}
    assert references["inputs"]["directories"] == []
    assert {Path(path) for path in references["outputs"]["directories"]} == {
        scene_file.parent / "renders",
        output_dir,
    }
    assert references["referencedPaths"] == []
