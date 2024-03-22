# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock

# we must mock nuke and UI code
mock_modules = [
    "deadline.client.ui.deadline_authentication_status",
    "nuke",
    "nuke.Node",
    "ui.deadline_submitter",
    "PySide2",
    "PySide2.QtCore",
    "PySide2.QtGui",
    "PySide2.QtWidgets",
    "PyOpenColorIO",
    "qtpy",
    "qtpy.QtCore",
    "qtpy.QtWidgets",
    "qtpy.QtGui",
]

for module in mock_modules:
    sys.modules[module] = MagicMock()
