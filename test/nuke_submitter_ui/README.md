# Nuke submitter UI tests (xa11y)

GUI tests that drive the real submitter dialog inside GUI Nuke through the
platform accessibility tree via [xa11y](https://github.com/xa11y/xa11y),
running fully offline against the mock Deadline backend from
[deadline-cloud-test-fixtures](https://github.com/aws-deadline/deadline-cloud-test-fixtures)
— no farm, no AWS credentials. This suite is the replacement path for the
Squish suite in `test/squish/`, which stays until all of its cases are
ported.

## Requirements

- A licensed GUI Nuke install, with this repo installed into Nuke's Python
  (see `DEVELOPMENT.md`). `NUKE_EXECUTABLE` overrides discovery.
- [Hatch](https://hatch.pypa.io/), which creates the test environment and
  installs `requirements-ui-testing.txt`.
- macOS: grant the terminal running pytest Accessibility permission
  (System Settings → Privacy & Security → Accessibility), then restart it.

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
`Nuke xa11y Integration Tests - macOS` workflow starts automatically.

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
PR-trigger access, installer provisioning, IAM, and secrets remain deferred.
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

## Windows GitHub runner trial

`integ_windows.yml` accepts a `windows_runner` choice, defaulting to
`windows-2025`, with `windows-2022` and C4D's
`aws-deadline_windows-2025_gpu-t4-4-core` as alternatives. It checks for an
unlocked interactive desktop before running tests. The GPU runner is billed and
requires repository access; the Nuke repository currently lacks that access.
Standard Windows images must still demonstrate Nuke's required OpenGL support.
The full GUI job is enabled only by a manual dispatch on `feature/ci-tests`
with `installer_s3_key` set to `nuke/17/Nuke17.1v2-win-x86_64.zip`.
It downloads from the same `INSTALLER_BUCKET` as Linux and macOS, using the
existing CI OIDC role and expected bucket owner. The installer script verifies
SHA-256 and the MSI's Foundry signature before installation. It uses the EULA
acceptance already authorized for this test setup.

The GUI job shares the existing licensed-run concurrency group and CI license
role. It installs submitter dependencies into temporary artifacts, runs the
complete mock-backend suite, and preserves JUnit results and logs. It does not
enable PR triggers or change IAM or repository secrets.

A dispatch without an installer key runs only the desktop check. That result
does not establish Nuke licensing or GUI test success. For a full trial:

```bash
gh workflow run integ_windows.yml --ref feature/ci-tests \
  -f windows_runner=windows-2025 \
  -f installer_s3_key=nuke/17/Nuke17.1v2-win-x86_64.zip
```

Before a full manual trial, check that no licensed workflow is already queued.
GitHub concurrency groups allow one running and one pending member, and a new
arrival can replace the pending member even with `cancel-in-progress: false`.

The Nuke 17.1v2 trial on the standard `windows-2022` runner passed desktop,
installer, and license setup, but Nuke reported `You need OpenGL 2.1 or better`
before opening an accessible window. This runner has not passed the GUI suite.
An unlocked desktop alone is insufficient: the runner must also provide the
OpenGL support required by Nuke. Inspection of the verified workstation
installation found no bundled software OpenGL DLL.

For startup diagnosis, add `-f diagnose_startup=true` to the dispatch command.
This stops at the first failed case and preserves Nuke stdout/stderr alongside
available accessibility diagnostics. A diagnostic run does not verify the full
suite; use the default full run after resolving the runner's graphics requirement.


### Isolated software OpenGL trial

Standard Windows 2022 and Windows 2025 runner trials both failed Nuke GUI startup
with `You need OpenGL 2.1 or better`, despite successful desktop, installation,
and licensing checks. An opt-in software trial extracts only `opengl32sw.dll`
from the official PySide6-Essentials 6.5.3 Windows wheel, matching the verified
Nuke 17.1v2 Qt runtime. Both the wheel and DLL SHA-256 values are pinned.

The helper stores the library under the runner's temporary directory, probes its
OpenGL version/vendor/renderer through a hidden native WGL context, and sets
`QT_OPENGL=software` plus an absolute `QT_OPENGL_DLL` path for this job. It does
not install PySide, replace installed Nuke DLLs, or change the workstation.
The probe establishes the library's capability; only actual Nuke startup and
test results establish whether Nuke uses it successfully.

```bash
gh workflow run integ_windows.yml --ref feature/ci-tests \
  -f windows_runner=windows-2025 -f software_opengl=true \
  -f installer_s3_key=nuke/17/Nuke17.1v2-win-x86_64.zip \
  -f diagnose_startup=true
```

This startup trial stops on the first error. Run the full suite with
`diagnose_startup=false` after demonstrating successful startup. The artifact
includes `nuke-software-opengl/probe.json` and Nuke's graphics/startup logs.

The Windows 2025 Qt-only trial on November 9, 2026 reported Mesa OpenGL 3.0 in
the independent probe, but Nuke 17.1v2 crashed with `glewInit failed: Missing GL
version` and an invalid `GlfGLContext`. Its first GUI case ended in a setup
error. This configuration has not passed Nuke GUI startup.

### Isolated native Mesa trial

The alternative `native_mesa` trial copies the installed Nuke runtime into a
new directory under `RUNNER_TEMP`, then adds the pinned x64 `opengl32.dll` and
`libgallium_wgl.dll` from the published mesa-dist-win 26.2.6 MinGW release.
The archive and both DLLs have verified SHA-256 pins. It selects llvmpipe and
desktop OpenGL so native Nuke graphics code can use Mesa as well as Qt.
Only the copy receives the per-application `.local` DLL redirection marker.
Original Nuke executable, Python, and overlay-target hashes are checked before
and after the trial. No system driver registration, registry changes, upstream
deployment scripts, or workstation changes are involved.

```bash
gh workflow run integ_windows.yml --ref feature/ci-tests \
  -f windows_runner=windows-2025 -f native_mesa=true \
  -f installer_s3_key=nuke/17/Nuke17.1v2-win-x86_64.zip \
  -f diagnose_startup=true
```

Select only one software trial. The artifact includes
`nuke-native-mesa/probe.json`; an independent probe result does not establish
Nuke compatibility. Run the full suite after successful Nuke GUI startup.
