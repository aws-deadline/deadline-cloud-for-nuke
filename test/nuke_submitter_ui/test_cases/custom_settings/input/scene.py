# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene script for the custom_settings case — executed INSIDE GUI Nuke by
the suite's opener hook (test/nuke_submitter_ui/_opener/menu.py).

Contract: build the scene, then save it to the path named by the
NUKE_SUBMITTER_UI_SCENE_FILE environment variable. Keep everything
deterministic — the exported bundle is compared against committed goldens.

A minimal single-write-node scene: this case is about the job properties
set in the dialog, so the scene is kept as plain as possible.
"""

import os

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
scene_dir = os.path.dirname(scene_file)

nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(10)

color_wheel = nuke.nodes.ColorWheel()
write_node = nuke.nodes.Write(name="Write1")
write_node.setInput(0, color_wheel)
write_node["file"].setValue(os.path.join(scene_dir, "renders", "custom_settings.####.exr"))

nuke.scriptSaveAs(scene_file, overwrite=1)
