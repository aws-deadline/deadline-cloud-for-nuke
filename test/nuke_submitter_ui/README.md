# Nuke submitter UI tests

GUI tests that drive the real submitter dialog inside GUI Nuke through the
platform accessibility tree via [xa11y](https://github.com/xa11y/xa11y),
running fully offline against the mock Deadline backend from
[deadline-cloud-test-fixtures](https://github.com/aws-deadline/deadline-cloud-test-fixtures)
— no farm, no AWS credentials. This suite is the replacement path for the
Squish suite in `test/squish/`, which stays until all of its cases are
ported.

The Linux CI export cases use Qt mouse/key events inside Nuke because the
verified Linux installer does not expose an AT-SPI bridge. This backend reuses
the nine case configurators and golden checks; it does not test OS accessibility.
macOS keeps the xa11y backend. The Hatch environment retains its `integ-xa11y`
name for both drivers.

## Requirements

- A licensed GUI Nuke install, with this repo installed into Nuke's Python
  (see `DEVELOPMENT.md`). `NUKE_EXECUTABLE` overrides discovery.
- [Hatch](https://hatch.pypa.io/), which creates the test environment and
  installs `requirements-ui-testing.txt`.
- macOS: grant the terminal running pytest Accessibility permission
  (System Settings → Privacy & Security → Accessibility), then restart it.
- Linux: run in an X11 desktop session with a window manager and AT-SPI2
  enabled on the same D-Bus session as pytest and Nuke. See
  [Linux CI setup](../../pipeline/README-linux-gui.md) for the Rocky 9 harness,
  unlicensed smoke check, and required installer/license configuration.

## Running

```
hatch run integ-xa11y:test
```

To run one case:

```
hatch run integ-xa11y:test test/nuke_submitter_ui -k custom_settings
```

The Hatch script clears the repo-wide pytest flags (coverage and xdist),
which don't apply to GUI tests. The suite is excluded from the default run
(`testpaths`) and skips when no Nuke installation is found.

Repository maintainers can run the suite on the configured macOS runner by
pushing a commit to the upstream repository's `feature/ci-tests` branch. The
`Nuke GUI Integration Tests` coordinator starts automatically and runs macOS
and Linux in parallel, with one GUI session per platform. The coordinator's shared
concurrency group prevents other suites from overlapping it. The reusable platform workflows
remain available for individual dispatches, with separate Linux installer
secrets. Linux defaults to the Qt export backend. Run the same export cases locally with:

```bash
NUKE_SUBMITTER_UI_DRIVER=qt hatch run integ-xa11y:test test/nuke_submitter_ui/test_submitter_ui.py
```

The newer interactive validation, attachment, and submission cases on the test
branch require a separate Qt port; Linux Qt CI does not claim those as covered.

Keep hands off the keyboard and mouse while tests run: they use real
(synthetic) clicks and keystrokes, which land in whatever window has focus.
A run is ~15 s with warm Nuke caches, ~35 s cold.

## Test case layout

Each case is a folder under `test_cases/`, auto-discovered by
`test_submitter_ui.py` (no registration step):

```
test_cases/<case>/
  input/scene.py        # builds the scene INSIDE GUI Nuke; must save to
                        #   $NUKE_SUBMITTER_UI_SCENE_FILE (see _opener/menu.py)
  input/configure.py    # optional: configure(dialog) drives the dialog
                        #   (receives the NukeSubmitterDialog page object)
  expected/job_bundle/  # committed goldens (normalization: _utils.py)
  expected/job_bundle_nuke17/  # optional OCIO asset/parameter overrides
  actual/               # runtime output; left behind on failure, gitignored
```

The OCIO cases use Nuke 17 overrides for its shipped `nuke-default` config.
Other versions retain the original `aces_1.2` expectations. The template stays
shared. Automatic golden updates are disabled when an override applies; review
and edit those two documents explicitly. Asset path collections are compared
without ordering, since absolute installation paths sort differently across
platforms; missing, duplicate, and changed assets still fail.

## Adding a test case

1. Create `test_cases/<case>/input/scene.py`. Build the scene inside Nuke and
   save it to the path in `NUKE_SUBMITTER_UI_SCENE_FILE`.
2. Add `input/configure.py` when the case must change submitter settings. It
   must define `configure(dialog)` using the page objects in `pages.py`.
3. Generate the expected job bundle:

   ```
   NUKE_SUBMITTER_UI_UPDATE_GOLDENS=1 hatch run integ-xa11y:test test/nuke_submitter_ui -k <case>
   ```

4. Review the generated files under `expected/job_bundle/`, then run the case
   again without `NUKE_SUBMITTER_UI_UPDATE_GOLDENS`.
5. Run `hatch run integ-xa11y:test` to verify the complete xa11y suite.

Diagnostic env vars:

- `NUKE_SUBMITTER_UI_DIALOG_DUMP=1` — dump both settings tabs' accessibility
  trees (for harvesting selectors, which differ across platforms) and fail
  without exporting.
- `NUKE_SUBMITTER_UI_UPDATE_GOLDENS=1` — regenerate a case's goldens from the
  run's verified bundle; review the diff before committing.
- `MOCK_DEADLINE_RESPONSE_DELAY_S` — mock backend per-response latency
  (default 0.3, approximating the real service).

## Platform notes

The accessibility-layer ground rules (Qt.Tool window visibility, anonymous
widgets, combo popup and spin-box workarounds) are documented once,
canonically, in the `pages.py` module docstring.

### Windows desktop runner

Verified on Windows Server 2022 / Nuke 17.1v2 / Qt 6.5.3 on 2026-11-04:
all nine GUI cases and four bundle-comparison checks passed in active RDP Session 2,
with no skips and native exit code 0. Teardown left no Nuke/frame-server workers.

Use a clean, isolated checkout and a licensed Nuke installation with its bundled Python and existing Foundry
licensing configuration. Foundry uses port 6101; C4D's ports 5054/7054 alone are
insufficient. Verify the actual Foundry forwarding and license availability.
The runner does not install Nuke or change licensing.

From an unlocked RDP desktop, with no other DCC or agent using the desktop:

```powershell
$env:NUKE_EXECUTABLE = 'C:\Program Files\Nuke17.1v2\Nuke17.1.exe'
$env:NUKE_PYTHON = 'C:\Program Files\Nuke17.1v2\python.exe'
.\pipeline\run-nuke-ui-windows.ps1 -RunDirectory C:\Dev\nuke-ui-runs\unique-run
```

Use the paths for the actual installation. `-PreflightOnly` checks desktop
access and installation paths without installing dependencies or launching Nuke;
it does not prove that a license can be acquired. For a focused run, pass
`-PytestArguments @('-k', 'basic_workflow')`.

The runner rejects Session 0, unavailable input desktops, existing interactive
DCC processes, and concurrent instances of this runner. It installs submitter
dependencies into the new run directory using Nuke's Python, sets a dedicated
`HATCH_DATA_DIR`, and records `runner.log`, `dependencies.log`, `pytest.log`,
`results.xml`, and per-case Nuke logs under `pytest/`. Native stderr is captured
with PowerShell's error preference set to `Continue`; pytest's native exit code
is returned. Preserve failure artifacts before removing the run directory.
Nuke inherits the isolated dependency directory through
`NUKE_SUBMITTER_UI_PYTHONPATH`; do not put it in pytest's `PYTHONPATH`, which
can bypass the test environment's pywin32 initialization. Windows processes
are owned by a Job Object so teardown also stops frame-server workers that
outlive the main GUI process.

SSM can inspect the host and prepare source/dependencies, but GUI tests must run
in the active desktop. Before using Task Scheduler, inspect `query user` and
existing task definitions. A scoped temporary task must use the logged-in user's
`InteractiveToken` (`LogonType Interactive` in PowerShell), and must be removed
after its logs are preserved. Do not reuse another test's task or guess desktop
credentials.

A Windows CI runner must have an unlocked, dedicated interactive desktop and
existing Nuke licensing. A runner installed as a Windows service runs in Session
0 and is unsuitable. Before enabling automation, verify the complete suite in
that runner's session, coordinate desktop ownership, and serialize licensed runs
with the existing workflow's `nuke-integration-tests` concurrency group.
PR-trigger access remains deferred; the GitHub workflow below uses the existing
installer bucket and license credentials.
Windows foreground recovery is not implemented; a dedicated desktop is required.

## Status

Ported Squish cases:

| Squish case | case(s) here |
| --- | --- |
| `basic_workflow_gui` | `basic_workflow` |
| `custom_frame_range_gui` | `custom_frame_range` |
| `default_frame_range_gui` | `default_frame_range` |
| `write_node_limit_gui` | `write_node_frame_limit` |
| `write_node_gui` | `write_node_selection_single`, `write_node_selection_all` |
| `custom_settings_gui` | `custom_settings` |
| `ocio_gui` | `ocio_stock_write1`, `ocio_stock_write2` |

`write_node_gui` and `ocio_gui` each submitted twice from one scene; since a
case here exports one bundle, each submission became its own case. The OCIO
cases pin `aces_1.2` on older installations and `nuke-default` on Nuke 17,
which no longer ships the legacy ACES files.

Remaining: `manual_attachments_gui`, `invalid_conda_gui`. Squish stays until they are ported.

Scenes are built programmatically rather than opening the Squish `.nk` sample
files, so the suite needs no Git LFS assets and each case's inputs are
readable in its `scene.py`.

## Interaction coverage

Two focused cases reuse the basic scene and mock backend, with output kept in
pytest's temporary directory. They inspect actual exported YAML rather than
adding new golden bundles:

| Case | Assertions |
| --- | --- |
| `test_manual_attachments_add_remove_and_export` | Add two real input files, remove one, add an output directory, and export. The asset references contain exactly the retained file, the scene, and both automatic and manual output directories. Paths contain spaces to exercise the picker. |
| `test_empty_frame_override_validation_and_recovery` | Enable an empty frame override, assert the specific validation message, dismiss it, and check that no bundle was exported. Correct the range in the same dialog and validate the resulting OpenJD template and `Frames=7-9`. |

These cases cover attachment editing and validation/recovery with little new
infrastructure. The attachment case extends the old Squish add-only behavior
with removal and exported-content assertions, but does not port its submission
step. The old `invalid_conda_gui` types invalid names and then checks hardcoded
default field values; it never asserts a validation message or package
resolution. It is not evidence of invalid-Conda feedback coverage.

The export/validation interaction cases reject unmatched mock requests.
Any `CreateJob` request would be unmatched because their mock has no submission route.
Submission now has its own focused mock and cases below.

## Submission coverage

`_submission_mock.py` extends the shared mock locally with two HTTP routes:
`CreateJob` validates and records the real client request, and `GetJob`
transitions from `CREATE_IN_PROGRESS` to `CREATE_COMPLETE`. It runs in a
separate spawned process, as required when native accessibility calls hold
pytest's GIL. Each test gets a fresh server.

The mock queue uses shared storage: it has no `jobAttachmentSettings`.
This is a supported client path that sends a job without S3 transfers.
The real Nuke scene, bundle builder, submission worker, client and botocore
HTTP path run normally. Fake credentials, isolated configuration and
loopback endpoint overrides keep the tests offline. The mock rejects
attachment payloads and unexpected routes. S3 upload, rendering and
rendered-output assertions remain outside this coverage.

| Case | Assertions |
| --- | --- |
| `test_submission_success` | Press Submit; verify completion status, returned job ID, and dialog closure. Assert one `CreateJob`, polling through creation, and the requested name, priority and frame range in the HTTP payload. |
| `test_submission_api_failure_and_retry` | Reject the first `CreateJob` with `ValidationException`; verify the error details and Close button, then retry from the same submitter. Assert two attempts and exactly one successfully created job, with the same settings. |
| `test_real_client_submission_transport` (two variants) | Submit the existing evidence-based basic bundle through the real client in a subprocess, with and without the initial API rejection. Verify the same captured request assertions and polling. These checks require no Nuke and verify the HTTP mock contract; they do not verify the GUI. |

Run the transport checks alone with:

```
hatch run integ-xa11y:test test/nuke_submitter_ui/test_submission_transport.py
```

Both transport variants passed locally on Linux with Python 3.11.18,
`deadline` 0.60.11 and `deadline-cloud-test-fixtures` 0.18.25.

### Live verification and remaining platform checks

The [first licensed macOS CI run](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/41544466504)
on Nuke 16.0v7 passed both submission GUI cases and validation recovery
(14 passed overall). The attachment case failed because Nuke exposed a Qt
picker, rather than the assumed native macOS sheet. After the helper was
updated to choose the picker path from its exposed controls, the
[licensed macOS rerun](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/41545926800)
at commit `32b1344` passed all 15 tests with no skips in 255.09 seconds.
All four new GUI cases and both real-client transport variants passed.
The runner used macOS 15, Nuke 16.0v7, Python 3.11, `deadline` 0.60.11,
`deadline-cloud-test-fixtures` 0.18.25 and `xa11y` 0.15.4.

This confirms the Qt attachment picker, attachment row selection/removal,
validation feedback and recovery, submission completion and same-dialog
retry on that runner. The native macOS Go to Folder fallback and other
platforms still require live verification. Collection and static checks
cannot verify accessibility selectors. On a licensed runner with the
repository and declared dependencies installed into Nuke's Python, run:

```
hatch run integ-xa11y:test test/nuke_submitter_ui -k 'manual_attachments or empty_frame_override or submission_success or submission_api_failure'
hatch run integ-xa11y:test
```

Verify that all four new GUI cases **pass**, rather than skip. Check the runner's
native macOS Go to Folder sheet or Qt File name/Directory/Folder controls, the
attachment row selection/removal, and the host-owned error message/OK button.
For submission, verify the progress window's completion label, job ID in
the log, and OK/Close buttons, including same-dialog retry after failure.
The Qt picker selectors passed the macOS rerun. No golden update was needed.
Record the runner OS, Nuke version, dependency versions and results before
claiming GUI validation.

## Windows GitHub CI

`integ_windows.yml` runs the mock-backend GUI suite on a standard `windows-2025`
runner with Mesa software OpenGL. A manual dispatch on `mainline` or
`feature/ci-tests` with `installer_s3_key` set to
`nuke/17/Nuke17.1v2-win-x86_64.zip` enables the complete suite. Omitting the key
runs only the unlocked-desktop preflight; that does not verify Nuke or licensing.
PR-triggered licensed runs remain deferred.

```bash
gh workflow run integ_windows.yml --ref mainline \
  -f installer_s3_key=nuke/17/Nuke17.1v2-win-x86_64.zip
```

The installer comes from the existing shared `INSTALLER_BUCKET`, using the CI
OIDC role and expected bucket owner. The script verifies the archive SHA-256
and the MSI's Foundry signature before installation. The licensed run shares
`nuke-integration-tests` concurrency with macOS/Linux and uses the existing CI
license connection. No IAM or repository-secret changes are required. Before
starting a run, check for pending licensed workflows: a new arrival can replace
the group's pending run even with `cancel-in-progress: false`.

### Software OpenGL

Standard Windows runners expose an unlocked desktop but do not provide Nuke's
required OpenGL support. Qt's older `opengl32sw.dll` did not resolve Nuke's native
graphics startup. The working setup uses mesa-dist-win 26.2.6's x64 MinGW
`opengl32.dll` and `libgallium_wgl.dll` with CPU rendering through llvmpipe.
The archive and both DLLs have verified SHA-256 pins.

Mesa is maintained through reviewed version and checksum updates, following the
[Blender Windows GUI workflow](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/.github/workflows/submitter_gui_tests.yml).
Dependabot does not update these pins. To upgrade Mesa, update `ARCHIVE_URL`,
`ARCHIVE_SHA256` and `DLL_HASHES` in `pipeline/prepare-native-mesa-windows.py`
for the selected x64 MinGW release. Verify the release artifacts, run the full
Windows GUI suite, and include its results in the upgrade PR before merging.

The helper copies the installed Nuke runtime into a fresh directory under
`RUNNER_TEMP`, adds those two libraries and a per-application `.local` redirection
marker, and sets `GALLIUM_DRIVER=llvmpipe` and `QT_OPENGL=desktop`. It probes the
selected OpenGL implementation and records its vendor, renderer and version.
Only the temporary copy uses Mesa; installed Nuke files and system drivers remain
untouched. Original executable, Python and overlay-target hashes are verified
before and after testing. Mesa is a CI test dependency, not a released package
component. Retain upstream license notices when managing the pinned distribution;
Mesa's core MIT license does not describe every bundled component's license.

The [verified GitHub run](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/43892583632)
on November 16, 2026 used Windows Server 2025 (build 26100), Nuke 17.1v2, and
Mesa 26.2.6 / llvmpipe with OpenGL 4.6. It passed **25 tests: 13 actual GUI cases
and 12 supporting checks**, with zero failures, errors or skips in 484.80 seconds.
This includes the original nine export cases, manual attachments, validation
recovery and both mock submission paths. Original Nuke file verification passed.
This establishes submitter GUI compatibility on that runner; it does not test
GPU rendering performance or establish long-term runner reliability.

After narrowing the native Windows attachment picker's confirmation-button
selector, the [full rerun](https://github.com/aws-deadline/deadline-cloud-for-nuke/actions/runs/43909094072)
passed all 25 tests with zero failures, errors or skips in 492.81 seconds.
The runner reported exit code 0 and verified the original Nuke files unchanged.

The workflow preserves JUnit results, runner/dependency/pytest logs, per-case Nuke
startup logs and screenshots, installer logs, license status and Mesa's
`probe.json`. For startup diagnosis, pass `-f diagnose_startup=true` to stop after
the first failure. Full runs continue through all cases by default.
