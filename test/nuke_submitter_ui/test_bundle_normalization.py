# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Unlicensed regressions for cross-platform asset-list comparison."""

from pathlib import Path

import pytest
import yaml

from _utils import assert_bundle_matches_golden


def make_bundles(tmp_path, install_root):
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    repo_root = str(Path(__file__).resolve().parents[2])
    expected_assets = {
        "assetReferences": {
            "inputs": {
                "filenames": ["<NUKE_OCIO_CONFIGS>/aces_1.2/config.ocio", "<REPO_ROOT>/scene.nk"],
                "directories": [],
            },
            "outputs": {"directories": []},
            "referencedPaths": [],
        }
    }
    actual_assets = {
        "assetReferences": {
            "inputs": {
                "filenames": sorted(
                    [
                        f"{install_root}/OCIOConfigs/configs/aces_1.2/config.ocio",
                        f"{repo_root}/scene.nk",
                    ]
                ),
                "directories": [],
            },
            "outputs": {"directories": []},
            "referencedPaths": [],
        }
    }
    for directory, assets in ((expected, expected_assets), (actual, actual_assets)):
        (directory / "asset_references.yaml").write_text(yaml.safe_dump(assets))
        (directory / "template.yaml").write_text(yaml.safe_dump({"steps": ["first", "second"]}))
        (directory / "parameter_values.yaml").write_text("parameterValues: []\n")
    return expected, actual


@pytest.mark.parametrize("root", ["/usr/local/Nuke16.0v9", "/Applications/Nuke16.0v7"])
def test_asset_order_compared_after_normalization(tmp_path, root):
    expected, actual = make_bundles(tmp_path, root)
    assert_bundle_matches_golden(expected, actual)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_changed_assets_still_fail(tmp_path, change):
    expected, actual = make_bundles(tmp_path, "/usr/local/Nuke16.0v9")
    path = actual / "asset_references.yaml"
    assets = yaml.safe_load(path.read_text())
    filenames = assets["assetReferences"]["inputs"]["filenames"]
    if change == "missing":
        filenames.pop()
    elif change == "extra":
        filenames.append("/unexpected/asset.exr")
    else:
        filenames.append(filenames[0])
    path.write_text(yaml.safe_dump(assets))
    with pytest.raises(AssertionError, match="Job bundles differ"):
        assert_bundle_matches_golden(expected, actual)


def test_template_step_order_preserved(tmp_path):
    expected, actual = make_bundles(tmp_path, "/usr/local/Nuke16.0v9")
    (actual / "template.yaml").write_text(yaml.safe_dump({"steps": ["second", "first"]}))
    with pytest.raises(AssertionError, match="Job bundles differ"):
        assert_bundle_matches_golden(expected, actual)
