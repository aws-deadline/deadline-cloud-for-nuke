# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
UI widgets for the Scene Settings tab.
"""
import os
import nuke
from PySide2.QtCore import Qt  # type: ignore
from PySide2.QtWidgets import (  # type: ignore
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

from ...assets import find_all_write_nodes
from ...data_classes.submission import RenderSubmitterSettings


class SceneSettingsWidget(QWidget):
    """
    Widget containing all top level scene settings.
    """

    def __init__(self, initial_settings: RenderSubmitterSettings, parent=None):
        super().__init__(parent=parent)

        self.developer_options = (
            os.environ.get("DEADLINE_NUKE_ENABLE_DEVELOPER_OPTIONS", "").upper() == "TRUE"
        )

        self._build_ui()
        self._configure_settings(initial_settings)

    def _build_ui(self):
        lyt = QGridLayout(self)

        self.write_node_box = QComboBox(self)
        self.write_node_box.addItem("All Write Nodes", None)
        for write_node in sorted(
            find_all_write_nodes(), key=lambda write_node: write_node.fullName()
        ):
            self.write_node_box.addItem(write_node.fullName(), write_node)

        lyt.addWidget(QLabel("Write Nodes"), 0, 0)
        lyt.addWidget(self.write_node_box, 0, 1)

        self.views_box = QComboBox(self)
        self.views_box.addItem("All Views", "")
        for view in sorted(nuke.views()):
            self.views_box.addItem(view, view)
        lyt.addWidget(QLabel("Views"), 1, 0)
        lyt.addWidget(self.views_box, 1, 1)

        self.frame_override_chck = QCheckBox("Override Frame Range", self)
        self.frame_override_txt = QLineEdit(self)
        lyt.addWidget(self.frame_override_chck, 2, 0)
        lyt.addWidget(self.frame_override_txt, 2, 1)
        self.frame_override_chck.stateChanged.connect(self.activate_frame_override_changed)

        self.proxy_mode_check = QCheckBox("Use Proxy Mode", self)
        lyt.addWidget(self.proxy_mode_check, 3, 0)

        if self.developer_options:
            self.include_adaptor_wheels = QCheckBox(
                "Developer Option: Include Adaptor Wheels", self
            )
            lyt.addWidget(self.include_adaptor_wheels, 4, 0)

        lyt.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), 10, 0)

    def _configure_settings(self, settings: RenderSubmitterSettings):
        self.frame_override_chck.setChecked(settings.override_frame_range)
        self.frame_override_txt.setEnabled(settings.override_frame_range)
        self.frame_override_txt.setText(settings.frame_list)

        index = self.write_node_box.findData(settings.write_node_selection)
        if index >= 0:
            self.write_node_box.setCurrentIndex(index)

        index = self.views_box.findData(settings.view_selection)
        if index >= 0:
            self.views_box.setCurrentIndex(index)

        self.proxy_mode_check.setChecked(settings.is_proxy_mode)

        if self.developer_options:
            self.include_adaptor_wheels.setChecked(settings.include_adaptor_wheels)

    def update_settings(self, settings: RenderSubmitterSettings):
        """
        Update a scene settings object with the latest values.
        """
        settings.override_frame_range = self.frame_override_chck.isChecked()
        settings.frame_list = self.frame_override_txt.text()

        settings.write_node_selection = self.write_node_box.currentData()
        settings.view_selection = self.views_box.currentData()
        settings.is_proxy_mode = self.proxy_mode_check.isChecked()

        if self.developer_options:
            settings.include_adaptor_wheels = self.include_adaptor_wheels.isChecked()
        else:
            settings.include_adaptor_wheels = False

    def activate_frame_override_changed(self, state: int):
        """
        Set the activated/deactivated status of the Frame override text box
        """
        self.frame_override_txt.setEnabled(state == Qt.Checked)
