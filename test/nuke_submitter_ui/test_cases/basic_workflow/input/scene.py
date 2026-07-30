# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene script for the basic_workflow case — executed INSIDE GUI Nuke by
the suite's opener hook (test/nuke_submitter_ui/_opener/menu.py).

Contract: build the scene, then save it to the path named by the
NUKE_SUBMITTER_UI_SCENE_FILE environment variable. Keep everything
deterministic — the exported bundle is compared against committed goldens.
"""

import os

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
scene_dir = os.path.dirname(scene_file)

# Deterministic frame range (also the Frames parameter in the golden bundle).
nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(100)

color_wheel = nuke.nodes.ColorWheel()
write_node = nuke.nodes.Write(name="Write1")
write_node.setInput(0, color_wheel)
# Renders land inside the case's actual/ dir (scene_file lives there), so a
# future render-comparison step can find them next to the bundle output.
write_node["file"].setValue(os.path.join(scene_dir, "renders", "basic_workflow.####.exr"))

nuke.scriptSaveAs(scene_file, overwrite=1)
