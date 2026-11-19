# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Cross-platform asset ordering must not hide missing or changed assets."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import]

from _utils import OCIO_CONFIGS_PLACEHOLDER, assert_bundle_matches_golden


def _bundle(directory: Path, filenames: list[str]) -> Path:
    directory.mkdir()
    for name in ("template.yaml", "parameter_values.yaml"):
        (directory / name).write_text("{}\n", encoding="utf-8")
    (directory / "asset_references.yaml").write_text(
        yaml.safe_dump({"assetReferences": {"inputs": {"filenames": filenames}}}),
        encoding="utf-8",
    )
    return directory


def test_asset_order_is_independent_of_installation_path(tmp_path: Path) -> None:
    expected = _bundle(
        tmp_path / "expected",
        [f"{OCIO_CONFIGS_PLACEHOLDER}/nuke-default/config.ocio", "C:/Dev/scene.nk"],
    )
    actual = _bundle(
        tmp_path / "actual",
        [
            "C:/Dev/scene.nk",
            r"C:\Program Files\Nuke17.1v2\plugins\OCIOConfigs\configs\nuke-default\config.ocio",
        ],
    )
    assert_bundle_matches_golden(expected, actual)


@pytest.mark.parametrize(
    "actual_assets",
    [
        ["scene.nk"],
        ["scene.nk", "config.ocio", "config.ocio"],
        ["scene.nk", "another-config.ocio"],
    ],
    ids=["missing", "duplicate", "different-config"],
)
def test_asset_differences_still_fail(tmp_path: Path, actual_assets: list[str]) -> None:
    expected = _bundle(tmp_path / "expected", ["scene.nk", "config.ocio"])
    actual = _bundle(tmp_path / "actual", actual_assets)
    with pytest.raises(AssertionError, match="Job bundles differ"):
        assert_bundle_matches_golden(expected, actual)
