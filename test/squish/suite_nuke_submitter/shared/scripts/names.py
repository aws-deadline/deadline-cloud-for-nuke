# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# from objectmaphelper import *
submit_to_AWS_Deadline_Cloud_SubmitJobToDeadlineDialog = {
    "type": "SubmitJobToDeadlineDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "Submit to AWS Deadline Cloud",
}
submit_to_AWS_Deadline_Cloud_qt_tabwidget_stackedwidget_QStackedWidget = {
    "name": "qt_tabwidget_stackedwidget",
    "type": "QStackedWidget",
    "visible": 1,
    "window": submit_to_AWS_Deadline_Cloud_SubmitJobToDeadlineDialog,
}
qt_tabwidget_stackedwidget_QScrollArea = {
    "container": submit_to_AWS_Deadline_Cloud_qt_tabwidget_stackedwidget_QStackedWidget,
    "type": "QScrollArea",
    "unnamed": 1,
    "visible": 1,
}
job_Properties_SharedJobPropertiesWidget = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "title": "Job Properties",
    "type": "SharedJobPropertiesWidget",
    "unnamed": 1,
    "visible": 1,
}
job_Properties_Name_QLabel = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "text": "Name",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
name_QLineEdit = {
    "buddy": job_Properties_Name_QLabel,
    "type": "QLineEdit",
    "unnamed": 1,
    "visible": 1,
}
job_Properties_Description_QLabel = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "text": "Description",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
job_Properties_Description_QLineEdit = {
    "aboveWidget": name_QLineEdit,
    "container": job_Properties_SharedJobPropertiesWidget,
    "leftWidget": job_Properties_Description_QLabel,
    "type": "QLineEdit",
    "unnamed": 1,
    "visible": 1,
}
nukeMainWindow_Foundry_UI_DockMainWindow = {
    "name": "NukeMainWindow",
    "type": "Foundry::UI::DockMainWindow",
    "visible": 1,
}
o_QMessageBox = {"type": "QMessageBox", "unnamed": 1, "visible": 1}
no_QPushButton = {
    "text": "No",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": o_QMessageBox,
}
manage_Nuke_crash_reports_QDialog = {
    "type": "QDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "Manage Nuke crash reports",
}
o_QMenuBar = {"type": "QMenuBar", "unnamed": 1, "visible": 1}
aWS_Deadline_Foundry_UI_Menu = {
    "title": "AWS Deadline",
    "type": "Foundry::UI::Menu",
    "unnamed": 1,
    "visible": 1,
}
oK_QPushButton = {
    "text": "OK",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": o_QMessageBox,
}
save_script_as_Foundry_UI_FileDialog = {
    "type": "Foundry::UI::FileDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "Save script as",
}
save_script_as_Save_QPushButton = {
    "text": "Save",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": save_script_as_Foundry_UI_FileDialog,
}
yes_QPushButton = {
    "text": "Yes",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": o_QMessageBox,
}
submit_to_AWS_Deadline_Cloud_Submit_QPushButton = {
    "text": "Submit",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": submit_to_AWS_Deadline_Cloud_SubmitJobToDeadlineDialog,
}
aWS_Deadline_Cloud_submission_SubmitJobProgressDialog = {
    "type": "SubmitJobProgressDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "AWS Deadline Cloud submission",
}
aWS_Deadline_Cloud_submission_OK_QPushButton = {
    "text": "OK",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_submission_SubmitJobProgressDialog,
}
file_Foundry_UI_Menu = {"title": "File", "type": "Foundry::UI::Menu", "unnamed": 1, "visible": 1}
script_to_open_Foundry_UI_FileDialog = {
    "type": "Foundry::UI::FileDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "Script to open",
}
script_to_open_QTreeView = {
    "type": "QTreeView",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
script_to_open_Open_QPushButton = {
    "text": "Open",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
nukeMainWindow_Foundry_UI_TimeSlider = {
    "type": "Foundry::UI::TimeSlider",
    "unnamed": 1,
    "visible": 1,
    "window": nukeMainWindow_Foundry_UI_DockMainWindow,
}
nukeMainWindow_qt_tabwidget_stackedwidget_QStackedWidget = {
    "name": "qt_tabwidget_stackedwidget",
    "type": "QStackedWidget",
    "visible": 1,
    "window": nukeMainWindow_Foundry_UI_DockMainWindow,
}
qt_tabwidget_stackedwidget_KnobPanel_QWidget = {
    "container": nukeMainWindow_qt_tabwidget_stackedwidget_QStackedWidget,
    "name": "KnobPanel",
    "type": "QWidget",
    "visible": 1,
}
knobPanel_FilePathEdit = {
    "container": qt_tabwidget_stackedwidget_KnobPanel_QWidget,
    "type": "FilePathEdit",
    "unnamed": 1,
    "visible": 1,
}
script_to_open_QPushButton = {
    "text": "+",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
script_to_open_FilePathEdit = {
    "aboveWidget": script_to_open_QPushButton,
    "type": "FilePathEdit",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
nukeMainWindow_DAG_DAG_Window = {
    "name": "DAG",
    "type": "DAG_Window",
    "visible": 1,
    "window": nukeMainWindow_Foundry_UI_DockMainWindow,
}
script_to_open_QListView = {
    "type": "QListView",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
script_to_open_Foundry_UI_FileBrowser = {
    "type": "Foundry::UI::FileBrowser",
    "unnamed": 1,
    "visible": 1,
    "window": script_to_open_Foundry_UI_FileDialog,
}
submit_to_AWS_Deadline_Cloud_Settings_QPushButton = {
    "text": "Settings...",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": submit_to_AWS_Deadline_Cloud_SubmitJobToDeadlineDialog,
}
aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog = {
    "type": "DeadlineConfigDialog",
    "unnamed": 1,
    "visible": 1,
    "windowTitle": "AWS Deadline Cloud workstation configuration",
}
aWS_Deadline_Cloud_workstation_configuration_Global_settings_QGroupBox = {
    "title": "Global settings",
    "type": "QGroupBox",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog,
}
global_settings_AWS_profile_QLabel = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Global_settings_QGroupBox,
    "text": "AWS profile",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
global_settings_AWS_profile_QComboBox = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Global_settings_QGroupBox,
    "leftWidget": global_settings_AWS_profile_QLabel,
    "type": "QComboBox",
    "unnamed": 1,
    "visible": 1,
}
aWS_Deadline_Cloud_workstation_configuration_Profile_settings_QGroupBox = {
    "title": "Profile settings",
    "type": "QGroupBox",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog,
}
profile_settings_QComboBox = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Profile_settings_QGroupBox,
    "type": "QComboBox",
    "unnamed": 1,
    "visible": 1,
}
aWS_Deadline_Cloud_workstation_configuration_Farm_settings_QGroupBox = {
    "title": "Farm settings",
    "type": "QGroupBox",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog,
}
farm_settings_QComboBox = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Farm_settings_QGroupBox,
    "type": "QComboBox",
    "unnamed": 1,
    "visible": 1,
}
aWS_Deadline_Cloud_workstation_configuration_OK_QPushButton = {
    "text": "OK",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog,
}
nukeMainWindow_Foundry_UI_OverflowButton = {
    "type": "Foundry::UI::OverflowButton",
    "unnamed": 1,
    "visible": 1,
    "window": nukeMainWindow_Foundry_UI_DockMainWindow,
}
save_script_as_Foundry_UI_FileBrowser = {
    "type": "Foundry::UI::FileBrowser",
    "unnamed": 1,
    "visible": 1,
    "window": save_script_as_Foundry_UI_FileDialog,
}
cancel_QPushButton = {
    "text": "Cancel",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": o_QMessageBox,
}
aWS_Deadline_Cloud_submission_Upload_progress_JobAttachmentsProgressWidget = {
    "title": "Upload progress",
    "type": "JobAttachmentsProgressWidget",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_submission_SubmitJobProgressDialog,
}
aWS_Deadline_Cloud_submission_Upload_progress_QTextEdit = {
    "aboveWidget": aWS_Deadline_Cloud_submission_Upload_progress_JobAttachmentsProgressWidget,
    "type": "QTextEdit",
    "unnamed": 1,
    "visible": 1,
    "window": aWS_Deadline_Cloud_submission_SubmitJobProgressDialog,
}
save_script_as_Cancel_QPushButton = {
    "text": "Cancel",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
    "window": save_script_as_Foundry_UI_FileDialog,
}
farm_settings_QComboBox_2 = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Farm_settings_QGroupBox,
    "occurrence": 2,
    "type": "QComboBox",
    "unnamed": 1,
    "visible": 1,
}
open_Recent_Comp_Foundry_UI_Menu = {
    "title": "Open Recent Comp",
    "type": "Foundry::UI::Menu",
    "unnamed": 1,
    "visible": 1,
}
queue_Environment_Conda_JobTemplateGroupLayout = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "name": "Queue Environment: Conda",
    "type": "_JobTemplateGroupLayout",
    "visible": 1,
}
queue_Environment_Conda_Conda_Packages_QLabel = {
    "container": queue_Environment_Conda_JobTemplateGroupLayout,
    "text": "Conda Packages",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
queue_Environment_Conda_Conda_Packages_QLineEdit = {
    "container": queue_Environment_Conda_JobTemplateGroupLayout,
    "leftWidget": queue_Environment_Conda_Conda_Packages_QLabel,
    "type": "QLineEdit",
    "unnamed": 1,
    "visible": 1,
}
queue_Environment_Conda_Conda_Channels_QLabel = {
    "container": queue_Environment_Conda_JobTemplateGroupLayout,
    "text": "Conda Channels",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
queue_Environment_Conda_Conda_Channels_QLineEdit = {
    "container": queue_Environment_Conda_JobTemplateGroupLayout,
    "leftWidget": queue_Environment_Conda_Conda_Channels_QLabel,
    "type": "QLineEdit",
    "unnamed": 1,
    "visible": 1,
}
job_Properties_qt_spinbox_lineedit_QLineEdit = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "name": "qt_spinbox_lineedit",
    "type": "QLineEdit",
    "visible": 1,
}
job_Properties_qt_spinbox_lineedit_QLineEdit_2 = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "name": "qt_spinbox_lineedit",
    "occurrence": 2,
    "type": "QLineEdit",
    "visible": 1,
}
job_Properties_qt_spinbox_lineedit_QLineEdit_3 = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "name": "qt_spinbox_lineedit",
    "occurrence": 3,
    "type": "QLineEdit",
    "visible": 1,
}
job_Properties_Priority_QLabel = {
    "container": job_Properties_SharedJobPropertiesWidget,
    "text": "Priority",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
deadline_Cloud_settings_DeadlineCloudSettingsWidget = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "title": "Deadline Cloud settings",
    "type": "DeadlineCloudSettingsWidget",
    "unnamed": 1,
    "visible": 1,
}
deadline_Cloud_settings_OpenJDParametersWidget = {
    "aboveWidget": deadline_Cloud_settings_DeadlineCloudSettingsWidget,
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "type": "OpenJDParametersWidget",
    "unnamed": 1,
    "visible": 1,
}
submit_to_AWS_Deadline_Cloud_QTabWidget = {
    "type": "QTabWidget",
    "unnamed": 1,
    "visible": 1,
    "window": submit_to_AWS_Deadline_Cloud_SubmitJobToDeadlineDialog,
}
continue_on_error_QCheckBox = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "text": "Continue on error",
    "type": "QCheckBox",
    "unnamed": 1,
    "visible": 1,
}
write_nodes_QLabel = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "text": "Write nodes",
    "type": "QLabel",
    "unnamed": 1,
    "visible": 1,
}
write_nodes_QComboBox = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "leftWidget": write_nodes_QLabel,
    "type": "QComboBox",
    "unnamed": 1,
    "visible": 1,
}
attach_input_files_QGroupBox = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "title": "Attach input files",
    "type": "QGroupBox",
    "unnamed": 1,
    "visible": 1,
}
attach_input_files_Add_QPushButton = {
    "container": attach_input_files_QGroupBox,
    "text": "Add...",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
fileNameLabel_QLabel = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "name": "fileNameLabel",
    "type": "QLabel",
    "visible": 1,
}
fileNameEdit_QLineEdit = {
    "buddy": fileNameLabel_QLabel,
    "name": "fileNameEdit",
    "type": "QLineEdit",
    "visible": 1,
}
open_QPushButton = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "text": "Open",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
specify_output_directories_QGroupBox = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "title": "Specify output directories",
    "type": "QGroupBox",
    "unnamed": 1,
    "visible": 1,
}
specify_output_directories_Add_QPushButton = {
    "container": specify_output_directories_QGroupBox,
    "text": "Add...",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
choose_QPushButton = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "text": "Choose",
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
override_frame_range_QCheckBox = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "text": "Override frame range",
    "type": "QCheckBox",
    "unnamed": 1,
    "visible": 1,
}
override_frame_range_QLineEdit = {
    "container": qt_tabwidget_stackedwidget_QScrollArea,
    "leftWidget": override_frame_range_QCheckBox,
    "type": "QLineEdit",
    "unnamed": 1,
    "visible": 1,
}
farm_settings_QPushButton = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Farm_settings_QGroupBox,
    "occurrence": 2,
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
profile_settings_QPushButton = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Profile_settings_QGroupBox,
    "occurrence": 2,
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
farm_settings_QPushButton_2 = {
    "container": aWS_Deadline_Cloud_workstation_configuration_Farm_settings_QGroupBox,
    "type": "QPushButton",
    "unnamed": 1,
    "visible": 1,
}
