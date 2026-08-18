# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the write_node_selection_all case.

Second half of the Squish write_node_gui case (see
write_node_selection_single for the split). Submits every write node from the
same two-node scene.

"All write nodes" is the dialog default, and the assertion comes first for
that reason: selecting before checking would quietly correct a changed
default and the check could never fail. The select call stays so the case
still states what it submits, and is a no-op while the default holds.
"""

from pages import WRITE_NODES_ALL


def configure(dialog) -> None:
    dialog.set_job_name("Multiple Write Node Submission Test")
    dialog.set_job_description("All write nodes option selected for submission")
    dialog.switch_to_job_specific_tab()
    assert dialog.selected_write_node() == WRITE_NODES_ALL
    dialog.select_write_node(WRITE_NODES_ALL)
