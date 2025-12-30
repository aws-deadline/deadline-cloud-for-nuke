import argparse
import dataclasses
import sys
from enum import Enum


class DestStream(Enum):
    STDOUT = "stdout"
    STDERR = "stderr"


@dataclasses.dataclass
class Line:
    text: str
    dest: DestStream


happy_case_lines = [
    Line(text="Nuke 16.0v1, 64 bit, built Feb 24 2025.", dest=DestStream.STDOUT),
    Line(
        text="Copyright (c) 2025 The Foundry Visionmongers Ltd.  All Rights Reserved.",
        dest=DestStream.STDOUT,
    ),
    Line(text="Licence expires on: 2026/3/18", dest=DestStream.STDOUT),
    Line(
        text="[19:28.55] Warning: /sessions/session-bb94863359344b398d92e0f41af024a5dffrdzmi/assetroot-8ec6f7889c962aeaebe1/Downloads/plushie_colorchange/copycat.nk is for nuke16.0v7; this is nuke16.0v1",
        dest=DestStream.STDERR,
    ),
    Line(text="", dest=DestStream.STDOUT),
    Line(text="[Step:1/30] Loss:0.022428", dest=DestStream.STDOUT),
    Line(text="[Step:10/30] Loss:0.022428", dest=DestStream.STDOUT),
    Line(text="[Step:20/30] Loss:0.0164353", dest=DestStream.STDOUT),
    Line(text="[Step:30/30] Loss:0.0164353", dest=DestStream.STDOUT),
    Line(
        text=" [*] Cat file saved at /sessions/session-bb94863359344b398d92e0f41af024a5dffrdzmi/assetroot-8ec6f7889c962aeaebe1/Downloads/plushie_colorchange/data_dir/Training_251223_192904.22500.cat",
        dest=DestStream.STDOUT,
    ),
    Line(
        text=" [*] Optimiser saved at /sessions/session-bb94863359344b398d92e0f41af024a5dffrdzmi/assetroot-8ec6f7889c962aeaebe1/Downloads/plushie_colorchange/data_dir/Training_251223_192904.22500.ost",
        dest=DestStream.STDOUT,
    ),
    Line(
        text=" [*] Contactsheet saved at /sessions/session-bb94863359344b398d92e0f41af024a5dffrdzmi/assetroot-8ec6f7889c962aeaebe1/Downloads/plushie_colorchange/data_dir/Training_251223_192904.22500.png",
        dest=DestStream.STDOUT,
    ),
    Line(text="", dest=DestStream.STDOUT),
    Line(text="Frame 1 (1 of 1)", dest=DestStream.STDOUT),
    Line(text="", dest=DestStream.STDOUT),
    Line(text="Total render time: 19 minutes, 42 seconds", dest=DestStream.STDOUT),
]

fail_case_lines = [
    Line(text="Nuke 16.0v1, 64 bit, built Feb 24 2025.", dest=DestStream.STDOUT),
    Line(
        text="Copyright (c) 2025 The Foundry Visionmongers Ltd.  All Rights Reserved.",
        dest=DestStream.STDOUT,
    ),
    Line(text="Licence expires on: 2026/3/18", dest=DestStream.STDOUT),
    Line(
        text="[19:28.55] Warning: /sessions/session-bb94863359344b398d92e0f41af024a5dffrdzmi/assetroot-8ec6f7889c962aeaebe1/Downloads/plushie_colorchange/copycat.nk is for nuke16.0v7; this is nuke16.0v1",
        dest=DestStream.STDERR,
    ),
    Line(text="Nuke 16.0v1, 64 bit, built Feb 24 2025.", dest=DestStream.STDOUT),
    Line(
        text="Copyright (c) 2025 The Foundry Visionmongers Ltd.  All Rights Reserved.",
        dest=DestStream.STDOUT,
    ),
    Line(text="Licence expires on: 2026/3/18", dest=DestStream.STDOUT),
    Line(
        text="[18:41.54] ERROR: CopyCat1: No valid or writable data directory is selected.",
        dest=DestStream.STDERR,
    ),
    Line(text=".1.2.3.4.5.6.7.8.9", dest=DestStream.STDOUT),
    Line(text="Total render time: 0.00 seconds", dest=DestStream.STDOUT),
    Line(text="CopyCat1: No valid or writable data directory is selected.", dest=DestStream.STDERR),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # use the argument passed into nuke_script to decide whether we should output
    # the happy case, or the failure case
    parser.add_argument("nuke_script")
    parser.add_argument("-X")
    parser.add_argument("-F")
    parser.add_argument("--gpu", action="store_true")

    args = parser.parse_args()

    is_happy_case = args.nuke_script == "happy_case"

    lines = happy_case_lines if is_happy_case else fail_case_lines

    for line in lines:
        print(line.text, file=sys.stdout if line.dest == DestStream.STDOUT else sys.stderr)

    if is_happy_case:
        sys.exit(0)
    else:
        sys.exit(1)
