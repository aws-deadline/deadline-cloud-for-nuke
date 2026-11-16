# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Run the OCIO scenes against Nuke's version-specific menu representations."""

from pathlib import Path
import runpy
import sys
from unittest.mock import MagicMock, Mock

import pytest


@pytest.mark.parametrize("case", ["ocio_stock_write1", "ocio_stock_write2"])
@pytest.mark.parametrize(
    "major,choices,expected",
    [
        (16, ["aces_1.2\tACES/aces_1.2\t\t", "nuke-default", "custom"], "aces_1.2"),
        (16, ["aces_1.2", "nuke-default", "custom"], "aces_1.2"),
        (17, ["nuke-default", "custom"], "nuke-default"),
        (16, ["nuke-default", "custom"], None),
        (17, ["custom"], None),
    ],
)
def test_ocio_scene_selects_installed_config(monkeypatch, tmp_path, case, major, choices, expected):
    config = Mock()
    config.values.return_value = choices
    root = {
        "first_frame": Mock(),
        "last_frame": Mock(),
        "colorManagement": Mock(),
        "OCIO_config": config,
    }
    nuke = Mock(env={"NukeVersionMajor": major})
    nuke.root.return_value = root
    nuke.nodes.Write.side_effect = lambda **_: MagicMock()
    monkeypatch.setitem(sys.modules, "nuke", nuke)
    scene_file = tmp_path / "scene.nk"
    monkeypatch.setenv("NUKE_SUBMITTER_UI_SCENE_FILE", str(scene_file))
    scene = (
        Path(__file__).resolve().parents[1]
        / "nuke_submitter_ui"
        / "test_cases"
        / case
        / "input"
        / "scene.py"
    )

    if expected is None:
        with pytest.raises(RuntimeError, match="Required stock OCIO config"):
            runpy.run_path(str(scene))
        config.setValue.assert_not_called()
        nuke.scriptSaveAs.assert_not_called()
    else:
        runpy.run_path(str(scene))
        config.setValue.assert_called_once_with(expected)
        nuke.scriptSaveAs.assert_called_once_with(str(scene_file), overwrite=1)
