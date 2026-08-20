# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene for ocio_stock_write2, run inside GUI Nuke by the opener hook.

Colour management is set to OCIO with the aces_1.2 stock config, as the
Squish case had, so the submitter adds
the config to the job's environment and input assets. Two write nodes, as the
Squish ocio_gui case had; ocio_stock_write1 builds the same scene and selects
the other one.
"""

import os

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
renders_dir = os.path.join(os.path.dirname(scene_file), "renders")

nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(10)
nuke.root()["colorManagement"].setValue("OCIO")
# Pinned, not left at the default: the Squish case used aces_1.2, and its
# larger search-path and LUT tree is what the asset scan walks.
nuke.root()["OCIO_config"].setValue("aces_1.2")

color_wheel = nuke.nodes.ColorWheel()
for node_name in ("Write1", "Write2"):
    write_node = nuke.nodes.Write(name=node_name)
    write_node.setInput(0, color_wheel)
    write_node["file"].setValue(
        os.path.join(renders_dir, node_name.lower(), f"{node_name.lower()}.####.exr")
    )

nuke.scriptSaveAs(scene_file, overwrite=1)
