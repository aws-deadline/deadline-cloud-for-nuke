# Nuke Submitter E2E Testing with Squish

Nuke and Squish require a license. If you have a Squish and Nuke license, please follow the guide below to run the tests.

## Prerequisites
### Install Nuke

Download and install Nuke 16.0v1. The current tests have been validated on macOS 15.5. Support for Windows and Linux will be added after macOS support is established. 

### Set up the Deadline Cloud Nuke Submitter

Read the DEVELOPMENT.md for instructions on setting up the Nuke submitter.

### Install Squish Framework

Install Squish 8.1.0 for Qt 6.5. If you are using any other version, be sure to select the correct version of Qt that is being used with Nuke on your machine.

## Configure Squish Environment

Register Nuke as an AUT (Application Under Test) by going to 'Edit' -> 'Server Settings' and registering under 'Mapped AUTs' (in Squish IDE). 

Then, configure the Nuke Submitter path by going to the test suite settings in the Squish IDE and adding an AUT environment variable called NUKE_PATH. Set it to the path where your Nuke submitter is installed: 
```sh
/path/to/DeadlineCloudForNukeSubmitter
```
You can also modify the envvars file:
```sh
NUKE_PATH=/Users/user/DeadlineCloudForNukeSubmitter
```
### Set Required Environment Variables
The following environment variables are required for running the tests:
```sh
export AWS_PROFILE=<profile name>
export DEADLINE_NUKE_PATH=/path/to/deadline-cloud-for-nuke
export NUKE_ASSET_ROOT=/path/to/nuke/assets
```

### AWS Authentication
Paste your temporary AWS credentials in the terminal session where you'll run the tests. These credentials should have permissions to access the Deadline Cloud resources.

### Deadline Cloud Monitor
Log in to the Deadline Cloud Monitor to verify your credentials are working and that you can access the required resources.

## Deadline Cloud Resources Needed for Running Tests

The following Deadline Cloud resources are needed in order to run `tst_verify_settings_dialogue` test suite:

- An AWS default profile (used for authentication)
- A farm named "Nuke Submitter Squish Farm"
- A queue named "Nuke Submitter Squish Automation Queue"
- Three storage profiles named "Linux Storage Profile", "Windows Storage Profile", and "macOS Storage Profile"
- Fleet instance market type of On-Demand instance

## Available Tests
### Basic Workflow Test
The `basic_workflow` test provides comprehensive end-to-end validation of the basic Nuke submitter workflow. This test consists of two main parts: First, the basic_workflow_gui Squish test automates the UI interaction by launching Nuke, opening a pre-configured script file with a write node, configuring AWS profile and resources, submitting a job to Deadline Cloud, and closing Nuke. Second, the test performs backend validation by verifying the job was successfully submitted to the correct queue, monitoring job completion, downloading the rendered output files, comparing them against reference images to ensure visual accuracy, and handling the cleanup of resource.

### Custom Settings Submission Test
The `custom_settings` test validates the customization capabilities of the Nuke submitter interface for Deadline Cloud jobs. This test automates the UI interaction by launching Nuke, opening a pre-configured script file, and accessing the submitter interface to configure various job parameters. It sets custom values for job metadata (name and description), performance settings (priority level 75, maximum 3 retries per task, maximum 10 failed tasks), and error handling options (continue on error). After configuring these parameters, the test submits the job and verifies that all custom settings are correctly applied in the submitted job configuration. This ensures that the submitter interface reliably handles non-default parameter configurations and maintains setting integrity throughout the submission process.

### Write Node Selection Tests
The `write_node_selection` test provides comprehensive validation of the write node selection functionality in the Nuke submitter interface. This test executes two distinct submission scenarios: first submitting a job that targets a single write node ("Write1"), and then submitting another job that processes all write nodes in the script. For each scenario, the test automates the UI interaction by launching Nuke, configuring the AWS profile, selecting the appropriate write node option, and submitting the job. After submission, the test performs backend validation by verifying the jobs were created with correct write node parameters, downloading the rendered outputs, comparing them against reference images with RGB difference tolerance checks, and cleaning up the output files. This ensures that the submitter correctly handles both individual and batch write node selections, maintaining proper job configuration and output generation in both scenarios.

### Job Attachments Tests
The job attachments tests provide validation of both automatic and manual file attachment capabilities in the Nuke submitter interface. These tests consist of two main scenarios:

The `auto_detected_attachments` test verifies that the submitter correctly identifies and includes all necessary files referenced within the Nuke script. This test automates the UI interaction by launching Nuke with a pre-configured script, submitting the job with default settings, and then performs backend validation to ensure all script-referenced files are properly detected and included in the job submission.

The `manual_attachments` test validates the ability to manually add supplementary files and output directories to a job submission. This test automates the UI interaction by launching Nuke with a configured script, navigating to the job attachments tab, and manually adding specific test files (EXR, NK, and PNG) along with a custom output directory. The test then performs validation by verifying the job configuration, confirming the presence of all manually attached files in the job manifest, validating the output directory configuration, and ensuring proper cleanup of resources. This comprehensive validation ensures that users can reliably supplement automatically detected files with additional required assets, supporting workflows that require files beyond those directly referenced in the Nuke script.

### OCIO Color Management Test
The `ocio` test validates the integration of OpenColorIO (OCIO) color management within the Nuke submitter workflow for Deadline Cloud jobs. This test automates the UI interaction by launching Nuke with an ACES-configured script containing multiple write nodes and submitting separate jobs for different output types. After submission, the test performs backend validation by verifying OCIO configuration settings in the submitted jobs, downloading rendered outputs for both image sequences and movie files, performing RGB difference comparisons against reference images to ensure color accuracy, and validating movie file output integrity. This comprehensive validation ensures that the submission process correctly preserves color spaces, transformations, and ACES configurations throughout the entire workflow, from job submission to final render output.

### Frame Range Tests
The `default_frame_range` test validates that the Nuke submitter correctly uses frame ranges specified in the Nuke script when submitting jobs to Deadline Cloud. This test automates the UI interaction by launching Nuke with a pre-configured script containing a specific frame range, submitting the job without modifying the frame range settings, and then performs backend validation by verifying the frame range parameters in the submitted job configuration. After submission, the test downloads the rendered outputs and performs RGB difference comparisons against reference images to ensure all frames are correctly rendered within the specified range. This validation ensures that the submitter reliably preserves and uses the frame ranges defined in Nuke scripts.



## Running Tests
To install necessary dependencies to run the tests, run:
```sh
hatch run squish:deps
```
Then, to run the tests:
```sh
hatch run squish:test
```

## Test Results Interpretation
### Successful vs. Unsuccessful Tests
A successful test will be indicated by pytest's green message saying that the test has passed.

An unsuccessful test will show:
- FAIL or FATAL messages in the Squish output
- Error messages like "Failed to download job output"
- Assertion failures for squish commands, job submission, download, or job verification steps

### Image Verification Failures
When image verification fails, you can check the output images located at `$NUKE_ASSET_ROOT/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/images/output` 

These output images can be compared with the expected reference images at:
`$NUKE_ASSET_ROOT/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/images/expected`.

The test compares RGB values across the frames and calculates an average difference. A difference exceeding the tolerance (default: 0.1) will cause the test to fail.

In the case changes are made to the Nuke script, such as adding color correction nodes, applying visual effects, or modifying render settings, the output images will likely differ from the reference images. When these changes are intentional, you should update the reference images to reflect the new expected output.
