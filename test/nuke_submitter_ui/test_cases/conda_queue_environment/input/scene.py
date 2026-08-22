# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene for conda_queue_environment, run inside GUI Nuke by the opener hook.

Minimal on purpose: this case is about the Conda queue environment's fields.
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
write_node["file"].setValue(os.path.join(scene_dir, "renders", "conda_queue_environment.####.exr"))

nuke.scriptSaveAs(scene_file, overwrite=1)
