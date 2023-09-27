# Amazon Deadline Cloud for Nuke Development

## `hatch` commands

To develop this package, you'll need Python with `hatch` installed to start.

### Build the package

```bash
hatch build
```

### Run tests

```bash
hatch run test
```

### Run linting

```bash
hatch run lint
```

### Run formatting

```bash
hatch run fmt
```

### Run a full release test

```bash
hatch run all:test
```

## Submitter Development Workflow

Here are steps you can follow to run and edit the source code within your Nuke installation on Windows. The steps
will work on Linux or MacOS if you modify the path references as appropriate.

WARNING: This workflow installs additional Python packages into your Nuke's python distribution. You may need to run the Command Prompt in Administrative mode if your current user does not have permission to write on Nuke's site-package folder.

1. Create a development location within which to do your git checkouts. For example `~/deadline-clients`. Clone packages from this directory with commands like `git clone git@github.com:casillas2/deadline-cloud-for-nuke.git`. You'll also want the `deadline-cloud` repo.
2. Switch to your Nuke directory, like `cd "C:\Program Files\Nuke13.2v4"`.
3. Run `.\python -m pip install -e C:\Users\<username>\deadline-clients\deadline-cloud` to install the Amazon Deadline Cloud Client Library in edit mode.
4. Run `.\python -m pip install -e C:\Users\<username>\deadline-clients\deadline-cloud-for-nuke` to install the Nuke Submitter in edit mode.
5. Run `set NUKE_PATH=C:\Users\<username>\deadline-clients\deadline-cloud-for-nuke\src` to put the `menu.py` file in the path Nuke searches for menu extensions.
6. Run `set DEADLINE_ENABLE_DEVELOPER_OPTIONS=true` to enable the job bundle debugging support. This enables a menu item you can use to run the tests from the `job_bundle_output_tests` directory.
7. Run `.\Nuke<version>.exe` to run Nuke. The Nuke submitter should be available in the Thinkbox menu.

## Application Interface Adaptor Development Workflow

You can work on the adaptor alongside your submitter development workflow using a Deadline Cloud farm that uses a service-managed fleet. You'll need to perform the following steps to subsititute your build of the adaptor for the one in the service.

1. Use the development location from the Submitter Development Workflow. You will need to also check out `openjd-adaptor-runtime-for-python` from git if you do not already have it. Make sure you're running Nuke with `set DEADLINE_ENABLE_DEVELOPER_OPTIONS=true` enabled.
2. Build wheels for `openjd_adaptor_runtime`, `deadline` and `deadline_cloud_for_nuke`, place them in a "wheels" folder in `deadline-cloud-for-nuke`. A script is provided to do this, just execute from `deadline-cloud-for-nuke`:

   ```bash
   ./scripts/build_wheels.sh
   ```

   Wheels should have been generated in the "wheels" folder:

   ```bash
   $ ls ./wheels
   openjd_adaptor_runtime-<version>-py3-none-any.whl
   deadline-<version>-py3-none-any.whl
   deadline_cloud_for_nuke-<version>-py3-none-any.whl
   ```

3. Open the Nuke integrated submitter, and in the Job-Specific Settings tab, enable the option 'Include Adaptor Wheels'. This option is only visible when the environment variable `DEADLINE_ENABLE_DEVELOPER_OPTIONS` is set to `true`. Then submit your test job.

### Running the Adaptor Locally

You can run the adaptor on your local workstation. This approach does not contain all of the steps that would happen when running an actual job on the farm (rez environment, job attachments), but it can provide quick iteration for certain development cases.

1. Install `deadline-cloud-for-nuke` in edit mode as described in submitter development workflow above.
2. Create `init-data.yaml` and `run-data.yaml` files, replacing variables as necessary.

   ```yaml
   # init-data.yaml

   continue_on_error: false
   proxy: false
   script_file: '/path/to/script.nk'
   write_nodes:
   - 'Write1'
   views:
   - 'main'
   ```

   ```yaml
   # run-data.yaml

   frame: 1
   ```

3. Optionally create path mapping file
4. Run the adaptor from the environment where you have `deadline-cloud-for-nuke` installed:

   ```bash
   # Path mapping disabled
   NukeAdaptor run --init-data file://init-data.yaml --run-data file://run-data.yaml

   #path mapping enabled
   NukeAdaptor run --init-data file://init-data.yaml --run-data file://run-data.yaml --path-mapping-rules file://path-mapping.yaml
   ```

5. The resulting image(s) will be written based on the output(s) specified on the write node(s), taking any path mapping into account.
