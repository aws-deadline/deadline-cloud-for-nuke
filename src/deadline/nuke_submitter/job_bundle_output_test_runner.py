# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import tempfile
from unittest import mock
import re
import shutil
import filecmp
import difflib

import nuke

from PySide2.QtWidgets import (  # pylint: disable=import-error; type: ignore
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
)
from deadline.client.ui import gui_error_handler
from deadline.client.ui.dialogs import submit_job_to_deadline_dialog
from deadline.client.exceptions import DeadlineOperationError
from .deadline_submitter_for_nuke import show_nuke_render_submitter_noargs


def run_nuke_render_submitter_job_bundle_output_test():
    # Get the main Nuke window so we can parent the submitter to it
    app = QApplication.instance()
    mainwin = [widget for widget in app.topLevelWidgets() if isinstance(widget, QMainWindow)][0]
    count_succeeded = 0
    count_failed = 0
    with gui_error_handler("Error running job bundle output test", mainwin):
        tests_dir = QFileDialog.getExistingDirectory(
            mainwin, "Select a Directory Containing Nuke Job Bundle Tests"
        )

        if not tests_dir:
            return

        test_job_bundle_results_file = os.path.join(tests_dir, "test-job-bundle-results.txt")
        with open(test_job_bundle_results_file, "w", encoding="utf8") as report_fh:
            for job_bundle_test in os.listdir(tests_dir):
                job_bundle_test = os.path.join(tests_dir, job_bundle_test)
                if not os.path.isdir(job_bundle_test):
                    continue
                report_fh.write(f"\nRunning job bundle output test: {job_bundle_test}\n")

                nuke_scripts = [
                    path for path in os.listdir(job_bundle_test) if path.endswith(".nk")
                ]
                if len(nuke_scripts) != 1:
                    raise DeadlineOperationError(
                        f"Directory {job_bundle_test} does not have a single .nk script: {nuke_scripts}."
                    )

                succeeded = _run_job_bundle_output_test(
                    job_bundle_test, os.path.join(job_bundle_test, nuke_scripts[0]), report_fh
                )
                if succeeded:
                    count_succeeded += 1
                else:
                    count_failed += 1

            report_fh.write("\n")
            if count_failed:
                report_fh.write(f"Failed {count_failed} tests, succeeded {count_succeeded}.\n")
                QMessageBox.warning(
                    mainwin,
                    "Some Job Bundle Tests Failed",
                    f"Failed {count_failed} tests, succeeded {count_succeeded}.\nSee the file {test_job_bundle_results_file} for a full report.",
                )
            else:
                report_fh.write(f"All tests passed, ran {count_succeeded} total.")
                QMessageBox.information(
                    mainwin,
                    "All Job Bundle Tests Passed",
                    f"Ran {count_succeeded} tests in total.",
                )


def _run_job_bundle_output_test(test_dir: str, nuke_script: str, report_fh):
    # with tempfile.TemporaryDirectory(prefix="job_bundle_output_test") as tempdir:
    tempdir = tempfile.mkdtemp(prefix="job_bundle_output_test")
    if True:
        temp_job_bundle_dir = os.path.join(tempdir, "job_bundle")
        os.makedirs(temp_job_bundle_dir, exist_ok=True)

        # Read the Nuke script
        with open(nuke_script, encoding="utf8") as f:
            script_contents = f.read()

        # Find the internal script path
        original_script_path = None
        for line in script_contents.splitlines():
            match = re.match(" *name *(.*)", line)
            if match:
                original_script_path = match.group(1)
                break
        if not original_script_path:
            raise DeadlineOperationError(f"Failed to analyze Nuke script: {nuke_script}")

        # Replace every instance of the original script path with tempdir
        script_contents = script_contents.replace(
            os.path.dirname(original_script_path), tempdir.replace("\\", "/")
        )

        # Save the script to the tempdir
        temp_nuke_script = os.path.join(tempdir, os.path.basename(nuke_script))
        with open(temp_nuke_script, "w", encoding="utf8") as f:
            f.write(script_contents)

        # Open the Nuke script in Nuke
        nuke.scriptOpen(temp_nuke_script)
        QApplication.processEvents()

        # Open the Amazon Deadline Cloud submitter
        submitter = show_nuke_render_submitter_noargs()
        QApplication.processEvents()

        # Save the Job Bundle
        # Use patching to set the job bundle directory and skip the success messagebox
        with mock.patch.object(
            submit_job_to_deadline_dialog,
            "create_job_history_bundle_dir",
            return_value=temp_job_bundle_dir,
        ), mock.patch.object(submit_job_to_deadline_dialog, "QMessageBox"), mock.patch.object(
            os, "startfile"
        ):
            submitter.on_save_bundle()
        QApplication.processEvents()

        # Close the Nuke script in Nuke
        nuke.scriptClose()

        # Process every file in the job bundle to replace the temp dir with a standardized path
        for filename in os.listdir(temp_job_bundle_dir):
            full_filename = os.path.join(temp_job_bundle_dir, filename)
            with open(full_filename, encoding="utf8") as f:
                contents = f.read()
            contents = contents.replace(tempdir + "\\", "/normalized/job/bundle/dir/")
            contents = contents.replace(tempdir, "/normalized/job/bundle/dir")
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
            if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
                report_fh.write("Test failed, found differences\n")
                if dcmp.left_only:
                    report_fh.write(f"Missing files: {dcmp.left_only}\n")
                if dcmp.right_only:
                    report_fh.write(f"Extra files: {dcmp.right_only}\n")
                for file in dcmp.diff_files:
                    with open(
                        os.path.join(expected_job_bundle_dir, file), encoding="utf8"
                    ) as fleft, open(
                        os.path.join(test_job_bundle_dir, file), encoding="utf8"
                    ) as fright:
                        diff = "".join(
                            difflib.unified_diff(
                                list(fleft), list(fright), "expected/" + file, "test/" + file
                            )
                        )
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
