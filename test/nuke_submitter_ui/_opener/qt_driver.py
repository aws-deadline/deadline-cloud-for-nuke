# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Qt event driver for the shared export cases, executed inside GUI Nuke.

Uses widget mouse/key events, not AT-SPI or direct bundle-generation calls.
The parent pytest process validates the exported bundle independently.
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

from PySide6.QtCore import Qt, QTimer, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QMessageBox

from deadline.client.ui.dialogs.export_bundle_dialog import ExportBundleDialog
from qt_pages import QtSubmitterDialog
from qt_readiness import ready_for_configuration


class ExportDriver:
    def __init__(self, dialog, result_file):
        self.dialog = dialog
        self.result_file = Path(result_file)
        self.deadline = time.monotonic() + 120
        self.phase = "waiting for mock farm and queue"
        self.timer = QTimer(dialog)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def finish(self, error=None):
        self.timer.stop()
        try:
            self.dialog.grab().save(str(self.result_file.with_suffix(".png")))
        except Exception:
            # A diagnostic failure must not hide the driver result from pytest.
            self.result_file.with_suffix(".diagnostics.txt").write_text(traceback.format_exc())
        # Publish atomically: the parent polls this file from another process.
        pending = self.result_file.with_suffix(".pending")
        pending.write_text(
            json.dumps(
                {"ok": error is None, "phase": self.phase, "qt": qVersion(), "error": error}
            ),
            encoding="utf-8",
        )
        pending.replace(self.result_file)

    def tick(self):
        try:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("Qt probe timed out: " + self.phase)
            if self.phase == "waiting for mock farm and queue":
                settings = self.dialog.shared_job_settings
                farm_name = os.environ["NUKE_SUBMITTER_QT_FARM_NAME"]
                farm_resolved = any(
                    farm_name in widget.text()
                    for widget in settings.deadline_cloud_settings_box.findChildren(QLabel)
                ) or any(
                    farm_name in widget.currentText()
                    for widget in settings.deadline_cloud_settings_box.findChildren(QComboBox)
                )
                if not ready_for_configuration(
                    self.dialog.submit_button.isEnabled(),
                    settings.queue_parameters_box.async_loading_state,
                    farm_resolved,
                ):
                    return
                self.timer.stop()
                self.configure()
                self.phase = "waiting for export dialog"
                self.timer.start()
                # The export button opens a nested modal event loop. Keep this
                # timer alive to drive that dialog while mouseClick is pending.
                QTest.mouseClick(self.dialog.export_bundle_button, Qt.LeftButton)
            elif self.phase == "waiting for export dialog":
                export = QApplication.activeModalWidget()
                if not isinstance(export, ExportBundleDialog):
                    return
                self.phase = "waiting for saved confirmation"
                QTest.mouseClick(export._radio_local, Qt.LeftButton)
                assert export._radio_local.isChecked(), "Local export was not selected"
                export._name_edit.setFocus()
                QTest.keyClick(export._name_edit, Qt.Key_A, Qt.ControlModifier)
                QTest.keyClicks(export._name_edit, "qt-export")
                QTest.mouseClick(export._export_button, Qt.LeftButton)
            elif self.phase == "waiting for saved confirmation":
                popup = QApplication.activeModalWidget()
                if not isinstance(popup, QMessageBox):
                    return
                if "Bundle saved to:" not in popup.text():
                    raise RuntimeError("Unexpected export message: " + popup.text())
                self.timer.stop()
                QTest.mouseClick(popup.button(QMessageBox.Ok), Qt.LeftButton)
                self.phase = "export completed"
                self.finish()
        except Exception:
            self.finish(traceback.format_exc())

    def configure(self):
        path = Path(os.environ["NUKE_SUBMITTER_QT_CONFIGURATOR"])
        if not path.is_file():
            return  # Cases may deliberately use the dialog's unchanged defaults.
        # Configurators can import dependency-free shared test constants.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        spec = importlib.util.spec_from_file_location("_qt_case_configurator", path)
        if spec is None or spec.loader is None:
            raise ImportError("Could not load configurator: " + str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.configure(QtSubmitterDialog(self.dialog))


def start(dialog, result_file):
    # Retain Python callbacks for the lifetime of the real submitter dialog.
    dialog._deadline_qt_driver = ExportDriver(dialog, result_file)
