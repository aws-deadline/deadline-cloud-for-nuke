# Linux Nuke GUI integration CI

`integ_gui.yml` runs macOS and Linux in parallel on each eligible push.
Its Linux worker, `integ_linux.yml`, runs the nine existing serial export cases with
Nuke 16.0v9, using an in-process Qt event driver by default. The macOS workflow
continues to use xa11y 0.15.*. The container is Rocky Linux 9 x86_64, hosted by
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
When `ui_driver=xa11y` is selected, a second unlicensed smoke test uses Nuke's bundled Python,
PySide6, Qt libraries, and platform plugin to verify AT-SPI discovery and a
synthetic pointer click. It runs before the license tunnel and submitter suite.
Neither smoke test validates Nuke-specific submitter selectors.

## Current Linux accessibility blocker

[Run 41544774137](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/41544774137)
installed Nuke 16.0v9 and established the license tunnel. Nuke logged a valid
license expiry and the scene opener reported success. However, all 13 GUI cases
failed or errored during accessibility application discovery; only the two
mock transport tests passed.

An unlicensed comparison in the same pinned Rocky container reproduced the
failure with Nuke's bundled Qt 6.5.3. The Qt process connected to the session
and accessibility buses but never registered with AT-SPI, even with an explicit
`AT_SPI_BUS_ADDRESS`. Official PySide6/Qt 6.5.3 in the same session registered
and accepted synthetic clicks. Nuke's `libQt6XcbQpa.so.6.5.3` lacked the
`QSpiAccessibleBridge` symbol present in the official library.
[Qt's XCB integration source](https://github.com/qt/qtbase/blob/v6.5.3/src/plugins/platforms/xcb/qxcbintegration.cpp)
guards bridge creation with `QT_NO_ACCESSIBILITY_ATSPI_BRIDGE`.
Together these findings indicate that this Nuke Qt build lacks the Linux
AT-SPI bridge. Desktop dependencies, license permissions, or a Rocky host
instead of a Rocky container do not address that build limitation.

The bundled Qt preflight therefore fails for the verified 16.0v9 installer.
Running the xa11y GUI suite requires a Foundry-supported build exposing AT-SPI,
or a separately evaluated automation approach. Replacing Nuke's Qt libraries
with system libraries has not been validated and is not part of this workflow.

## Qt event backend for the export cases

[Run 41710453902](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/41710453902)
passed a licensed Qt-driven export prototype in Nuke 16.0v9 on the Rocky runner.
The backend now reuses all nine `test_submitter_ui.py` cases, their scene scripts,
configurators, mock-traffic assertions, and existing golden-bundle comparisons.
No goldens are regenerated as part of the backend change.
Asset path collections are compared in normalized path order, matching Deadline's
set-based asset model; missing, extra, or duplicate paths still fail comparison.
Template steps and other ordered lists retain their order.

`NUKE_SUBMITTER_UI_DRIVER=qt` selects the backend. The opener drives Qt mouse/key
events on real widgets inside Nuke's GUI thread, then clicks the real local export
and confirmation dialogs. The parent pytest process independently validates the
export. Results are published atomically, and failures retain the phase, traceback,
dialog screenshot, Nuke logs, and actual bundle. Nuke remains licensed and each
case uses a fresh, serialized GUI session.

This verifies widget behavior and bundle contents; it does not verify OS input or
accessibility. It depends on Nuke shipping `PySide6.QtTest`. The four newer
interactive validation/attachment/submission cases on `feature/ci-tests` have not
been ported to this backend. Qt CI explicitly runs the nine export cases and,
when present, the two mock transport tests; those four GUI cases are not counted
as covered. macOS continues to run its complete xa11y suite.

```bash
gh workflow run integ_gui.yml --repo aws-deadline/deadline-cloud-for-nuke \
  --ref feature/ci-tests -f ui_driver=qt
```

`ui_driver=xa11y` retains the accessibility preflight and complete xa11y suite
for evaluating a future Foundry build with a working AT-SPI bridge. It is expected
to fail the bundled Qt preflight with the current 16.0v9 installer.

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

The coordinator holds the `nuke-integration-tests` concurrency group for the
entire parallel macOS/Linux suite, with no cancellation of the active run. GitHub can
replace a pending suite when multiple pushes queue, but the two platforms from
one push no longer compete for that pending slot. Each platform runs independently
of the other's result, unless the suite is explicitly cancelled.
The coordinator passes distinct child concurrency groups to the reusable
platform workflows to avoid acquiring its own lock again. Direct platform
dispatches and the existing macOS-only release call keep the shared group by
default, so they cannot overlap the coordinated suite. Other callers must keep
that default unless they already hold the shared lock themselves.
This is not a FIFO queue.
Each platform runs without xdist and starts only one licensed GUI Nuke at a time,
so the coordinated suite uses at most two simultaneous GUI sessions. The shared
Foundry license configuration lists 30 Nuke interactive seats expiring December 11,
2026; these are shared with other developers and are not reserved for CI.

## Cleanup and diagnostics

The GUI command has a 40-minute limit within the job's 60-minute limit.
On success, failure, or a catchable cancellation, traps close the display
processes and any surviving Nuke process. The tunnel helper owns a process group,
checks readiness and continuing tunnel liveness, stops its plugin and test
processes, and terminates the remote SSM session. On interruption it first sends
SIGINT to pytest and allows 45 seconds for Nuke teardown before closing the tunnel.
The outer timeout allows 90 seconds for that cleanup before forced termination.
The `always()` teardown retries
remote termination using private session state in `RUNNER_TEMP`.
A runner forcibly destroyed before cleanup completes still depends on SSM's
service-side session expiry.

Failure artifacts retain desktop logs, the final PNG screenshot, pytest JUnit
output and temporary directories (including Nuke startup logs), and failed
case `actual/` bundles for seven days. The default Qt driver writes each case's
`qt-result.json` and `qt-result.png`. For xa11y sessions, CI sets
`NUKE_SUBMITTER_UI_CAPTURE_DIAGNOSTICS=1` to save the accessibility tree and
screenshot before Nuke closes, including startup failures that got as far as
accessibility registration. The private license config and SSM log
are outside the upload paths. Installer configuration values and checksum
values are not printed by the setup helper.

The GTK/AT-SPI smoke and bundled-Qt AT-SPI preflight run only for the xa11y driver.
The normalization regressions run before licensing in either mode.
Once the bundled-Qt AT-SPI preflight passes, a licensed xa11y run must verify all nine original cases,
any additional cases on the test branch, and Linux-specific role/name selectors.
Use `NUKE_SUBMITTER_UI_DIALOG_DUMP=1` for a deliberate
diagnostic run if selectors fail; do not regenerate goldens to hide a platform
failure. macOS installation and its workflow remain available.

## Unlicensed local checks

```bash
python -m pytest test/unit/pipeline -o addopts= -q
actionlint .github/workflows/integ_gui.yml .github/workflows/integ_linux.yml .github/workflows/integ_macos.yml
zizmor --offline .github/workflows/integ_gui.yml .github/workflows/integ_linux.yml
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

With a legitimate Nuke installation already available, check its Qt bridge
without a license:

```bash
bash pipeline/run-linux-gui.sh hatch -e integ-xa11y run python pipeline/linux-gui-smoke.py \
  --qt-python "$NUKE_PYTHON" --qt-root "$(dirname "$NUKE_EXECUTABLE")"
```
