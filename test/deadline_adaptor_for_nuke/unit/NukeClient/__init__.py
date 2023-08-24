# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock

# we must mock nuke before importing client code
nuke_modules = ["nuke"]

for module in nuke_modules:
    sys.modules[module] = MagicMock()
