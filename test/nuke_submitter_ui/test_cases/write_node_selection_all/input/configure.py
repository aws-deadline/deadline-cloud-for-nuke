# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the write_node_selection_all case.

Second half of the Squish write_node_gui case (see
write_node_selection_single for the split). Submits every write node from
the same two-node scene. "All write nodes" is the dialog default, so the
selection is asserted rather than clicked — a real regression here would be
the default silently changing, which the assertion catches.
"""

from pages import WRITE_NODES_ALL


def configure(dialog) -> None:
    dialog.set_job_name("Multiple Write Node Submission Test")
    dialog.set_job_description("All write nodes option selected for submission")
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node(WRITE_NODES_ALL)
    assert dialog.selected_write_node() == WRITE_NODES_ALL
