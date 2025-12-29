import subprocess
import sys

from deadline.nuke_adaptor.copycat_adaptor import (
    get_nuke_remap_string,
    report_openjd_messages,
)

def test_report_openjd_messages_progress():
    msg = report_openjd_messages("[Step:1/3] some other stuff")
    assert msg == "openjd_progress: 33.3"


def test_report_openjd_messages_exception():
    msg = report_openjd_messages("some stuff ERROR: error message here")
    assert msg == "openjd_fail: error message here"


def test_path_remapping():
    path_mapping_rules = [
        {
            "source_path": "x:\\some\\path\\to\\somewhere",
            "destination_path": "/new/path/to",
        },
        {
            "source_path": "x:\\another\\path\\to\\somewhere",
            "destination_path": "Y:\\new\\path\\to\\elsewhere",
        },
    ]

    remap_str = get_nuke_remap_string(path_mapping_rules)
    assert remap_str == (
        "x:/some/path/to/somewhere,/new/path/to,x:/another/path/to/somewhere,Y:/new/path/to/elsewhere"
    )
