# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Configurator for ocio_stock_write1.

First half of the Squish ocio_gui case, which submitted the same OCIO scene
once per write node.
"""


def configure(dialog) -> None:
    dialog.set_job_name("OCIO Config Job Submission")
    dialog.set_job_description(
        "This test includes a render that includes the use of OCIO color management."
    )
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node("Write1")
    selected = dialog.selected_write_node()
    assert selected == "Write1", f"write-node combo shows {selected!r}"
