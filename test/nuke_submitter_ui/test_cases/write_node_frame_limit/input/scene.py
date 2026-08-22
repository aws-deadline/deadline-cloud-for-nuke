# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene script for the write_node_frame_limit case — executed INSIDE GUI
Nuke by the suite's opener hook (test/nuke_submitter_ui/_opener/menu.py).

Contract: build the scene, then save it to the path named by the
NUKE_SUBMITTER_UI_SCENE_FILE environment variable. Keep everything
deterministic — the exported bundle is compared against committed goldens.

Write1 carries its own frame-range limit (use_limit, 5-10) inside a much
wider scene range (1-100). The submitter prefers a selected write node's
own limit over the scene range when the override is off, so the golden's
Frames parameter (5-10) can only be produced by that limit being honored.
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
write_node["file"].setValue(os.path.join(scene_dir, "renders", "write_node_frame_limit.####.exr"))
write_node["use_limit"].setValue(True)
write_node["first"].setValue(5)
write_node["last"].setValue(10)

nuke.scriptSaveAs(scene_file, overwrite=1)
