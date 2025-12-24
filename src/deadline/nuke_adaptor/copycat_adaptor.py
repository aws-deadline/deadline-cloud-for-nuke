import argparse
import json
import logging
import pathlib
import re
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

error_regex = re.compile(r".*ERROR: (.+)")
step_complete_regex = re.compile(r"\[Step:(\d+)/(\d+)\].*")

_current_percent_done = 0
def _report_progress(current_step, total_steps):
    global _current_percent_done
    # round progress to a single decimal point
    progress = round(current_step * 100.0 / total_steps, 1)
    if progress != _current_percent_done:
        _current_percent_done = progress
        return f'openjd_progress: {progress}'


_error_encountered = False
# returning message rather than printing to make this unit testable
def report_openjd_messages(line) -> Optional[str]:
    global _error_encountered
    if (match := error_regex.match(line)) != None:
        # error message is captured in group(1)
        _error_encountered = True
        return f'openjd_fail: {match.group(1)}'
    if (match := step_complete_regex.match(line)) != None:
        return _report_progress(current_step=int(match.group(1)), total_steps=int(match.group(2)))


def _stream_reader(stream_name, stream, logger):
    for line in iter(stream.readline, ""):
        line_stripped = line.rstrip()
        if msg := report_openjd_messages(line_stripped):
            # msg will be the str of the openjd message if there is something to print,
            # None otherwise
            logger.info(msg)
        logger.info(f'{stream_name}: {line_stripped}')


def get_nuke_remap_string(path_mapping_rules: List[Dict[str, str]]) -> str:
    return ','.join(
        pathlib.Path(path).as_posix()
        for rule in path_mapping_rules
        for path in (rule['source_path'], rule['destination_path'])
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = 'NukeCopyCatAdaptor',
        description = (
            'Wrapper around executing CopyCat nodes in Nuke. Handle path mapping from job attachments'
            ' and emmision of OpenJD status messages to stdout'
        ),
    )

    parser.add_argument('--nuke', type=pathlib.Path, help='Path to the Nuke exe.')
    parser.add_argument('--path-mapping-rules', type=pathlib.Path, help='Path to path-mapping rules file.')
    parser.add_argument('--nuke-script', type=pathlib.Path, help='Path to the nuke script file.')
    parser.add_argument('--copycat-node', type=str, help='Name of the copycat node to train.')
    parser.add_argument(
        '--run-as-shell',
        action='store_true',
        default=False,
        help='Uses shell=true when launching the passed in executable. This just exists for unit testing'
    )

    args = parser.parse_args()

    nuke_run_copycat_args = [
        str(args.nuke),
        '-X',
        args.copycat_node,
        '-F', # when running copycat we specify to execute only a single "frame"
        '1',
        '--gpu',
        str(args.nuke_script),
    ]

    if args.path_mapping_rules:
        with open(args.path_mapping_rules) as f:
            path_mapping_rules = json.loads(f.read())["path_mapping_rules"]

        nuke_path_mapping_string = get_nuke_remap_string(path_mapping_rules)

        nuke_run_copycat_args += [
            '--remap',
            nuke_path_mapping_string,
        ]

    nuke_process = subprocess.Popen(
        nuke_run_copycat_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=args.run_as_shell,
        text=True
    )

    logging.basicConfig(format='%(message)s', stream=sys.stdout)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    stdout_reader = threading.Thread(target=_stream_reader, args=('STDOUT', nuke_process.stdout, logger))
    stdout_reader.daemon = False

    stderr_reader = threading.Thread(target=_stream_reader, args=('STDERR', nuke_process.stderr, logger))
    stderr_reader.daemon = False

    stdout_reader.start()
    stderr_reader.start()

    while nuke_process.poll() is None:
        # wait for training to finish
        time.sleep(0.1)

    stdout_reader.join()
    stderr_reader.join()

    if _error_encountered:
        sys.exit(1)
    else:
        sys.exit(0)
