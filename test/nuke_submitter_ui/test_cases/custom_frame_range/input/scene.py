# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene script for the custom_frame_range case — executed INSIDE GUI Nuke
by the suite's opener hook (test/nuke_submitter_ui/_opener/menu.py).

Contract: build the scene, then save it to the path named by the
NUKE_SUBMITTER_UI_SCENE_FILE environment variable. Keep everything
deterministic — the exported bundle is compared against committed goldens.

The scene range (1-100) is deliberately wider than the range the
configurator overrides it with, so the golden's Frames parameter can only
be produced by the override actually taking effect.
"""

import os

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
scene_dir = os.path.dirname(scene_file)

nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(100)

color_wheel = nuke.nodes.ColorWheel()
write_node = nuke.nodes.Write(name="Write1")
write_node.setInput(0, color_wheel)
write_node["file"].setValue(os.path.join(scene_dir, "renders", "custom_frame_range.####.exr"))

nuke.scriptSaveAs(scene_file, overwrite=1)
