import os
import nuke
from unittest.mock import ANY
from deadline.nuke_submitter.menu import add_deadline_menu


def test_add_deadline_menu_env_var_true() -> None:
    # GIVEN
    os.environ["DEADLINE_ENABLE_DEVELOPER_OPTIONS"] = "true"

    # WHEN
    add_deadline_menu()

    # THEN
    nuke.menu("Nuke").addMenu.assert_called_with("&AWS Deadline")
    nuke.menu("Nuke").addMenu("&AWS Deadline").addCommand.assert_called_with(
        "Run Nuke Submitter Job Bundle Output Tests...", ANY, ANY
    )


def test_add_deadline_menu_env_var_false() -> None:
    # GIVEN
    os.environ["DEADLINE_ENABLE_DEVELOPER_OPTIONS"] = "false"

    # WHEN
    add_deadline_menu()

    # THEN
    nuke.menu("Nuke").addMenu.assert_called_with("&AWS Deadline")
    nuke.menu("Nuke").addMenu("&AWS Deadline").addCommand.assert_called_with(
        "Submit to Deadline Cloud", ANY, ANY
    )
