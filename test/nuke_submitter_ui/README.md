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
- Test dependencies: `pip install -r requirements-ui-testing.txt`
- macOS: grant the terminal running pytest Accessibility permission
  (System Settings → Privacy & Security → Accessibility), then restart it.

## Running

```
python -m pytest test/nuke_submitter_ui -o addopts= -q
```

`-o addopts=` clears the repo-wide pytest flags (coverage and xdist), which
don't apply to GUI tests. The suite is excluded from the default run
(`testpaths`) and skips when no Nuke installation is found.

Keep hands off the keyboard and mouse while tests run: they use real
(synthetic) clicks and keystrokes, which land in whatever window has focus.
A run is ~15 s with warm Nuke caches, ~35 s cold.

## Test case layout

Each case is a folder under `test_cases/` registered in
`test_submitter_ui.py`:

```
test_cases/<case>/
  input/scene.py        # builds the scene INSIDE GUI Nuke; must save to
                        #   $NUKE_SUBMITTER_UI_SCENE_FILE (see _opener/menu.py)
  input/configure.py    # optional: configure(dialog) drives the dialog
                        #   (receives the NukeSubmitterDialog page object)
  expected/job_bundle/  # committed goldens (normalization: utils.py)
  actual/               # runtime output; left behind on failure, gitignored
```

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

Ported Squish cases: `basic_workflow_gui` (as case `basic_workflow`).
Remaining: 8 cases — see `test/squish/suite_nuke_submitter/`.
