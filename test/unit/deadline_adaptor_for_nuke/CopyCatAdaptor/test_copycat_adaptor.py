import subprocess
import sys

import deadline.nuke_adaptor.copycat_adaptor as copycat_adaptor_module
import test.unit.deadline_adaptor_for_nuke.CopyCatAdaptor.stubbed_nuke as stubbed_nuke_module
from deadline.nuke_adaptor.copycat_adaptor import (
    get_nuke_remap_string,
    report_openjd_messages,
)
from test.unit.deadline_adaptor_for_nuke.CopyCatAdaptor.stubbed_nuke import (
    fail_case_lines,
    happy_case_lines,
)


def test_report_openjd_messages_progress():
    msg = report_openjd_messages('[Step:1/3] some other stuff')
    assert msg == 'openjd_progress: 33.3'


def test_report_openjd_messages_exception():
    msg = report_openjd_messages('some stuff ERROR: error message here')
    assert msg == 'openjd_fail: error message here'


def test_path_remapping():
    path_mapping_rules = [
        {
            'source_path': 'x:\\some\\path\\to\\somewhere',
            'destination_path': '/new/path/to',
        },
        {
            'source_path': 'x:\\another\\path\\to\\somewhere',
            'destination_path': 'Y:\\new\\path\\to\\elsewhere',
        }
    ]

    remap_str = get_nuke_remap_string(path_mapping_rules)
    assert remap_str == (
        'x:/some/path/to/somewhere,/new/path/to,x:/another/path/to/somewhere,Y:/new/path/to/elsewhere'
    )


def test_execution_with_stubbed_nuke_success():
    """ Tests the copycat adaptor is able to run a process stubbing nuke and handle the output from stdout and stderr properly """
    adaptor_args = [
        '--nuke',
        stubbed_nuke_module.__file__,
        '--copycat-node',
        'node', # stubber doesnt actually use this
        '--nuke-script',
        'happy_case' # we use this argument to signal to the stubber whether to act out the happy or fail case
    ]
    # run the adaptor with the stubber instead of actual nuke
    proc = subprocess.run(['python', '-u', copycat_adaptor_module.__file__] + adaptor_args, check=False, shell=True, capture_output=True, text=True)
    # just for debugging failures, not functional to the test
    print(proc.stdout)
    print(proc.stderr)

    # confirm all the expected text was written to stdout, and that the adaptor exited as expected
    stdout_lines = proc.stdout.split('\n')
    exit_code = proc.returncode

    expected_open_jd_lines = [
        'openjd_progress: 3.3',
        'openjd_progress: 33.3',
        'openjd_progress: 66.7',
        'openjd_progress: 100.0'
    ]

    assert exit_code == 0
    for line in expected_open_jd_lines:
        assert any([line == stdout_line for stdout_line in stdout_lines])
    for line in happy_case_lines:
        prefix = 'STDOUT: ' if line.dest == sys.stdout else 'STDERR: '
        prefixed_text = f'{prefix}{line.text}'
        assert any([prefixed_text == stdout_line for stdout_line in stdout_lines])


def test_execution_with_stubbed_nuke_fail():
    """ Tests the copycat adaptor is able to run a process stubbing nuke and handle the output from stdout and stderr properly """
    adaptor_args = [
        '--nuke',
        stubbed_nuke_module.__file__,
        '--copycat-node',
        'node', # stubber doesnt actually use this
        '--nuke-script',
        'fail_case' # we use this argument to signal to the stubber whether to act out the happy or fail case
    ]
    # run the adaptor with the stubber instead of actual nuke
    proc = subprocess.run(['python', '-u', copycat_adaptor_module.__file__] + adaptor_args, check=False, shell=True, capture_output=True, text=True)
    # just for debugging failures, not functional to the test
    print(proc.stdout)
    print(proc.stderr)

    # confirm all the expected text was written to stdout, and that the adaptor exited as expected
    stdout_lines = proc.stdout.split('\n')
    exit_code = proc.returncode

    expected_open_jd_lines = [
        'openjd_fail: CopyCat1: No valid or writable data directory is selected.'
    ]

    assert exit_code == 1
    for line in expected_open_jd_lines:
        assert any([line == stdout_line for stdout_line in stdout_lines])
    for line in fail_case_lines:
        prefix = 'STDOUT: ' if line.dest == sys.stdout else 'STDERR: '
        prefixed_text = f'{prefix}{line.text}'
        assert any([prefixed_text == stdout_line for stdout_line in stdout_lines])
