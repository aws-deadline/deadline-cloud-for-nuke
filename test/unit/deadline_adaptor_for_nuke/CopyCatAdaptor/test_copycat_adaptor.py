import subprocess
import pytest

import deadline.nuke_adaptor.copycat_adaptor as copycat_adaptor_module
import test.unit.deadline_adaptor_for_nuke.CopyCatAdaptor.stubbed_nuke as stubbed_nuke_module
from deadline.nuke_adaptor.copycat_adaptor import (
    get_nuke_remap_string,
    report_openjd_messages,
)
from test.unit.deadline_adaptor_for_nuke.CopyCatAdaptor.stubbed_nuke import (
    fail_case_lines,
    happy_case_lines,
    DestStream,
)


def test_report_openjd_messages_progress():
    msg, progress = report_openjd_messages("[Step:1/3] some other stuff", 0.0)
    assert msg == "openjd_progress: 33.3"
    assert progress == 33.3


def test_report_openjd_messages_progress_same_percent_not_repeated():
    msg, progress = report_openjd_messages("[Step:1/3] some other stuff", 33.3)
    assert msg is None
    assert progress == 33.3


@pytest.mark.parametrize("error_flag", ["ERROR: ", "Error:", "Error :", "Eddy[ERROR]"])
def test_report_openjd_messages_exception(error_flag):
    msg, progress = report_openjd_messages(f"some stuff {error_flag}error message here", 0.5)
    assert msg == "openjd_fail: error message here"
    assert progress == 0.5


def test_report_openjd_messages_nothing():
    msg, progress = report_openjd_messages("some stuff not an error not progress", 0.5)
    assert msg is None
    assert progress == 0.5


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


def test_execution_with_stubbed_nuke_success(capsys):
    """Tests the copycat adaptor is able to run a process stubbing nuke and handle the output from stdout and stderr properly"""
    adaptor_args = [
        "--nuke",
        stubbed_nuke_module.__file__,
        "--run-stubbed",  # special arg so that we can pass in a python script to stub the nuke executable
        "--copycat-node",
        "node",  # stubber doesnt actually use this
        "--nuke-script",
        "happy_case",  # we use this argument to signal to the stubber whether to act out the happy or fail case
    ]
    # run the adaptor with the stubber instead of actual nuke
    proc = subprocess.run(
        f"python -u {copycat_adaptor_module.__file__} " + " ".join(adaptor_args),
        check=False,
        shell=True,
        capture_output=True,
        text=True,
    )
    # just for debugging failures, not functional to the test
    print(proc.stdout)
    print(proc.stderr)

    # confirm all the expected text was written to stdout, and that the adaptor exited as expected
    stdout_lines = proc.stdout.split("\n")
    exit_code = proc.returncode

    expected_open_jd_messages = [
        "openjd_progress: 3.3",
        "openjd_progress: 33.3",
        "openjd_progress: 66.7",
        "openjd_progress: 100.0",
    ]

    assert exit_code == 0
    for message in expected_open_jd_messages:
        assert message in [stdout_line for stdout_line in stdout_lines]
    for line in happy_case_lines:
        prefix = "STDOUT: " if line.dest == DestStream.STDOUT else "STDERR: "
        prefixed_text = f"{prefix}{line.text}"
        assert prefixed_text in [stdout_line for stdout_line in stdout_lines]


def test_execution_with_stubbed_nuke_fail():
    """Tests the copycat adaptor is able to run a process stubbing nuke and handle the output from stdout and stderr properly"""
    adaptor_args = [
        "--nuke",
        stubbed_nuke_module.__file__,
        "--run-stubbed",  # special arg so that we can pass in a python script to stub the nuke executable
        "--copycat-node",
        "node",  # stubber doesnt actually use this
        "--nuke-script",
        "fail_case",  # we use this argument to signal to the stubber whether to act out the happy or fail case
    ]
    # run the adaptor with the stubber instead of actual nuke
    proc = subprocess.run(
        f"python -u {copycat_adaptor_module.__file__} " + " ".join(adaptor_args),
        check=False,
        shell=True,
        capture_output=True,
        text=True,
    )
    # just for debugging failures, not functional to the test
    print(proc.stdout)
    print(proc.stderr)

    # confirm all the expected text was written to stdout, and that the adaptor exited as expected
    stdout_lines = proc.stdout.split("\n")
    exit_code = proc.returncode

    expected_open_jd_messages = [
        "openjd_fail: CopyCat1: No valid or writable data directory is selected."
    ]

    assert exit_code != 0
    for message in expected_open_jd_messages:
        assert message in [stdout_line for stdout_line in stdout_lines]
    for line in fail_case_lines:
        prefix = "STDOUT: " if line.dest == DestStream.STDOUT else "STDERR: "
        prefixed_text = f"{prefix}{line.text}"
        assert prefixed_text in [stdout_line for stdout_line in stdout_lines]
