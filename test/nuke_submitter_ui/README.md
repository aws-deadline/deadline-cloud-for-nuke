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
  actual/               # runtime output; left behind on failure, gitignored
```

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
cases pin the `aces_1.2` stock config, as the Squish scene did.

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
