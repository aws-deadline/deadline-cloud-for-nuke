import os
import subprocess
from shared.scripts import api_helpers, verification_helpers, cleanup_helpers

def run_squish_command(command):
    """
    Execute a Squish test runner command and extract job ID from output.
        
    Returns:
        tuple: (success, job_id)
            - success (bool): True if command executed successfully (return code 0)
            - job_id (str or None): Extracted job ID from output if found, None otherwise      
    """
    
    try:
        result = subprocess.run(
            command,
            shell=True,  # Use shell=True for complex commands
            check=False,  # Don't raise exception on non-zero exit
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Captures and displays both stdout and stderr from the command.
        print("=== Squish Command Output ===")
        print(result.stdout)

        if result.stderr:
            print("=== Squish Command Errors ===")
            print(result.stderr)

        # Parse output to find job ID from test.log messages
        job_id = None
        lines = result.stdout.split('\n')
        for line in lines:
            if "Found job ID:" in line:
                # Extract job ID from the log message
                job_id = line.split("Found job ID:")[1].strip()
                break

        return result.returncode == 0, job_id
    except Exception as e:
        print(f"Error running squish command: {e}")
        return False
    
def test_basic_workflow():
    deadline_nuke_path = os.environ.get("DEADLINE_NUKE_PATH")
    squish_command = f"/Applications/Squish\\ for\\ Qt\\ 8.1.0/bin/squishrunner --testsuite {deadline_nuke_path}/test/squish/suite_nuke_submitter --testcase basic_workflow_gui --local"
    success, job_id = run_squish_command(squish_command)
    # Exit early if the Squish test failed
    if success is False:
        assert success, "Squish command failed"
    
    # Get the farm ID from configuration
    farm_id = api_helpers.get_farm_id_by_name()
    assert farm_id is not None, "Farm ID not found"
    
    # Get the queue ID from configuration
    queue_id = api_helpers.get_queue_id_by_name(farm_id)
    assert queue_id is not None, "Queue ID not found"
    
    # Get the most recent job ID from the queue
    latest_job_id = api_helpers.get_latest_job_id(farm_id, queue_id)

    # Verify the job ID from Squish matches the latest job in the queue
    if job_id == latest_job_id:
        print("Job ID from Squish execution matches the latest job ID.")
    else:
        print("Error: Job ID from Squish execution does not match the latest job ID.")
        return

    job_in_queue = api_helpers.verify_job_in_queue(farm_id, queue_id, latest_job_id)
    latest_job = api_helpers.get_latest_job(farm_id, queue_id, latest_job_id)

    assert job_in_queue == True

    print("\n=== Latest Job Information ===")
    print(f"Job Info: {latest_job}")

    # Download the job's output files
    api_helpers.download_output(farm_id, queue_id, latest_job_id)

    # Verify the rendered image sequence matches expected output
    verification_helpers.verify_image_sequence_rgb_matches(
        expected_dir=os.environ.get("NUKE_ASSET_ROOT", "")+ "/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/images/expected",
        output_dir=os.environ.get("NUKE_ASSET_ROOT", "") + "/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/images/output",
        start_frame=101,  
        end_frame=120,   
        rgb_diff_tolerance=0.1
    )

    cleanup_helpers.cleanup_output_images(
        output_dir=os.environ.get("NUKE_ASSET_ROOT", "")+ "/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/images/output",
        end_frame=120
    )