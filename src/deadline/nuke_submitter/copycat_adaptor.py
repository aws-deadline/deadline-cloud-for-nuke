import argparse
import json
import logging
import re
import subprocess
import sys
import threading
import time
import pathlib
from typing import Dict, List, Optional, TextIO, Tuple

error_regex = re.compile(r".*(ERROR: |Error ?:|Eddy\[ERROR\])(.+)")
step_complete_regex = re.compile(r"\[Step:(\d+)/(\d+)\].*")


def _report_progress(
    current_step: int, total_steps: int, current_percent_done: float
) -> Tuple[Optional[str], float]:
    """Determines if we should write an openjd_progress message.
    If we should, returns the openjd_progress message to print. otherwise, returns None

    Args:
        current_step (int): the step number we have just completed.
        total_step (int): the total number of steps in the training job
        current_percent_done (float): the last progress percent that we have outputed.

    Returns:
        Optional[str]: If we should not print, returns None.
                       If we should, returns the openjd_progress message to print
        float:         Updated current percent done value
    """
    # round progress to a single decimal point
    progress = round(current_step * 100.0 / total_steps, 1)
    if progress != current_percent_done:
        return f"openjd_progress: {progress}", progress
    else:
        return None, progress


def report_openjd_messages(line: str, current_percent_done: float) -> Tuple[Optional[str], float]:
    """Takes in a single line output from the Nuke executable. If we should print an openjd
    message, e.g. a progress or error message, then returns a string of what we should print.
    Otherwise, returns None

    Args:
        line (str): line output from either stdout or stderr of the nuke executable
    Returns:
        Optional[str]: None is if there isn't anything we should print. Otherwise if there is a message
                       to report, returns a str of the message we should print.
        float:         Updated current_percent_done value
    """
    if (match := error_regex.match(line)) is not None:
        # error_regex is written so that the error message in line will be stored in match.group(2)
        return f"openjd_fail: {match.group(2)}", current_percent_done
    elif (match := step_complete_regex.match(line)) is not None:
        return _report_progress(
            current_step=int(match.group(1)),
            total_steps=int(match.group(2)),
            current_percent_done=current_percent_done,
        )
    else:
        return None, current_percent_done


def _stream_reader(stream_name: str, stream: TextIO, logger: logging.Logger):
    """Handler given to a thread to process either the stdout or stderr stream from the nuke executable"""
    for line in iter(stream.readline, ""):
        line_stripped = line.rstrip()
        current_percent_done = 0.0
        msg, current_percent_done = report_openjd_messages(line_stripped, current_percent_done)
        if msg is not None:
            logger.info(msg)
        logger.info(f"{stream_name}: {line_stripped}")


def get_nuke_remap_string(path_mapping_rules: List[Dict[str, str]]) -> str:
    return ",".join(
        pathlib.Path(path.replace("\\", "/")).as_posix()
        for rule in path_mapping_rules
        for path in (rule["source_path"], rule["destination_path"])
    )


def run_adaptor(
    nuke_path: str,
    path_mapping_rules_path: Optional[str],
    nuke_script_path: str,
    copycat_node_name: str,
    using_stubber_for_nuke: bool,
) -> int:
    """Runs the nuke executable with path mapping.
    Will write output from the nuke executable, as well as any openjd messages we should print to stdout

    arguments map 1-to-1 with the CLI arguments. see the help strings in parse_args for a description of what they do.

    Returns:
        int: exit code for the adaptor
    """

    nuke_run_copycat_args = [
        nuke_path,
        "-X",
        copycat_node_name,
        "-F",  # when running copycat we specify to execute only a single "frame"
        "1",
        "--gpu",
    ]

    if path_mapping_rules_path:
        with open(path_mapping_rules_path) as f:
            path_mapping_rules = json.loads(f.read())["path_mapping_rules"]

        nuke_path_mapping_string = get_nuke_remap_string(path_mapping_rules)

        nuke_run_copycat_args += [
            "--remap",
            nuke_path_mapping_string,
        ]

    nuke_run_copycat_args.append(nuke_script_path)  # positional argument needs to be last

    if using_stubber_for_nuke:
        nuke_run_copycat_args.insert(0, "python")

    nuke_process = subprocess.Popen(
        nuke_run_copycat_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    stdout_reader = threading.Thread(
        target=_stream_reader, args=("STDOUT", nuke_process.stdout, logger)
    )
    stdout_reader.daemon = False

    stderr_reader = threading.Thread(
        target=_stream_reader, args=("STDERR", nuke_process.stderr, logger)
    )
    stderr_reader.daemon = False

    stdout_reader.start()
    stderr_reader.start()

    while nuke_process.poll() is None:
        # wait for training to finish
        time.sleep(0.1)

    stdout_reader.join()
    stderr_reader.join()

    return nuke_process.returncode


def parse_args() -> argparse.Namespace:
    """Handle CLI arguments"""
    parser = argparse.ArgumentParser(
        prog="NukeCopyCatAdaptor",
        description=(
            "Wrapper around executing CopyCat nodes in Nuke. Handle path mapping from job attachments"
            " and emission of OpenJD status messages to stdout"
        ),
    )

    parser.add_argument("--nuke", type=str, help="Path to the Nuke exe.", required=True)
    parser.add_argument("--path-mapping-rules", type=str, help="Path to path-mapping rules file.")
    parser.add_argument(
        "--nuke-script", type=str, help="Path to the nuke script file.", required=True
    )
    parser.add_argument(
        "--copycat-node", type=str, help="Name of the copycat node to train.", required=True
    )
    parser.add_argument(
        "--run-stubbed",
        action="store_true",
        default=False,
        help=(
            "informs the adaptor to expect a path to a python script as the argument to --nuke rather than "
            "an excutable. the adaptor will use python to run this script rather than executing it directly "
            " in this mode. this flag is just used for local testing"
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    sys.exit(
        run_adaptor(
            nuke_path=args.nuke,
            path_mapping_rules_path=args.path_mapping_rules,
            nuke_script_path=args.nuke_script,
            copycat_node_name=args.copycat_node,
            using_stubber_for_nuke=args.run_stubbed,
        )
    )
