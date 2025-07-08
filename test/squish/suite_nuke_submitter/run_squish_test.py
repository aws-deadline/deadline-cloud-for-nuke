# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import os
import subprocess
import sys
from shared.scripts import api_helpers, verification_helpers, cleanup_helpers
from shared.scripts.constants import TestConstants
import pathlib
import pytest
import json
from typing import Optional


def run_squish_command(testcase_name, local=True):
    """
    Execute a Squish test runner command and extract job ID from output.

    Args:
        testcase_name (str): Name of the test case to run (e.g., "basic_workflow_gui")
        local (bool): Whether to run the test locally (default: True)

    Returns:
        tuple: (success, job_id)
            - success (bool): True if command executed successfully (return code 0)
            - job_id (str or None): Extracted job ID from output if found, None otherwise
    """

    deadline_nuke_path = os.environ.get("DEADLINE_NUKE_PATH")
    squish_runner = "/Applications/Squish\\ for\\ Qt\\ 8.1.0/bin/squishrunner"
    testsuite_path = f"{deadline_nuke_path}/test/squish/suite_nuke_submitter"
    local_flag = "--local" if local else ""

    command = (
        f"{squish_runner} --testsuite {testsuite_path} --testcase {testcase_name} {local_flag}"
    )

    try:
        result = subprocess.run(
            command,
            shell=True,  # Use shell=True for complex commands
            check=False,  # Don't raise exception on non-zero exit
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Captures and displays both stdout and stderr from the command.
        print("=== Squish Command Output ===")
        print(result.stdout)

        if result.stderr:
            print("=== Squish Command Errors ===")
            print(result.stderr)

        if result.returncode != 0:
            print(f"Squish command failed with return code {result.returncode}")
            return False, []

        # Check for Squish test failures in the output
        has_squish_failure = False
        failure_message = ""
        lines = result.stdout.split("\n")
        job_ids = []
        for line in lines:
            # Look for job ID
            if "Found job ID:" in line:
                job_ids.append(line.split("Found job ID:")[1].strip())

            # Check for FAIL or FATAL in the output
            if "\tFAIL\t" in line or "FAIL " in line:
                has_squish_failure = True
                failure_message = line.strip()
            elif "\tFATAL\t" in line or "FATAL " in line:
                has_squish_failure = True
                failure_message = line.strip()

        if has_squish_failure:
            print(f"Squish test failed: {failure_message}")
            return False, []

        # Parse output to find job ID from test.log messages
        return True, job_ids
    except Exception as e:
        print(f"Error running squish command: {e}")
        return False


def test_valid_environment_variables():
    # Test that required environment variables are set and valid.
    env_vars = {
        "AWS_PROFILE": {"check_path": False},
        "DEADLINE_NUKE_PATH": {"check_path": True},
        "NUKE_ASSET_ROOT": {"check_path": True},
    }

    for var_name, config in env_vars.items():
        # Check if variable is set
        value = os.environ.get(var_name)
        assert value, f"{var_name} environment variable is not set"

        # Check if path exists
        if config["check_path"]:
            path = pathlib.Path(value)
            assert path.exists(), f"{var_name} does not exist: {value}"

        print(f"✓ {var_name} is valid: {value}")


@pytest.fixture
def cleanup_render_outputs():
    """Fixture that manages cleanup of rendered image outputs with manual trigger points"""
    cleanup_queue = []

    def register_cleanup(
        output_dir: str, base_name: str, render_settings_path: Optional[str] = None
    ):
        """Register a cleanup task"""
        cleanup_queue.append((output_dir, base_name, render_settings_path))

    def execute_cleanup():
        """Execute all registered cleanups"""
        while cleanup_queue:
            output_dir, base_name, render_settings_path = cleanup_queue.pop(0)
            try:
                success, message = cleanup_helpers.cleanup_output_images(output_dir, base_name)
                if not success:
                    raise RuntimeError(f"Cleanup failed: {message}")

                if render_settings_path:
                    success, message = cleanup_helpers.cleanup_render_settings_json(
                        render_settings_path
                    )
                    if not success:
                        raise RuntimeError(f"Render settings cleanup failed: {message}")

            except Exception as e:
                raise RuntimeError(f"Cleanup error: {str(e)}")

    yield register_cleanup, execute_cleanup

    # Final cleanup of any remaining items
    execute_cleanup()


def test_invalid_conda_env():
    check_platform()
    success = run_squish_command("invalid_conda_gui")
    if success is False:
        assert success, "Squish command failed"


def check_platform():
    assert (
        sys.platform == "darwin"
    ), "Deadline Nuke Squish Tests are only supported on macOS currently."


def test_basic_workflow(cleanup_render_outputs):
    check_platform()
    register_cleanup, _ = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.DEFAULT_TEST_SAMPLES_DIR,
        "scripts/nukeSubmitter_v02_nuke_default_one_write_node.deadline_render_settings.json",
    )
    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        "nukeTest_output_v01",
        render_settings_path,
    )

    success, job_id = run_squish_command("basic_workflow_gui")
    # Exit early if the Squish test failed
    if not success:
        assert success, "Squish command failed"
    if len(job_id) != 1:
        assert len(job_id) == 1, f"Expected exactly one job ID, but got {len(job_id)}"

    print("Basic Workflow Job ID: " + job_id[0])

    # Get the farm ID from configuration
    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    # Get the queue ID from configuration
    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, job_id[0])
    assert job_in_queue

    api_helpers.get_job(farm_id, queue_id, job_id[0])

    # Download the job's output files and assert success
    download_success = api_helpers.download_output(farm_id, queue_id, job_id[0])
    assert download_success, "Failed to download job output files"

    # Verify the rendered image sequence matches expected output
    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=TestConstants.get_expected_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        output_dir=TestConstants.get_output_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        base_name="nukeTest_output_v01",
        start_frame=TestConstants.FRAME_RANGE[0],
        end_frame=TestConstants.FRAME_RANGE[1],
        rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
    )


def test_custom_settings_workflow(cleanup_render_outputs):
    check_platform()
    register_cleanup, _ = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.DEFAULT_TEST_SAMPLES_DIR,
        "scripts/nukeSubmitter_v02_nuke_default_one_write_node.deadline_render_settings.json",
    )
    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        "nukeTest_output_v01",
        render_settings_path,
    )

    success, job_id = run_squish_command("custom_settings_gui")
    # Exit early if the Squish test failed
    if not success:
        assert success, "Squish command failed"
    if len(job_id) != 1:
        assert len(job_id) == 1, f"Expected exactly one job ID, but got {len(job_id)}"

    print("Custom Settings Workflow Job ID: " + job_id[0])

    # Get the farm ID from configuration
    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    # Get the queue ID from configuration
    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, job_id[0])
    assert job_in_queue

    custom_job = api_helpers.get_job(farm_id, queue_id, job_id[0])
    assert custom_job["name"] == "Custom Setting Submission"
    assert custom_job["description"] == "This test verifies submission with modified settings"
    assert custom_job["priority"] == 75
    assert custom_job["maxFailedTasksCount"] == 10
    assert custom_job["maxRetriesPerTask"] == 3
    assert custom_job["parameters"]["ContinueOnError"]["string"] == "true"

    # Download the job's output files
    api_helpers.download_output(farm_id, queue_id, job_id[0])

    # Verify the rendered image sequence matches expected output
    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=TestConstants.get_expected_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        output_dir=TestConstants.get_output_img_dir(TestConstants.DEFAULT_TEST_SAMPLES_DIR),
        base_name="nukeTest_output_v01",
        start_frame=TestConstants.FRAME_RANGE[0],
        end_frame=TestConstants.FRAME_RANGE[1],
        rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
    )


# Write Node Selection Test
def test_write_node_selection(cleanup_render_outputs):
    check_platform()

    register_cleanup, execute_cleanup = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.MODIFIED_TEST_SAMPLES_DIR,
        "scripts/nukeSubmitter_v02_nuke_modified.deadline_render_settings.json",
    )
    success, job_ids = run_squish_command("write_node_gui")

    # Verify test execution was successful
    if not success:
        assert success, "Squish command failed"
    if len(job_ids) != 2:
        assert len(job_ids) == 2, f"Expected exactly two job IDs, but got {len(job_ids)}"

    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"
    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    # Process single write node job (second most recent job)
    single_write_node_id = job_ids[0]
    single_write_job = api_helpers.get_job(farm_id, queue_id, single_write_node_id)

    print("\n=== Job Information ===")
    print(single_write_job)

    assert single_write_job is not None, "Failed to get single write node job"
    assert single_write_job["parameters"]["WriteNode"]["string"] == "Write1"

    download_success = api_helpers.download_output(farm_id, queue_id, single_write_node_id)
    assert download_success, "Failed to download single write node job output"

    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.MODIFIED_TEST_SAMPLES_DIR),
        "nukeTest_output_v01",
        render_settings_path,
    )

    # Verify single write node output
    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=TestConstants.get_expected_img_dir(TestConstants.MODIFIED_TEST_SAMPLES_DIR),
        output_dir=TestConstants.get_output_img_dir(TestConstants.MODIFIED_TEST_SAMPLES_DIR),
        base_name="nukeTest_output_v01",
        start_frame=TestConstants.FRAME_RANGE[0],
        end_frame=TestConstants.FRAME_RANGE[1],
        rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
    )

    execute_cleanup()

    # Process multiple write nodes job (most recent job)
    multiple_write_nodes_id = job_ids[1]
    multiple_nodes_job = api_helpers.get_job(farm_id, queue_id, multiple_write_nodes_id)

    print("\n=== Job Information ===")
    print(multiple_nodes_job)
    assert multiple_nodes_job is not None, "Failed to get multiple node selection job"
    assert multiple_nodes_job["parameters"]["WriteNode"]["string"] == "All Write Nodes"
    download_success = api_helpers.download_output(farm_id, queue_id, multiple_write_nodes_id)
    assert download_success, "Failed to download multiple write nodes job output"

    # Verify multiple write nodes outputs (two output files)
    for base_name in ["nukeTest_color_correct2", "nukeTest_output_v01"]:
        register_cleanup(
            TestConstants.get_output_img_dir(TestConstants.MODIFIED_TEST_SAMPLES_DIR),
            base_name,
            render_settings_path,
        )
        verification_helpers.verify_image_sequence_rgb_matches(
            expected_dir=TestConstants.get_expected_img_dir(
                TestConstants.MODIFIED_TEST_SAMPLES_DIR
            ),
            output_dir=TestConstants.get_output_img_dir(TestConstants.MODIFIED_TEST_SAMPLES_DIR),
            base_name=base_name,
            start_frame=TestConstants.FRAME_RANGE[0],
            end_frame=TestConstants.FRAME_RANGE[1],
            rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
        )


def test_ocio_job(cleanup_render_outputs):
    check_platform()

    register_cleanup, execute_cleanup = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.ACES_STOCK_TEST_SAMPLES_DIR,
        "scripts/nukeSubmitter_OCIO_v02_aces_stock.deadline_render_settings.json",
    )
    success, job_ids = run_squish_command("ocio_gui")

    # Verify test execution was successful
    if not success:
        assert success, "Squish command failed"
    if len(job_ids) != 2:
        assert len(job_ids) == 2, f"Expected exactly one job ID, but got {len(job_ids)}"

    # Get the farm ID from configuration
    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    # Get the queue ID from configuration
    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, job_ids[0])
    assert job_in_queue

    ocio_job = api_helpers.get_job(farm_id, queue_id, job_ids[0])
    print(json.dumps(ocio_job, indent=2, default=str))

    ocio_config_path = pathlib.Path(
        "/Applications/Nuke16.0v1/Nuke16.0v1.app/Contents/Resources/OCIOConfigs/configs/aces_1.2/config.ocio"
    )
    api_helpers.verify_ocio_config(ocio_config_path, ocio_job)

    download_success = api_helpers.download_output(farm_id, queue_id, job_ids[0])
    assert download_success, "Failed to download OCIO job output"

    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR),
        "nukeTest_output_OCIO_v01",
        render_settings_path,
    )

    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=TestConstants.get_expected_img_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR),
        output_dir=TestConstants.get_output_img_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR),
        base_name="nukeTest_output_OCIO_v01",
        start_frame=TestConstants.FRAME_RANGE[0],
        end_frame=TestConstants.FRAME_RANGE[1],
        rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
    )

    execute_cleanup()

    # Verify movie output
    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, job_ids[1])
    assert job_in_queue

    ocio_job = api_helpers.get_job(farm_id, queue_id, job_ids[1])
    print(json.dumps(ocio_job, indent=2, default=str))
    api_helpers.verify_ocio_config(ocio_config_path, ocio_job)

    download_success = api_helpers.download_output(farm_id, queue_id, job_ids[1])
    assert download_success, "Failed to download OCIO job output"

    register_cleanup(
        TestConstants.get_output_mov_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR),
        "nukeTest_OCIO_aces_stock",
        render_settings_path,
    )

    expected_movie_path = f"{TestConstants.get_expected_mov_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR)}/nukeTest_OCIO_aces_stock.mov"
    output_movie_path = f"{TestConstants.get_output_mov_dir(TestConstants.ACES_STOCK_TEST_SAMPLES_DIR)}/nukeTest_OCIO_aces_stock.mov"
    verification_helpers.verify_video_sequence_matches(expected_movie_path, output_movie_path)


def test_default_frame_range(cleanup_render_outputs):
    check_platform()
    register_cleanup, _ = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR,
        "scripts/Shot002.v01.001.deadline_render_settings.json",
    )

    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR),
        "Shot002_v01_001",
        render_settings_path,
    )
    success, job_id = run_squish_command("default_frame_range_gui")

    if not success:
        assert success, "Squish command failed"
    if len(job_id) != 1:
        assert len(job_id) == 1, f"Expected exactly one job ID, but got {len(job_id)}"

    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, job_id[0])
    assert job_in_queue

    default_frame_range_job = api_helpers.get_job(farm_id, queue_id, job_id[0])

    assert (
        default_frame_range_job["parameters"]["Frames"]["string"] == "1-56"
    ), f"Frame range mismatch: Expected '1-56' from Nuke script, but got '{default_frame_range_job['parameters']['Frames']['string']}'"

    download_success = api_helpers.download_output(farm_id, queue_id, job_id[0])
    assert download_success, "Failed to download OCIO job output"

    verification_helpers.count_files(
        TestConstants.get_output_img_dir(TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR)
    )

    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=TestConstants.get_expected_img_dir(
            TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR
        ),
        output_dir=TestConstants.get_output_img_dir(
            TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR
        ),
        base_name="Shot002_v01_001",
        start_frame=1,
        end_frame=56,
        rgb_diff_tolerance=TestConstants.RGB_TOLERANCE,
    )


def test_auto_detected_attachments(cleanup_render_outputs):
    check_platform()

    success, job_id = run_squish_command("default_frame_range_gui")
    register_cleanup, _ = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR,
        "scripts/Shot002.v01.001.deadline_render_settings.json",
    )

    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.INTRO_COMPOSITION_TEST_SAMPLES_DIR),
        "Shot002_v01_001",
        render_settings_path,
    )

    if not success:
        assert success, "Squish command failed"
    if len(job_id) != 1:
        assert len(job_id) == 1, f"Expected exactly one job ID, but got {len(job_id)}"

    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    default_frame_range_job = api_helpers.get_job(farm_id, queue_id, job_id[0])
    print(json.dumps(default_frame_range_job, indent=2, default=str))

    input_paths = api_helpers.get_job_input_paths(farm_id, queue_id, job_id[0])

    verification_helpers.verify_required_files(input_paths)


def test_manual_attachments(cleanup_render_outputs):
    check_platform()
    success, job_id = run_squish_command("manual_attachments_gui")

    register_cleanup, _ = cleanup_render_outputs
    render_settings_path = os.path.join(
        TestConstants.ACES_CUSTOM_TEST_SAMPLES_DIR,
        "scripts/nukeSubmitter_OCIO_v02_aces_custom.deadline_render_settings.json",
    )

    register_cleanup(
        TestConstants.get_output_img_dir(TestConstants.ACES_CUSTOM_TEST_SAMPLES_DIR),
        "nukeTest_output_OCIO_v01",
        render_settings_path,
    )

    if not success:
        assert success, "Squish command failed"
    if len(job_id) != 1:
        assert len(job_id) == 1, f"Expected exactly one job ID, but got {len(job_id)}"

    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"

    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"

    manual_attachment_job = api_helpers.get_job(farm_id, queue_id, job_id[0])

    input_paths = api_helpers.get_job_input_paths(farm_id, queue_id, job_id[0])

    root_path = next(iter(input_paths))
    manifest_group = input_paths[root_path]
    all_paths = set(manifest_group.get_all_paths())

    base_path = os.path.join(
        TestConstants.ACES_CUSTOM_TEST_SAMPLES_DIR,
        "manual",
    )[1:]

    api_helpers.verify_output_directory(base_path, manual_attachment_job)

    manual_files = ["manual_asset.exr", "manual_script.nk", "nukeTest_manual_frame.png"]
    missing_files = [
        os.path.join(base_path, f)
        for f in manual_files
        if os.path.join(base_path, f) not in all_paths
    ]

    assert not missing_files, f"Missing {len(missing_files)} required files:\n" + "\n".join(
        f"  - {f}" for f in missing_files
    )
