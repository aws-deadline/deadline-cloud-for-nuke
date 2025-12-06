# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import traceback
from typing import NamedTuple

from deadline.nuke_submitter.assets import AssetReferencesParsingOutcome

# Handle different Qt imports for different Nuke versions
try:
    # For Nuke 16+
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
    )
except ImportError:
    # For Nuke 13-15
    from PySide2.QtCore import Qt  # pylint: disable=import-error
    from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
    )


class OutputScanWarningResult(NamedTuple):
    """Result from the output scan warning dialog"""

    continue_submission: bool


class OutputScanWarningDialog(QDialog):
    """Dialog to warn user when output file scanning fails"""

    def __init__(self, parsing_outcome: AssetReferencesParsingOutcome, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Output Scan Warning")
        self.setModal(True)
        self.resize(400, 200)

        self._continue_submission = False
        self._show_details = False

        self._setup_ui(parsing_outcome)

    def _setup_ui(self, parsing_outcome: AssetReferencesParsingOutcome):
        layout = QVBoxLayout(self)

        if parsing_outcome.high_level_exception is None:
            failed_nodes = ", ".join(parsing_outcome.failed_to_parse_nodes.keys())
            warning_message = (
                "The submitter was unable to identify some of the input or output paths for this job "
                f"related to the following nodes: [{failed_nodes}]\n\n"
                "You can continue with the submission, but input or output files may not be "
                "properly tracked or transferred."
            )

            details_message = ""
            for failed_node, e in parsing_outcome.failed_to_parse_nodes.items():
                details_message += f"\nexception when parsing {failed_node}\n"
                details_message += "".join(traceback.format_exception(e))

        else:
            warning_message = (
                "The submitter encountered an exception trying to identify some of the input or output paths for this job\n\n"
                "You can continue with the submission, but input or output files may not be "
                "properly tracked or transferred."
            )
            details_message = "\n".join(
                traceback.format_exception(parsing_outcome.high_level_exception)
            )

        warning_label = QLabel(warning_message)
        warning_label.setWordWrap(True)
        warning_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        layout.addWidget(warning_label)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel Submission")
        cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_button)

        continue_button = QPushButton("Ignore && Continue")
        continue_button.clicked.connect(self._on_continue)
        continue_button.setDefault(True)
        button_layout.addWidget(continue_button)

        # Disclosable Details
        disclosure_button = QPushButton("▶ show more details")
        disclosure_button.setFlat(True)
        layout.addWidget(disclosure_button, alignment=Qt.AlignLeft)

        details_label = QLabel(details_message)
        details_label.setVisible(False)
        details_label.setFrameStyle(QFrame.Sunken | QFrame.Panel)
        details_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        details_label.setLineWidth(3)
        layout.addWidget(details_label)

        def toggle_details_visibility():
            self._show_details = not self._show_details
            details_label.setVisible(self._show_details)

            disclosure_button.setText(
                "▼ hide more details" if self._show_details else "▶ show more details"
            )
            self.adjustSize()

        disclosure_button.clicked.connect(toggle_details_visibility)

        layout.addLayout(button_layout)

    def _on_cancel(self):
        self._continue_submission = False
        self.reject()

    def _on_continue(self):
        self._continue_submission = True
        self.accept()

    def get_result(self) -> OutputScanWarningResult:
        """Get the user's choice from the dialog"""
        return OutputScanWarningResult(
            continue_submission=self._continue_submission,
        )
