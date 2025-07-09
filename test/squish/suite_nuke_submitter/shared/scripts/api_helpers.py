# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from shared.scripts import config
from deadline.client.api import get_boto3_client, list_farms, list_queues, list_jobs
from botocore.exceptions import ClientError
from deadline.job_attachments.download import OutputDownloader, get_job_input_paths_by_asset_root
from deadline.job_attachments.models import (
    JobAttachmentS3Settings,
    Attachments,
    ManifestProperties,
)
from pathlib import Path
import time
from typing import Dict, Any, cast


def get_farm_id_by_name():
    """Get farm ID by name from config"""

    farms = list_farms()
    print(farms)
    farm_id = next(
        (farm["farmId"] for farm in farms["farms"] if farm["displayName"] == config.farm_name), None
    )

    return farm_id


def get_queue_id_by_name(farm_id):
    """Get queue ID by name from config"""

    queues = list_queues(farmId=farm_id)
    print(queues)
    queue_id = next(
        (
            queue["queueId"]
            for queue in queues["queues"]
            if queue["displayName"] == config.queue_name
        ),
        None,
    )

    return queue_id


def get_job(farm_id, queue_id, job_id, check_storage_profile=False):
    # Returns the job details if found, None otherwise. This also serves to verify that the default farm/queue and the optional storage is selected.
    try:
        deadline = get_boto3_client("deadline")
        job = deadline.get_job(farmId=farm_id, queueId=queue_id, jobId=job_id)

        storage_profile_id = job.get("storageProfileId")

        if check_storage_profile:
            storage_profile = deadline.get_storage_profile(
                farmId=farm_id, storageProfileId=storage_profile_id
            )
            print(storage_profile["osFamily"])
            assert storage_profile["osFamily"] == "MACOS", "Storage profile is not macOS"
            print(f"Verified storage profile is macOS: {storage_profile['displayName']}")
        return job
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            print(f"Job not found with ID: {job_id}")
        else:
            print(f"Error getting job: {e}")
        return None


def verify_job_in_queue(farm_id, queue_id, job_id):
    """
    Verify if a job with the specified job_id exists in the queue.

    Args:
        farm_id (str): The ID of the farm
        queue_id (str): The ID of the queue
        job_id (str): The ID of the job to check

    Returns:
        bool: True if the job exists in the queue, False otherwise
    """
    try:
        # Get all jobs in the queue
        jobs = list_jobs(farmId=farm_id, queueId=queue_id)

        # Check if the jobs list is empty
        if not jobs["jobs"]:
            print(f"No jobs found in queue {queue_id}")
            return False

        # Check if the job_id exists in the list of jobs
        if any(job["jobId"] == job_id for job in jobs["jobs"]):
            print(f"Job {job_id} found in queue {queue_id}")
            return True

        print(f"Job {job_id} not found in queue {queue_id}")
        return False

    except Exception as e:
        print(f"Error verifying job in queue: {str(e)}")
        return False


def verify_ocio_config(ocio_path: Path, job_info):
    if job_info["parameters"]["OCIOConfigPath"] is None:
        raise AssertionError("No OCIO config path found")

    assert job_info["parameters"]["OCIOConfigPath"]["path"] == str(ocio_path), (
        f"OCIO config path mismatch:\n"
        f"Expected: {str(ocio_path)}\n"
        f"Actual: {job_info['parameters']['OCIOConfigPath']['path']}"
    )


def verify_output_directory(output_dir_path: Path, job_info):
    manifest = job_info["attachments"]["manifests"][0]
    if not manifest.get("outputRelativeDirectories"):
        raise AssertionError("No output directories found in manifest")

    output_dir_str = str(output_dir_path)
    assert any(
        output_dir_str in directory for directory in manifest["outputRelativeDirectories"]
    ), (
        f"Output directory not found in job manifest:\n"
        f"Expected: {output_dir_str}\n"
        f"Available directories: {', '.join(manifest['outputRelativeDirectories'])}"
    )


def wait_for_job_completion(farm_id, queue_id, job_id, timeout_seconds=600, poll_interval=10):
    """
    Wait for a job to complete (succeed or fail) with timeout and a poll interval (seconds).

    Returns:
        tuple: (success, final_status)
        - success: True if job completed (either succeeded or failed), False if timed out
        - final_status: Final job status ('SUCCEEDED', 'FAILED', etc.)
    """
    start_time = time.time()

    while True:
        # Check if we've exceeded timeout
        if time.time() - start_time > timeout_seconds:
            print(f"Timeout waiting for job {job_id} to complete")
            return False, "TIMEOUT"

        # Get current job status
        job = get_job(farm_id, queue_id, job_id)
        if not job:
            print(f"Could not get job status for {job_id}")
            return False, "ERROR"

        status = job.get("taskRunStatus")
        print(f"Current job status: {status}")

        # Check if job has reached a terminal state
        if status in ["SUCCEEDED", "FAILED", "CANCELED"]:
            print(f"Job {job_id} completed with status: {status}")
            return True, status

        # Wait before checking again
        time.sleep(poll_interval)


def download_output(farm_id, queue_id, job_id):
    """Download job outputs after verifying job completion."""
    try:
        # Wait for job completion
        job_complete, job_status = wait_for_job_completion(farm_id, queue_id, job_id)
        if not job_complete or job_status != "SUCCEEDED":
            print(f"Job did not complete successfully: {job_status}")
            return False

        # Get queue info
        deadline = get_boto3_client("deadline")
        queue = deadline.get_queue(farmId=farm_id, queueId=queue_id)

        # Create S3 settings from queue info
        s3_settings = JobAttachmentS3Settings(**queue["jobAttachmentSettings"])

        # Create downloader
        downloader = OutputDownloader(
            s3_settings=s3_settings, farm_id=farm_id, queue_id=queue_id, job_id=job_id
        )

        # Get output paths
        output_paths = downloader.get_output_paths_by_root()
        print("Output paths by root:", output_paths)

        if output_paths:
            # Download output files
            download_summary = downloader.download_job_output()
            print(
                f"Downloaded {download_summary.processed_files} files totaling {download_summary.processed_bytes} bytes"
            )
        return True

    except Exception as e:
        error_msg = f"Error downloading outputs: {str(e)}"
        print(error_msg)
        return False


def get_job_input_paths(farm_id, queue_id, job_id):
    try:
        deadline = get_boto3_client("deadline")
        queue = deadline.get_queue(farmId=farm_id, queueId=queue_id)

        s3_settings = JobAttachmentS3Settings(**queue["jobAttachmentSettings"])

        job = deadline.get_job(farmId=farm_id, queueId=queue_id, jobId=job_id)

        attachments = Attachments(**job["attachments"])

        for i in range(len(attachments.manifests)):
            manifest_dict = cast(Dict[str, Any], attachments.manifests[i])
            manifest = ManifestProperties(**manifest_dict)
            if manifest.inputManifestPath is not None:
                manifest.inputManifestPath = s3_settings.add_root_and_manifest_folder_prefix(
                    manifest.inputManifestPath
                )
            attachments.manifests[i] = manifest

        input_paths = get_job_input_paths_by_asset_root(
            s3_settings=s3_settings,
            attachments=attachments,
        )

        return input_paths

    except Exception as e:
        print(f"Error getting input paths: {str(e)}")
        return None
