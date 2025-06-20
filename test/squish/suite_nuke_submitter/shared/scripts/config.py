# -*- coding: utf-8 -*-
from pathlib import Path
import os

home_dir = str(Path.home())

profile_name = os.environ.get("AWS_PROFILE", "(default)")

farm_name = "Nuke Submitter Squish Farm"
farm_desc = "Squish Automation Test Framework"
queue_name = "Nuke Submitter Squish Automation Queue"

storage_profile_linux = "Linux Storage Profile"
storage_profile_windows = "Windows Storage Profile"
storage_profile_macos = "macOS Storage Profile"
