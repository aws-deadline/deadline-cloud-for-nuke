# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Helpers and the local golden-bundle normalization policy."""

from __future__ import annotations

import re
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
# resolved repo root appears (scene file, output dirs). Replaced with the
# runtime value before comparison; independent of the clone's directory name.
PATH_PLACEHOLDER = "<REPO_ROOT>"
_REPO_ROOT = Path(__file__).resolve().parents[2]

# OCIO-managed scenes reference Nuke's stock config, whose path carries the
# install location, the exact Nuke version and the platform's layout. Only the
# tail (which config, which files) is worth pinning.
OCIO_CONFIGS_PLACEHOLDER = "<NUKE_OCIO_CONFIGS>"
# Applied at comparison time and when writing goldens, so committed files are
# already canonical. Anchored on a root or drive rather than "no whitespace",
# so a Windows install under "Program Files" still matches, and either
# separator is accepted because the comparison normalizes them only afterwards.
_PATH_REGEX_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"(?:[A-Za-z]:)?[\\/][^\"'\n]*?[\\/]OCIOConfigs[\\/]configs", OCIO_CONFIGS_PLACEHOLDER),
)


def log(message: str) -> None:
    elapsed = time.monotonic() - _T0
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[nuke_submitter_ui {timestamp} +{elapsed:6.2f}s] {message}", flush=True)


def nuke_bundle_normalization() -> BundleNormalization:
    """Normalization applied to BOTH bundles before structural comparison.

    * Machine-specific absolute paths: committed goldens carry
      ``PATH_PLACEHOLDER`` where the resolved repo root appears, and
      ``OCIO_CONFIGS_PLACEHOLDER`` where Nuke's stock OCIO config tree does.
    * Conda package pins: the integration's own version and the Nuke minor
      version churn with releases; both sides are mapped to a canonical
      form so goldens don't need updating on every version bump. Ordering
      matters: the paired form must match first or the standalone pattern
      would rewrite half of it.
    """
    return BundleNormalization(
        replacements={PATH_PLACEHOLDER: str(_REPO_ROOT)},
        regex_replacements=_PATH_REGEX_REPLACEMENTS
        + (
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
        normalization=nuke_bundle_normalization(),
    )


def copy_bundle_files_flat(bundle_dir: Path, dest: Path) -> None:
    """Copy the exported bundle's files flat into *dest*."""
    names = sorted(source.name for source in bundle_dir.iterdir() if source.is_file())
    for name in names:
        copy2(bundle_dir / name, dest / name)
    log(f"copied bundle files {names} -> {dest}")


def write_goldens_from_actual(actual_dir: Path, expected_dir: Path) -> None:
    """Regenerate a case's committed goldens from a verified actual bundle.

    Reverse of the path normalization: the runtime repo-parent prefix is
    replaced with ``PATH_PLACEHOLDER`` so the files are machine-independent.
    Used by the ``NUKE_SUBMITTER_UI_UPDATE_GOLDENS=1`` bootstrap mode; review
    the resulting diff before committing.
    """
    expected_dir.mkdir(parents=True, exist_ok=True)
    # Iterate the required documents (not the directory) so a bundle that is
    # missing one raises here instead of silently writing incomplete goldens.
    # actual/ also holds the scene and the submitter's sticky-settings
    # sidecar, which are not golden material.
    for name in ("template.yaml", "parameter_values.yaml", "asset_references.yaml"):
        text = (actual_dir / name).read_text(encoding="utf-8")
        text = text.replace(str(_REPO_ROOT), PATH_PLACEHOLDER)
        for pattern, replacement in _PATH_REGEX_REPLACEMENTS:
            text = re.sub(pattern, replacement, text)
        (expected_dir / name).write_text(text, encoding="utf-8")
        log(f"golden written: {expected_dir / name}")
