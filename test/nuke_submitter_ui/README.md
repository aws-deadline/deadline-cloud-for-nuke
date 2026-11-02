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

Submission success and API failure/retry remain gaps. The allowed shared
mock backend (inspected at `deadline-cloud-test-fixtures` 0.18.25) exposes
resource-read routes, but no `CreateJob` route. These tests assert no
`CreateJob` calls; adding submission coverage requires a separate mock
submission design, including attachment transfer, rather than relying on
real AWS or treating a local export as submission.

### Required live verification for the interaction cases

The interaction cases have not yet been run in licensed GUI Nuke. Collection
and static checks cannot verify accessibility selectors or native file pickers.
On a licensed Nuke 16.0v7 runner with the repository and declared dependencies
installed into Nuke's Python, run:

```
hatch run integ-xa11y:test test/nuke_submitter_ui -k 'manual_attachments or empty_frame_override'
hatch run integ-xa11y:test
```

Verify that both new cases **pass**, rather than skip. Check the macOS native
Go to Folder sheet and the File name/Directory/Folder controls on Linux/Windows, the
attachment row selection/removal, and the host-owned error message/OK button.
The new picker selectors are based on the dialogs' source and platform
conventions, and still require live confirmation. No golden update is needed.
Record the runner OS, Nuke version, dependency versions and results before
claiming GUI validation.
