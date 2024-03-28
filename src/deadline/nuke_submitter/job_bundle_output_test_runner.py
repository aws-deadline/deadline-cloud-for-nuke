# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Runs a set of job bundle tests defined in a folder structure.

<job_bundle_tests>/
    test_1/
        scene/
            test_1.ext
            <support data>
        expected_job_bundle/
            <reference output>
    test_2
        scene/
            test_2.ext
            <support data>
        expected_job_bundle/
            <reference output>
    ...
"""
import os
import tempfile
from unittest import mock
import re
import shutil
import filecmp
import difflib
import yaml  # type: ignore[import]
from typing import Any
from pathlib import Path
from datetime import datetime, timezone

import nuke
from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
    QApplication,
    QFileDialog,
    QMainWindow,
)

from deadline.client.ui import gui_error_handler
from deadline.client.ui.dialogs import submit_job_to_deadline_dialog
from deadline.client.exceptions import DeadlineOperationError
from .deadline_submitter_for_nuke import show_nuke_render_submitter_noargs


# The following functions expose a DCC interface to the job bundle output test logic.


def _get_dcc_main_window() -> Any:
    # Get the main Nuke window so we can parent the submitter to it
    app = QApplication.instance()
    return [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]


def _get_dcc_scene_file_extension() -> str:
    return ".nk"


def _open_dcc_scene_file(filename: str):
    """Opens the scene file in Nuke."""
    nuke.scriptOpen(filename)


def _close_dcc_scene_file():
    """Closes the scene file in Nuke."""
    nuke.scriptClose()


def _copy_dcc_scene_file(source_filename: str, dest_filename: str):
    # Copy all support files under the source filename's dirname
    # Python 3.7 doesn't support dirs_exist_ok=True, so we
    # go through all the files & directories at the top level.
    source_dir = os.path.dirname(source_filename)
    dest_dir = os.path.dirname(dest_filename)
    for path in os.listdir(source_dir):
        source = os.path.join(source_dir, path)
        dest = os.path.join(dest_dir, path)
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copy(source, dest)

    # Read the Nuke script
    with open(source_filename, encoding="utf8") as f:
        script_contents = f.read()

    # Find the internal script path
    original_script_dirname = None
    for line in script_contents.splitlines():
        match = re.match(" *name *(.*)", line)
        if match:
            original_script_dirname = os.path.dirname(match.group(1))
            break
    if not original_script_dirname:
        raise DeadlineOperationError(
            "Failed to analyze Nuke script file, it does not contain the name"
            + " line containing the original full file path."
        )

    # Replace every instance of the original script path with tempdir
    script_contents = script_contents.replace(
        original_script_dirname, os.path.dirname(dest_filename).replace("\\", "/")
    )

    # Save the script to the tempdir
    with open(dest_filename, "w", encoding="utf8") as f:
        f.write(script_contents)


def _show_deadline_cloud_submitter(mainwin: Any):
    """Shows the Deadline Cloud Submitter for Nuke."""
    return show_nuke_render_submitter_noargs()


# The following functions implement the test logic.


def _timestamp_string() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def run_render_submitter_job_bundle_output_test():
    """
    Runs a set of job bundle output tests from a directory.
    """
    # Get the DCC's main window so we can parent the submitter to it
    mainwin = _get_dcc_main_window()
    count_succeeded = 0
    count_failed = 0
    with gui_error_handler("Error running job bundle output test", mainwin):
        default_tests_dir = Path(__file__).parent.parent.parent.parent / "job_bundle_output_tests"

        tests_dir = QFileDialog.getExistingDirectory(
            mainwin, "Select a Directory Containing the Job Bundle Tests", str(default_tests_dir)
        )

        if not tests_dir:
            return

        tests_dir = os.path.normpath(tests_dir)

        test_job_bundle_results_file = os.path.join(tests_dir, "test-job-bundle-results.txt")
        with open(test_job_bundle_results_file, "w", encoding="utf8") as report_fh:
            for test_name in os.listdir(tests_dir):
                job_bundle_test = os.path.join(tests_dir, test_name)
                if not os.path.isdir(job_bundle_test):
                    continue
                report_fh.write(f"\nTimestamp: {_timestamp_string()}\n")
                report_fh.write(f"Running job bundle output test: {job_bundle_test}\n")

                dcc_scene_file = os.path.join(
                    job_bundle_test, "scene", f"{test_name}{_get_dcc_scene_file_extension()}"
                )

                if not (os.path.exists(dcc_scene_file) and os.path.isfile(dcc_scene_file)):
                    raise DeadlineOperationError(
                        f"Directory {job_bundle_test} does not contain the expected {_get_dcc_scene_file_extension()} scene: {dcc_scene_file}."
                    )

                succeeded = _run_job_bundle_output_test(
                    job_bundle_test, dcc_scene_file, report_fh, mainwin
                )
                if succeeded:
                    count_succeeded += 1
                else:
                    count_failed += 1

            report_fh.write("\n")
            if count_failed:
                report_fh.write(f"Failed {count_failed} tests, succeeded {count_succeeded}.\n")
                nuke.alert(
                    "Some Job Bundle Tests Failed\n\n"
                    f"Failed {count_failed} tests, succeeded {count_succeeded}.\n\n"
                    f'See the file "{test_job_bundle_results_file}" for a full report.',
                )
            else:
                report_fh.write(f"All tests passed, ran {count_succeeded} total.\n")
                nuke.message(
                    f"All Job Bundle Tests Passed\n\nRan {count_succeeded} tests in total.\n\n"
                    f'See the file "{test_job_bundle_results_file}" for a full report.',
                )
            report_fh.write(f"Timestamp: {_timestamp_string()}\n")


def _run_job_bundle_output_test(test_dir: str, dcc_scene_file: str, report_fh, mainwin: Any):
    with tempfile.TemporaryDirectory(prefix="job_bundle_output_test") as tempdir:
        temp_job_bundle_dir = os.path.join(tempdir, "job_bundle")
        os.makedirs(temp_job_bundle_dir, exist_ok=True)

        temp_cwd_bundle_dir = os.path.join(tempdir, "job_cwd")
        os.makedirs(temp_cwd_bundle_dir, exist_ok=True)

        temp_dcc_scene_file = os.path.join(tempdir, os.path.basename(dcc_scene_file))

        # Copy the DCC scene file to the temp directory, transforming any
        # internal paths as necessary.
        _copy_dcc_scene_file(dcc_scene_file, temp_dcc_scene_file)

        # Open the DCC scene file
        _open_dcc_scene_file(temp_dcc_scene_file)
        QApplication.processEvents()

        # Open the AWS Deadline Cloud submitter
        submitter = _show_deadline_cloud_submitter(mainwin)
        QApplication.processEvents()

        # Save the Job Bundle
        # Use patching to set the job bundle directory and skip the success messagebox
        with (
            mock.patch.object(
                submit_job_to_deadline_dialog,
                "create_job_history_bundle_dir",
                return_value=temp_job_bundle_dir,
            ),
            mock.patch.object(submit_job_to_deadline_dialog, "QMessageBox"),
            mock.patch.object(
                os,
                "startfile",
                create=True,  # only exists on win. Just create to avoid AttributeError
            ),
        ):
            submitter.on_export_bundle()
        QApplication.processEvents()

        # Close the DCC scene file
        _close_dcc_scene_file()

        # Process every file in the job bundle to replace the temp dir with a standardized path
        for filename in os.listdir(temp_job_bundle_dir):
            full_filename = os.path.join(temp_job_bundle_dir, filename)
            with open(full_filename, encoding="utf8") as f:
                contents = f.read()
            contents = contents.replace(tempdir + "\\", "/normalized/job/bundle/dir/")
            contents = contents.replace(
                tempdir.replace("\\", "/") + "/", "/normalized/job/bundle/dir/"
            )
            contents = contents.replace(tempdir, "/normalized/job/bundle/dir")
            contents = contents.replace(tempdir.replace("\\", "/"), "/normalized/job/bundle/dir")

            # Windows corner case
            contents = contents.replace("C:\\tmp\\", "/tmp/")
            contents = contents.replace("C:\\tmp", "/tmp")
            contents = contents.replace("C:/tmp", "/tmp")

            if os.getcwd() != "/":
                contents = contents.replace(os.getcwd() + "\\", "/normalized/cwd/")
                contents = contents.replace(
                    os.getcwd().replace("\\", "/") + "\\", "/normalized/cwd/"
                )
                contents = contents.replace(os.getcwd(), "/normalized/cwd")
            else:
                # Mac specific cases
                contents = contents.replace(" /\n", " /normalized/cwd\n")
                contents = contents.replace(" /output\n", " /normalized/cwd/output\n")

            with open(full_filename, "w", encoding="utf8") as f:
                f.write(contents)

        # If there's an expected job bundle to compare with, do the comparison,
        # otherwise copy the one we created to be that expected job bundle.
        expected_job_bundle_dir = os.path.join(test_dir, "expected_job_bundle")
        if os.path.exists(expected_job_bundle_dir):
            test_job_bundle_dir = os.path.join(test_dir, "test_job_bundle")
            if os.path.exists(test_job_bundle_dir):
                shutil.rmtree(test_job_bundle_dir)
            shutil.copytree(temp_job_bundle_dir, test_job_bundle_dir)

            dcmp = filecmp.dircmp(expected_job_bundle_dir, test_job_bundle_dir)
            report_fh.write("\n")
            report_fh.write(f"{os.path.basename(test_dir)}\n")

            filtered_diff = []
            if dcmp.diff_files:
                for file in dcmp.diff_files:
                    with (
                        open(os.path.join(expected_job_bundle_dir, file), encoding="utf8") as fleft,
                        open(os.path.join(test_job_bundle_dir, file), encoding="utf8") as fright,
                    ):
                        # Convert the yaml to an ordered dict to verify the differences are not caused by ordering.
                        # For example, MacOS creates "/tmp/luts" directory in different order compare to Windows/Linux
                        # NOTE: if there are other diffs in the same file, then the ordering mismatch will still
                        # be printed in output, but can be ignored.
                        expected_data = _sort(yaml.safe_load(fleft.read()))
                        actual_data = _sort(yaml.safe_load(fright.read()))

                        if expected_data != actual_data:
                            expected = open(
                                os.path.join(expected_job_bundle_dir, file), encoding="utf8"
                            )
                            actual = open(os.path.join(test_job_bundle_dir, file), encoding="utf8")
                            diff = "".join(
                                difflib.unified_diff(
                                    list(expected), list(actual), "expected/" + file, "test/" + file
                                )
                            )
                            filtered_diff.append(diff)

            if dcmp.left_only or dcmp.right_only or filtered_diff:
                report_fh.write("Test failed, found differences\n")
                if dcmp.left_only:
                    report_fh.write(f"Missing files: {dcmp.left_only}\n")
                if dcmp.right_only:
                    report_fh.write(f"Extra files: {dcmp.right_only}\n")
                for diff in filtered_diff:
                    report_fh.write(diff)

                # Failed the test
                return False
            else:
                report_fh.write("Test succeeded\n")
                # Succeeded the test
                return True
        else:
            shutil.copytree(temp_job_bundle_dir, expected_job_bundle_dir)

            report_fh.write("Test cannot compare. Saved new reference to expected_job_bundle.\n")
            # We generated the original expected job bundle, so did not succeed a test.
            return False


def _sort(obj):
    if isinstance(obj, dict):
        return sorted((k, _sort(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(_sort(x) for x in obj)
    else:
        return obj
