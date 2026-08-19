# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the write_node_selection_single case.

First half of the Squish write_node_gui case, which submitted twice from one
multi-write-node scene. Each submission is a case here (the runner exports
one bundle per case): this one selects a single write node, and
write_node_selection_all selects every node from the identical scene.

Note on this case's golden: the scene gives each write node its own output
directory, and the exported asset references list BOTH of them even though
only Write1 is submitted — output scanning is scene-wide, not scoped to the
selected write node. That is current behavior, pinned here deliberately; if
scanning is ever scoped to the selection, this golden changes and the
difference becomes a conscious decision rather than a silent one.
"""


def configure(dialog) -> None:
    dialog.set_job_name("Single Write Node Submission Test")
    dialog.set_job_description("Selected single write node for submission")
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node("Write1")
    selected = dialog.selected_write_node()
    assert selected == "Write1", f"write-node combo shows {selected!r}"
