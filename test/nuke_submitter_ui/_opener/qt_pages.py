# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Configurator-compatible page object executed in Nuke's GUI thread.

Controls receive Qt mouse/key events. This verifies widget behavior and
exported data, but does not exercise operating-system accessibility/input.
"""

from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


class TextField:
    """Read adapter for the existing configurators' element().value assertions."""

    def __init__(self, widget):
        self.widget = widget

    def element(self):
        return SimpleNamespace(value=self.widget.text())


class QtSubmitterDialog:
    def __init__(self, dialog):
        self.dialog = dialog

    def _tab(self, title):
        tabs = self.dialog.tabs
        index = next(i for i in range(tabs.count()) if tabs.tabText(i) == title)
        bar = tabs.tabBar()
        QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(index).center())
        assert tabs.currentIndex() == index, "Tab did not activate: " + title

    def switch_to_shared_tab(self):
        self._tab("Shared job settings")

    def switch_to_job_specific_tab(self):
        self._tab("Job-specific settings")

    @staticmethod
    def _text(widget, value):
        assert widget.isEnabled(), "Text field is disabled"
        widget.setFocus()
        QTest.keyClick(widget, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClick(widget, Qt.Key_Backspace)
        QTest.keyClicks(widget, value)
        assert widget.text() == value, "Text field did not receive the requested value"
        return widget.text()

    @staticmethod
    def _check(widget, enabled):
        assert widget.isEnabled(), "Checkbox is disabled"
        if widget.isChecked() != enabled:
            QTest.mouseClick(widget, Qt.LeftButton, pos=QPoint(10, widget.height() // 2))
        assert widget.isChecked() == enabled, "Checkbox did not toggle"

    @staticmethod
    def _spin(widget, value):
        assert widget.minimum() <= value <= widget.maximum(), "Spin value is out of range"
        assert widget.isEnabled(), "Spin box is disabled"
        widget.setFocus()
        QTest.keyClick(widget, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(widget, str(value))
        QTest.keyClick(widget, Qt.Key_Tab)
        assert widget.value() == value, "Spin box did not accept the requested value"

    def _properties(self):
        self.switch_to_shared_tab()
        return self.dialog.shared_job_settings.shared_job_properties_box

    def set_job_name(self, value):
        return self._text(self._properties().sub_name_edit, value)

    def set_job_description(self, value):
        return self._text(self._properties().desc_edit, value)

    def set_priority(self, value):
        self._spin(self._properties().priority_box, value)

    def set_max_failed_tasks(self, value):
        self._spin(self._properties().max_failed_tasks_count_box, value)

    def set_max_retries(self, value):
        self._spin(self._properties().max_retries_per_task_box, value)

    def selected_write_node(self):
        return self.dialog.job_settings.write_node_box.currentText()

    def select_write_node(self, label):
        combo = self.dialog.job_settings.write_node_box
        index = combo.findText(label)
        assert index >= 0, "Write node is missing: " + label
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key_Home)
        for _ in range(index):
            QTest.keyClick(combo, Qt.Key_Down)
        assert combo.currentText() == label, "Write node did not change: " + label

    def frame_range_field(self):
        return TextField(self.dialog.job_settings.frame_override_txt)

    def override_frame_range_enabled(self):
        return self.dialog.job_settings.frame_override_chck.isChecked()

    def set_override_frame_range(self, enabled):
        self._check(self.dialog.job_settings.frame_override_chck, enabled)

    def set_frame_range(self, value):
        self.set_override_frame_range(True)
        self._text(self.dialog.job_settings.frame_override_txt, value)

    def set_chunk_size(self, value):
        self._spin(self.dialog.job_settings.chunk_size_spin, value)

    def set_proxy_mode(self, enabled):
        self._check(self.dialog.job_settings.proxy_mode_check, enabled)

    def set_continue_on_error(self, enabled):
        self._check(self.dialog.job_settings.continue_on_error_check, enabled)

    def set_use_timeouts(self, enabled):
        self._check(self.dialog.job_settings.timeout_checkbox, enabled)

    def set_include_gizmos(self, enabled):
        self._check(self.dialog.job_settings.gizmos_checkbox, enabled)
