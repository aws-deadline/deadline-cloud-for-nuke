# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock, Mock

# we must mock nuke and UI code
mock_modules = [
    "nuke",
    "nuke.Node",
    "ui.deadline_submitter",
    "PySide2",
    "PySide2.QtCore",
    "PySide2.QtGui",
    "PySide2.QtWidgets",
    "PyOpenColorIO",
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# Mock the call to DeadlineCredentialsStatus.getInstance that happens at the module level
# in submit_job_to_deadline_dialog.py. That call is done at the module level to gather the
# status before the dialog is opened.
from deadline.client.ui.deadline_credentials_status import DeadlineCredentialsStatus

DeadlineCredentialsStatus.getInstance = Mock(return_value=None)
