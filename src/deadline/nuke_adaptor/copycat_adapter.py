import time
import threading
import subprocess
import argparse
import pathlib
import json
import sys
import re


_current_percent_done = 0
def _report_progress(current_step, total_steps):
    global _current_percent_done
    # round progress to a single decimal point
    progress = round(current_step * 100.0 / total_steps, 1)
    if progress != _current_percent_done:
        _current_percent_done = progress
        print(f'openjd_progress: {progress}')

_error_encountered = False
error_regex = re.compile(r".*ERROR: (.+)")
step_complete_regex = re.compile(r"\[Step:(\d+)/(\d+)\].*")
def _report_openjd_messages(line):
    global _error_encountered
    if (match := error_regex.match(line)) != None:
        # error message is captured in group(1)
        print(f'openjd_fail: {match.group(1)}')
        _error_encountered = True
    elif (match := step_complete_regex.match(line)) != None:
        _report_progress(current_step=int(match.group(1)), total_steps=int(match.group(2)))

def _stream_reader(stream_name, stream):
    for line in iter(stream.readline, ""):
        line_stripped = line.rstrip()
        _report_openjd_messages(line_stripped)
        print(f'{stream_name}: {line_stripped}')

parser = argparse.ArgumentParser(
    prog = 'NukeCopyCatAdapter',
    description = (
        'Wrapper around executing CopyCat nodes in Nuke. Handle path mapping from job attachments'
        ' and emmision of OpenJD status messages to stdout'
    ),
)

parser.add_argument('--nuke', type=pathlib.Path, help='Path to the Nuke exe.')
parser.add_argument('--path-mapping-rules', type=pathlib.Path, help='Path to path-mapping rules file.')
parser.add_argument('--nuke-script', type=pathlib.Path, help='Path to the nuke script file.')
parser.add_argument('--copycat-node', type=str, help='Name of the copycat node to train.')

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
    with open(args.path_mapping_rules, "r") as f:
        path_mapping_rules = json.loads(f.read())["path_mapping_rules"]

    nuke_path_mapping_string = ','.join(
        pathlib.Path(path).as_posix()
        for rule in path_mapping_rules 
        for path in (rule['source_path'], rule['destination_path'])
    )

    print(f"debug - path mapping string: {nuke_path_mapping_string}")

    nuke_run_copycat_args += [
        '--remap',
        nuke_path_mapping_string,
    ]

nuke_process = subprocess.Popen(
    nuke_run_copycat_args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

stdout_reader = threading.Thread(target=_stream_reader, args=('STDOUT', nuke_process.stdout))
stdout_reader.daemon = False

stderr_reader = threading.Thread(target=_stream_reader, args=('STDERR', nuke_process.stderr))
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