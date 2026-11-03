# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Experimental Qt event driver, executed inside licensed GUI Nuke.

Uses widget mouse/key events, not AT-SPI or direct bundle-generation calls.
The parent pytest process validates the exported bundle independently.
"""

import json
from pathlib import Path
import time
import traceback

from PySide6.QtCore import QPoint, Qt, QTimer, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from deadline.client.ui.dialogs.export_bundle_dialog import ExportBundleDialog


class Probe:
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
        self.dialog.grab().save(str(self.result_file.with_suffix(".png")))
        self.result_file.write_text(
            json.dumps(
                {"ok": error is None, "phase": self.phase, "qt": qVersion(), "error": error}
            ),
            encoding="utf-8",
        )

    def tick(self):
        try:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("Qt probe timed out: " + self.phase)
            if self.phase == "waiting for mock farm and queue":
                if not self.dialog.submit_button.isEnabled():
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
                QTest.keyClicks(export._name_edit, "qt-frame-range-probe")
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
        tabs = self.dialog.tabs
        index = next(i for i in range(tabs.count()) if tabs.tabText(i) == "Job-specific settings")
        bar = tabs.tabBar()
        QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(index).center())
        assert tabs.currentIndex() == index, "Job-specific tab did not activate"
        settings = self.dialog.job_settings
        combo = settings.write_node_box
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key_Home)
        for _ in range(combo.findText("Write1")):
            QTest.keyClick(combo, Qt.Key_Down)
        assert combo.currentText() == "Write1", "Write1 was not selected"
        checkbox = settings.frame_override_chck
        if not checkbox.isChecked():
            QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(10, checkbox.height() // 2))
        assert checkbox.isChecked(), "Frame override did not toggle"
        field = settings.frame_override_txt
        assert field.isEnabled(), "Frame field did not become editable"
        field.setFocus()
        QTest.keyClick(field, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(field, "1-10")
        assert field.text() == "1-10", "Frame field did not receive key events"


def start(dialog, result_file):
    # Retain Python callbacks for the lifetime of the real submitter dialog.
    dialog._deadline_qt_probe = Probe(dialog, result_file)
