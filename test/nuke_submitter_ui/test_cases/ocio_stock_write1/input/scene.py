# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene for ocio_stock_write1, run inside GUI Nuke by the opener hook.

Colour management is set to OCIO with a pinned stock config, so the submitter adds
the config to the job's environment and input assets. Two write nodes, as the
Squish ocio_gui case had; ocio_stock_write2 builds the same scene and selects
the other one.
"""

import os
from pathlib import Path

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
renders_dir = Path(os.path.dirname(scene_file), "renders").as_posix()

nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(10)
nuke.root()["colorManagement"].setValue("OCIO")
# Nuke 17 removed the legacy ACES files. Keep the original config on older
# installs, and explicitly select the shipped file-backed config on Nuke 17.
stock_config = "nuke-default" if int(nuke.env["NukeVersionMajor"]) == 17 else "aces_1.2"
choices = nuke.root()["OCIO_config"].values()
# Nuke 16 appends tab-separated menu metadata to file-backed config names.
if stock_config not in [choice.split("\t", 1)[0] for choice in choices]:
    raise RuntimeError(f"Required stock OCIO config {stock_config!r} is unavailable: {choices}")
nuke.root()["OCIO_config"].setValue(stock_config)

color_wheel = nuke.nodes.ColorWheel()
for node_name in ("Write1", "Write2"):
    write_node = nuke.nodes.Write(name=node_name)
    write_node.setInput(0, color_wheel)
    write_node["file"].setValue(
        Path(renders_dir, node_name.lower(), f"{node_name.lower()}.####.exr").as_posix()
    )

nuke.scriptSaveAs(scene_file, overwrite=1)
