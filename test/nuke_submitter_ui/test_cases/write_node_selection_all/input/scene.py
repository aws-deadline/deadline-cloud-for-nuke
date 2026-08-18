# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Scene script for the write_node_selection_all case — executed INSIDE GUI
Nuke by the suite's opener hook (test/nuke_submitter_ui/_opener/menu.py).

Contract: build the scene, then save it to the path named by the
NUKE_SUBMITTER_UI_SCENE_FILE environment variable. Keep everything
deterministic — the exported bundle is compared against committed goldens.

Intentionally identical to write_node_selection_single's scene (cases are
self-contained by design, so it is duplicated rather than imported): with
the scene held constant, the difference between the two cases' goldens is
exactly the effect of the write-node selection.
"""

import os

import nuke

scene_file = os.environ["NUKE_SUBMITTER_UI_SCENE_FILE"]
scene_dir = os.path.dirname(scene_file)
renders_dir = os.path.join(scene_dir, "renders")

nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(10)

color_wheel = nuke.nodes.ColorWheel()
for node_name in ("Write1", "Write2"):
    write_node = nuke.nodes.Write(name=node_name)
    write_node.setInput(0, color_wheel)
    # A directory per write node, so the exported asset references show
    # which nodes the submission actually covers.
    write_node["file"].setValue(
        os.path.join(renders_dir, node_name.lower(), f"{node_name.lower()}.####.exr")
    )

nuke.scriptSaveAs(scene_file, overwrite=1)
