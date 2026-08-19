# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the write_node_selection_all case.

Second half of the Squish write_node_gui case (see
write_node_selection_single for the split). Submits every write node from the
same two-node scene.

The combo is driven to Write1 and back so this exercises switching to
all-nodes, as the Squish case did on its second submission in the same
session. Each case here starts from a fresh dialog, so without that detour
the selection would already be the default and nothing would be exercised.
The default is checked first, before anything moves it.
"""

from pages import WRITE_NODES_ALL


def configure(dialog) -> None:
    dialog.set_job_name("Multiple Write Node Submission Test")
    dialog.set_job_description("All write nodes option selected for submission")
    dialog.switch_to_job_specific_tab()

    opened_with = dialog.selected_write_node()
    assert opened_with == WRITE_NODES_ALL, f"dialog opened showing {opened_with!r}"

    dialog.select_write_node("Write1")
    dialog.select_write_node(WRITE_NODES_ALL)
    selected = dialog.selected_write_node()
    assert selected == WRITE_NODES_ALL, f"write-node combo shows {selected!r}"
