# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Helpers and the local golden-bundle normalization policy."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from shutil import copy2

from deadline_test_fixtures.job_bundle import (
    BundleNormalization,
    assert_job_bundles_equal,
)

_T0 = time.monotonic()

# Placeholder used in committed expected/job_bundle/ files wherever the
# absolute path of the repo's parent directory appears (scene file, output
# dirs). Replaced with the runtime value before comparison.
PATH_PLACEHOLDER = "PATH_TO_BE_REPLACED"


def log(message: str) -> None:
    elapsed = time.monotonic() - _T0
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[nuke_submitter_ui {timestamp} +{elapsed:6.2f}s] {message}", flush=True)


def repo_parent_path(any_path_in_repo: Path) -> str:
    """The absolute path prefix that PATH_PLACEHOLDER stands for.

    Everything up to (not including) the last literal
    ``deadline-cloud-for-nuke`` in the resolved path — separator included,
    so goldens read ``PATH_TO_BE_REPLACEDdeadline-cloud-for-nuke/...`` and
    expand correctly on any machine. No trailing-separator stripping: the
    prefix must round-trip exactly, and clones with a decorated dir name
    (e.g. ``Bea-1234-deadline-cloud-for-nuke``) don't even end in one.
    """
    return str(any_path_in_repo.resolve()).rsplit("deadline-cloud-for-nuke", 1)[0]


def nuke_bundle_normalization(expected_dir: Path) -> BundleNormalization:
    """Normalization applied to BOTH bundles before structural comparison.

    * Machine-specific absolute paths: committed goldens carry
      ``PATH_PLACEHOLDER``; the runtime repo parent is substituted in.
    * Conda package pins: the integration's own version and the Nuke minor
      version churn with releases; both sides are mapped to a canonical
      form so goldens don't need updating on every version bump.
    """
    return BundleNormalization(
        replacements={PATH_PLACEHOLDER: repo_parent_path(expected_dir)},
        regex_replacements=(
            (
                r"nuke=\d+\.\d+ nuke-openjd=\d+\.\d+\.\*",
                "nuke=VERSION nuke-openjd=VERSION",
            ),
            (
                r"nuke-openjd=\d+\.\d+\.\*",
                "nuke-openjd=VERSION",
            ),
        ),
    )


def assert_bundle_matches_golden(expected_dir: Path, actual_dir: Path) -> None:
    """Structural comparison of the exported bundle against the case golden."""
    assert_job_bundles_equal(
        expected_dir,
        actual_dir,
        normalization=nuke_bundle_normalization(expected_dir),
    )


def copy_bundle_files_flat(bundle_dir: Path, dest: Path) -> None:
    """Copy the exported bundle's files flat into *dest*."""
    log(f"copying bundle files {bundle_dir} -> {dest}")
    for source in bundle_dir.iterdir():
        if source.is_file():
            copy2(source, dest / source.name)
            log(f"  copied {source.name}")


def write_goldens_from_actual(actual_dir: Path, expected_dir: Path) -> None:
    """Regenerate a case's committed goldens from a verified actual bundle.

    Reverse of the path normalization: the runtime repo-parent prefix is
    replaced with ``PATH_PLACEHOLDER`` so the files are machine-independent.
    Used by the ``NUKE_SUBMITTER_UI_UPDATE_GOLDENS=1`` bootstrap mode; review
    the resulting diff before committing.
    """
    expected_dir.mkdir(parents=True, exist_ok=True)
    prefix = repo_parent_path(actual_dir)
    # Only the bundle documents: actual/ also holds the scene and the
    # submitter's sticky-settings sidecar, which are not golden material.
    bundle_files = ("template.yaml", "parameter_values.yaml", "asset_references.yaml")
    for source in sorted(actual_dir.iterdir()):
        if not source.is_file() or source.name not in bundle_files:
            continue
        text = source.read_text(encoding="utf-8")
        (expected_dir / source.name).write_text(
            text.replace(prefix, PATH_PLACEHOLDER), encoding="utf-8"
        )
        log(f"golden written: {expected_dir / source.name}")
