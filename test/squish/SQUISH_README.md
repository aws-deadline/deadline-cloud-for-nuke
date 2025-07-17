# Nuke Submitter E2E Testing with Squish

Nuke and Squish require a license. If you have a Squish and Nuke license, please follow the guide below to run the tests.

## Prerequisites
### Install Nuke

Download and install Nuke 16.0v1. The current tests have been validated on macOS 15.5 and Windows. Support for Linux will be added after macOS and Windows support is established. 

### Set up the Deadline Cloud Nuke Submitter

Read the DEVELOPMENT.md for instructions on setting up the Nuke submitter.

### Install Squish Framework

Install Squish 8.1.0 for Qt 6.5. If you are using any other version, be sure to select the correct version of Qt that is being used with Nuke on your machine.

## Configure Squish Environment

Register Nuke as an AUT (Application Under Test) by going to 'Edit' -> 'Server Settings' and registering under 'Mapped AUTs' (in Squish IDE). 

Import the test suite to Squish by going to 'File' -> 'Open Test Suite' and entering the test suite directory. 
#### For Windows: 
```C:\Users\<user>\deadline-client\deadline-cloud-for-nuke\test\squish\suite_nuke_submitter```

#### For macOS:
```/Users/<user>/deadline-clients/deadline-cloud-for-nuke/test/squish/suite_nuke_submitter```

\
Then, configure the Nuke Submitter path by going to the test suite settings in the Squish IDE and adding an AUT environment variable called NUKE_PATH. Set it to the path where your Nuke submitter is installed: 

#### For Windows:

```sh
C:\path\to\DeadlineCloudForNukeSubmitter
```
In the suite.conf file, set AUT to ```Nuke16.0```.
#### For macOS:
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
AWS_PROFILE=<profile name>
DEADLINE_NUKE_PATH=/path/to/deadline-cloud-for-nuke
```

### Replace environment variables in Nuke Scripts

The test suite includes Nuke scripts that use environment variables in their file paths. Before running the tests, you need to replace these environment variables with actual paths. A utility script is provided to handle this:

```sh
# Navigate to the scripts directory
cd deadline-cloud-for-nuke/test/squish/suite_nuke_submitter/shared/scripts/

# Replace $DEADLINE_NUKE_PATH with actual paths
python3 replace_env_paths.py

# To revert back to environment variables (if needed)
python3 replace_env_paths.py --revert
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

### Common Test Flow
All tests follow a standard pattern:
- Launch Nuke and open a pre-configured script
- Configure AWS profile and resources
- Submit job to Deadline Cloud
- Verify job submission and configuration
- Download and validate rendered outputs
- Clean up resources

### Test Categories

#### Basic Workflow
Validates the basic end-to-end submission workflow using default settings. Verifies job submission, rendering, and output generation with a simple write node configuration.

#### Custom Settings
Tests job submission with modified parameters including priority, retry limits, and error handling options. Ensures all custom settings are correctly applied and preserved in the submitted job.

#### Write Node Selection
Validates job submission using both single and multiple write node selections. Verifies that outputs are correctly generated for each selected write node configuration.

#### Job Attachments
Tests automatic detection of script-referenced files and manual addition of supplementary files. Verifies that both auto-detected and manually added files are properly included in the job bundle.

#### OCIO Color Management
Tests job submission with ACES color configurations across multiple write nodes. Validates color accuracy of rendered outputs for both image sequences and movie files.

#### Frame Range
Validates frame range handling across multiple scenarios: using default ranges from Nuke scripts, applying user-specified custom ranges, and respecting write node frame limits. 


## Running Tests
To install necessary dependencies to run the tests, run:
```sh
hatch run squish:deps
```
Then, to run the tests:
```sh
hatch run squish:test
```
To run a specific test:
```sh
# Navigate to the scripts directory
cd deadline-cloud-for-nuke/test/squish/suite_nuke_submitter

# Run the testcase
pytest run_squish_test.py::<testcase name>

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
