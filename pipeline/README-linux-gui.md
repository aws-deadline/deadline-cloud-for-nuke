# Linux Nuke GUI integration CI

`integ_linux.yml` runs the existing serial `test/nuke_submitter_ui` suite with
Nuke 16.0v9 and xa11y 0.15.*. The container is Rocky Linux 9 x86_64, hosted by
GitHub's `ubuntu-24.04` runner. Ubuntu is the host, not the Nuke userspace.
The Rocky image is pinned to its amd64 manifest digest.

The runner choice and session setup come from:

- [Foundry's Nuke 16 Linux requirements](https://learn.foundry.com/nuke/16.0/content/getting_started/installation/linux.html):
  Rocky 9 is qualified, and `libnuma` is required.
- [Deadline Cloud's Nuke 16 packaging recipe](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/nuke-16.0/recipe/build.sh):
  the Linux `.tgz` contains a `.run` installer; `--prefix=DIR` names its parent
  directory and `--accept-foundry-eula` enables unattended installation.
  The verified 16.0v9 archive bundles `python3`, linking to `python3.11`.
- [xa11y 0.15.0's Linux harness](https://github.com/xa11y/xa11y/blob/v0.15.0/scripts/run_integ_tests.sh)
  and [accessibility setup](https://github.com/xa11y/xa11y/blob/v0.15.0/scripts/setup_linux_a11y.sh):
  X11/XTest, a window manager, and AT-SPI2 in the same D-Bus session are required.
  Rocky provides Openbox, so this harness uses it for EWMH focus management.

`setup-linux-gui.sh` installs the runtime dependencies and the checksum-pinned
official AWS Session Manager plugin RPM. `run-linux-gui.sh` creates a private
D-Bus session, an authenticated Xvfb display with TCP disabled, Openbox, and
AT-SPI2. It checks XTest, window-manager readiness, and accessibility-bus readiness
before starting the command. `linux-gui-smoke.py` proves accessibility discovery,
window activation, and a synthetic pointer click against an unlicensed GTK app.
This check does not prove that Nuke's Qt bridge or submitter selectors work.

## Required live-run configuration

Maintainers must supply the following secrets through repository configuration
or the reusable workflow caller:

| Secret | Configuration |
| --- | --- |
| `NUKE_LINUX_INSTALLER_S3_KEY` | Existing, legitimate Nuke **16.0v9 Linux x86_64 `.tgz`** object in the installer bucket |
| `NUKE_LINUX_INSTALLER_SHA256` | SHA-256 of that exact archive, verified from the legitimate installer |
| `INSTALLER_BUCKET`, `INSTALLER_BUCKET_EXPECTED_OWNER` | Existing private installer bucket and its 12-digit owner account |
| `AWS_OIDC_ROLE_ARN`, `AWS_REGION` | Existing CI role and region |
| `LICENSE_ROLE_ARN`, `BASTION_INSTANCE_TAG` | Existing licensing role and unique running SSM bastion |

There is deliberately no fallback to `NUKE_INSTALLER_S3_KEY` or
`NUKE_INSTALLER_SHA256`, which currently configure the macOS DMG.
This change does not upload installers or modify secrets, roles, or infrastructure.
The helper verifies the bucket owner and archive checksum before executing the
installer. It copies only the sole regular `.run` member to a private staging
directory; archive paths and links are not extracted.

OIDC access currently trusts only upstream `mainline` and `feature/ci-tests`.
The workflow mirrors that repository/branch guard for push, dispatch, and
reusable calls. A dispatch from `nuke-gui/linux-ci` will skip the job.
After legitimate installer configuration exists, maintainers can validate the
change on an already trusted branch. Pull-request triggers remain deferred.

Linux and macOS share the `nuke-integration-tests` concurrency group with no
cancellation of the active run. GitHub can replace a pending run when multiple
pushes queue; the group serializes licensed runs and is not a FIFO queue.
The suite runs without xdist and starts only one licensed GUI Nuke at a time.

## Cleanup and diagnostics

The GUI command has a 40-minute limit within the job's 60-minute limit.
On success, failure, or a catchable cancellation, traps close the display
processes and any surviving Nuke process. The tunnel helper owns a process group,
checks readiness and continuing tunnel liveness, stops its plugin and test
processes, and terminates the remote SSM session. The `always()` teardown retries
remote termination using private session state in `RUNNER_TEMP`.
A runner forcibly destroyed before cleanup completes still depends on SSM's
service-side session expiry.

Failure artifacts retain desktop logs, the final PNG screenshot, pytest JUnit
output and temporary directories (including Nuke startup logs), and failed
case `actual/` bundles for seven days. CI sets
`NUKE_SUBMITTER_UI_CAPTURE_DIAGNOSTICS=1` to save each session's accessibility
tree and screenshot before Nuke closes, including startup failures that got
as far as accessibility registration. The private license config and SSM log
are outside the upload paths. Installer configuration values and checksum
values are not printed by the setup helper.

The first licensed run must verify all nine existing cases and Linux-specific
role/name selectors. Use `NUKE_SUBMITTER_UI_DIALOG_DUMP=1` for a deliberate
diagnostic run if selectors fail; do not regenerate goldens to hide a platform
failure. macOS installation and its workflow remain available.

## Unlicensed local checks

```bash
python -m pytest test/unit/pipeline -o addopts= -q
actionlint .github/workflows/integ_linux.yml .github/workflows/integ_macos.yml
zizmor --offline .github/workflows/integ_linux.yml
```

To validate the actual runtime without accessing installers or licenses, use
the pinned Rocky image from the workflow, copy the repository into a writable
container directory, set `RUNNER_TEMP` and `GUI_ARTIFACT_DIR`, then run:

```bash
bash pipeline/setup-linux-gui.sh
hatch env create integ-xa11y
bash pipeline/run-linux-gui.sh hatch -e integ-xa11y run python pipeline/linux-gui-smoke.py
```

Recheck the smoke test when updating the image, xa11y version, or desktop
dependencies. Update the Session Manager plugin version and digest together
from the official package.
