# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock

# we must mock nuke and PyOpenColorIO before importing client code
nuke_modules = ["nuke", "PyOpenColorIO"]

for module in nuke_modules:
    sys.modules[module] = MagicMock()
