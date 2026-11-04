# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Page object for the Nuke render submitter dialog.

Extends the shared-dialog page object from ``deadline-cloud-test-fixtures``
with accessors for the Nuke ``SceneSettingsWidget`` (Job-specific settings
tab).

Platform notes — verified on macOS 15 / Nuke 16.0v7 and Windows Server 2022 /
Nuke 17.1v2 (Qt 6.5.3). This is
the canonical write-up for the suite; other modules reference it:

* Qt.Tool windows: the submitter dialog is a ``Qt.Tool`` window, and
  macOS removes those from the accessibility tree whenever the owning
  app is not frontmost. Every accessor therefore re-asserts Nuke
  frontmost first (the ``ensure_frontmost`` hook), making tests
  self-healing after brief focus steals. Synthetic input still lands in
  whatever window has focus at the moment it fires — keep hands off the
  machine while tests run.
* The dialog window title is ``Submit Rendering to AWS Deadline Cloud``
  (Nuke overrides the shared client default).
* Most scene-settings widgets are anonymous in the accessibility tree
  (no ``setAccessibleName``/``setBuddy`` in ``scene_settings_tab.py``),
  and Qt tab pages drop out of the tree when inactive, so accessors are
  positional (``nth``, 1-BASED) scoped to the active Job-specific tab.
  Positions follow the layout order of ``scene_settings_tab.py``;
  revisit after UI changes there. An accessible-naming pass will make
  these selectors robust.
* QComboBox accessible names mirror their current text, so combos are
  addressed positionally, never by name. Popup items expose no working
  AX activation action (rows accept only ``focus``; pressing their text
  is a no-op), so selection uses ``show_menu`` plus physical input: a
  real click at the target row, falling back to arrow keys + Enter.
* QSpinBox AX increment/decrement and direct numeric writes are unreliable
  on macOS. Focusing the control and sending physical Up/Down keys uses the
  widget's single step. Every transition is verified before continuing.
* Windows UIA exposes the submitter as a nested ``dialog``, combo selections
  as ``value``, and popup entries as ``list_item`` names. Open combos with a
  physical click because ``show_menu`` is unsupported. The same physical
  spin-box transitions work on the active Windows desktop. Windows has no
  foreground-recovery hook here; keep that desktop dedicated to the tests.
"""

from __future__ import annotations

import re
import sys
import time
from functools import partial
from pathlib import Path
from typing import Callable

import xa11y
from _constants import WRITE_NODES_ALL  # noqa: F401 (public page-object constant)
from _utils import log
from deadline_test_fixtures.xa11y import SharedSubmitterDialog, dismiss_bundle_saved_popup
from deadline_test_fixtures.xa11y.controls import (
    TAB_JOB_SPECIFIC,
    TAB_SHARED,
    is_checked,
    set_checkbox,
    set_text_field,
    switch_to_tab,
)

DIALOG_TITLE = "Submit Rendering to AWS Deadline Cloud"

WIDGET_TIMEOUT = 30.0
FARM_RESOLVE_TIMEOUT = 30.0
EXPORT_TIMEOUT = 60.0
POPUP_TIMEOUT = 10.0
_MAX_SPIN_KEY_PRESSES = 100
_SPIN_VALUE_PATTERN = re.compile(r"-?\d+")

# Positional indexes on the active Job-specific tab, in document order.
# NOTE: xa11y Locator.nth is 1-BASED.
_COMBO_WRITE_NODES = 1
_COMBO_VIEWS = 2
_SPIN_CHUNK_SIZE = 1
_SPIN_TARGET_CHUNK_DURATION = 2
_TEXT_FRAME_RANGE = 1

# Positional within the shared tab's "Job Properties" group, in document order
# (1-based). That group lives in the shared client's UI, so its name is the
# stable anchor and only the order inside it is positional.
_GROUP_JOB_PROPERTIES = "Job Properties"
_SPIN_PRIORITY = 1
_SPIN_MAX_FAILED_TASKS = 2
_SPIN_MAX_RETRIES = 3

# Accessible names that exist today (Qt auto-derived from label/text).
CHECKBOX_OVERRIDE_FRAME_RANGE = "Override frame range"
CHECKBOX_PROXY_MODE = "Use proxy mode"
CHECKBOX_CONTINUE_ON_ERROR = "Continue on error"
CHECKBOX_USE_TIMEOUTS = "Use timeouts"
CHECKBOX_INCLUDE_GIZMOS = "Include gizmos in job bundle"
# The Description field's AX name is inherited from its QGroupBox — an
# artifact of the missing naming pass, not a real name.
_DESCRIPTION_FIELD_AX_NAME = "Job Properties"


def _spin_value(element: xa11y.Element | None) -> int | None:
    if element is None or element.value is None:
        return None
    match = _SPIN_VALUE_PATTERN.search(element.value)
    return int(match.group()) if match else None


def _spin_value_changed(element: xa11y.Element | None, *, previous: int) -> bool:
    current = _spin_value(element)
    return current is not None and current != previous


class NukeSubmitterDialog(SharedSubmitterDialog):
    """Drives the Nuke submitter dialog through the accessibility tree.

    Rooted at the dialog window locator so selectors cannot leak into
    Nuke's main window; keeps the app handle for popups (message boxes,
    combo popups) that surface outside the dialog window.
    """

    def __init__(
        self,
        app: xa11y.App,
        window: xa11y.Locator,
        ensure_frontmost: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(window, app_root=app)
        self.app = app
        self.window = window
        self._ensure_frontmost = ensure_frontmost or (lambda: None)

    @classmethod
    def wait_for(
        cls,
        app: xa11y.App,
        timeout: float = WIDGET_TIMEOUT,
        ensure_frontmost: Callable[[], object] | None = None,
    ) -> "NukeSubmitterDialog":
        if ensure_frontmost is not None:
            ensure_frontmost()
        # Windows UIA exposes the Qt.Tool submitter as a dialog nested under
        # Nuke's main window; macOS exposes it as a window.
        window = app.locator(f'window[name="{DIALOG_TITLE}"], dialog[name="{DIALOG_TITLE}"]')
        window.wait_visible(timeout=timeout)
        return cls(app, window, ensure_frontmost)

    def _front(self) -> None:
        """Re-assert Nuke frontmost (see module notes on Qt.Tool windows)."""
        self._ensure_frontmost()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def switch_to_shared_tab(self) -> None:
        self._front()
        switch_to_tab(self.window, TAB_SHARED, timeout=WIDGET_TIMEOUT)

    def switch_to_job_specific_tab(self) -> None:
        self._front()
        switch_to_tab(self.window, TAB_JOB_SPECIFIC, timeout=WIDGET_TIMEOUT)

    # ------------------------------------------------------------------
    # Shared job settings
    # ------------------------------------------------------------------

    def set_job_name(self, name: str) -> str:
        self.switch_to_shared_tab()
        return set_text_field(self.window, "Name", name, timeout=WIDGET_TIMEOUT)

    def set_job_description(self, description: str) -> str:
        self.switch_to_shared_tab()
        return set_text_field(
            self.window, _DESCRIPTION_FIELD_AX_NAME, description, timeout=WIDGET_TIMEOUT
        )

    def wait_farm_resolved(self, farm_name: str, timeout: float = FARM_RESOLVE_TIMEOUT) -> None:
        """Wait until the farm display name appears in the dialog tree,
        i.e. ListFarms against the backend succeeded."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._front()
            try:
                if farm_name in self.window.element().dump():
                    return
            except Exception:
                # Transient AX-tree churn (see module notes); retry.
                pass
            time.sleep(0.5)
        raise TimeoutError(
            f"Farm {farm_name!r} did not resolve within {timeout}s\n{self.dump_tree()}"
        )

    def wait_settled(self, timeout: float = FARM_RESOLVE_TIMEOUT) -> None:
        """Wait for the queue-environment loading caption to clear.

        The shared client shows "Loading Queue Environments..." while it
        rebuilds queue parameter widgets; waiting for it to disappear is the
        dialog's own "finished loading" signal. A dialog stuck in the ERROR
        state fails fast here — proceeding would only fail later with an
        unrelated message. The loading/reloading wait itself is non-fatal.
        """
        self._front()
        error = self.window.descendant("static_text[name^='Error loading queue environments']")
        try:
            if error.exists():
                raise AssertionError(
                    f"dialog is in a queue-environment error state\n{self.dump_tree()}"
                )
        except AssertionError:
            raise
        except Exception:
            # Transient AX-tree churn (see module notes); the loading wait
            # below still covers settling.
            pass
        loading = self.window.descendant(
            "static_text[name^='Loading Queue Environments'], "
            "static_text[name^='Reloading Queue Environments']"
        )
        try:
            loading.wait_hidden(timeout=timeout)
        except Exception as exc:
            # Non-fatal: absence of the caption is the common steady state.
            log(f"queue-environment settle wait ended without signal: {exc!r}")

    def dump_settings_tabs(self) -> None:
        """Print each settings tab's accessibility subtree.

        Selector-harvesting aid: accessible role+name pairs differ between
        macOS AX and Windows UIA and cannot be guessed, so contributors run
        the suite with NUKE_SUBMITTER_UI_DIALOG_DUMP=1 to capture them when
        writing a case configurator (see README).
        """
        for tab in (TAB_SHARED, TAB_JOB_SPECIFIC):
            print(f"=== DIALOG_DUMP: {tab} (depth 15) ===")
            try:
                self._front()
                switch_to_tab(self.window, tab, timeout=WIDGET_TIMEOUT)
                print(self.window.element().dump(max_depth=15))
            except Exception as exc:
                print(f"dump of {tab!r} failed: {exc!r}")
            print(f"=== DIALOG_DUMP: end {tab} ===")

    # ------------------------------------------------------------------
    # Job-specific (scene) settings — positional, tab must be active
    # ------------------------------------------------------------------

    def _job_specific_combo(self, index: int) -> xa11y.Locator:
        self._front()
        combo = self.window.descendant("combo_box").nth(index)
        combo.wait_visible(timeout=WIDGET_TIMEOUT)
        return combo

    def write_nodes_combo(self) -> xa11y.Locator:
        return self._job_specific_combo(_COMBO_WRITE_NODES)

    def views_combo(self) -> xa11y.Locator:
        return self._job_specific_combo(_COMBO_VIEWS)

    def selected_write_node(self, timeout: float = WIDGET_TIMEOUT) -> str:
        """Current selection: Windows exposes its value, macOS its name."""
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            self._front()
            try:
                element = self.write_nodes_combo().element()
                if sys.platform == "win32":
                    return element.value or element.name or ""
                return element.name or ""
            except Exception as exc:
                # Transient AX-tree churn (see module notes); retry.
                last_error = exc
                time.sleep(0.5)
        raise TimeoutError(f"Could not read write-node combo: {last_error!r}")

    def _popup_rows(self, timeout: float = POPUP_TIMEOUT) -> list[tuple[xa11y.Element, str]]:
        """Open combo popup rows: unique ``(row_element, label)`` pairs.

        macOS exposes the popup list twice (floating dialog + nested under
        the combo); the floating copy comes first and is the clickable one.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows: list[tuple[xa11y.Element, str]] = []
            seen: set[str] = set()
            try:
                selector = "list_item" if sys.platform == "win32" else "table_row"
                for row in self.app.locator(selector).elements():
                    label = (
                        (row.name or "")
                        if sys.platform == "win32"
                        else next(
                            (c.name or "" for c in row.children() if (c.name or "").strip()), ""
                        )
                    )
                    if label and label not in seen:
                        seen.add(label)
                        rows.append((row, label))
            except Exception:
                # Transient AX-tree churn (see module notes); retry.
                rows = []
            if rows:
                return rows
            time.sleep(0.5)
        return []

    def _open_write_node_popup(
        self, label: str
    ) -> tuple[list[tuple[xa11y.Element, str]], xa11y.Element]:
        """Open the write-node popup; return its rows and the row for *label*."""
        self._front()
        combo = self.write_nodes_combo()
        if sys.platform == "win32":
            # The Windows bridge does not support show_menu on Qt combos.
            xa11y.input_sim().click(combo.element())
        else:
            combo.show_menu()
        rows = self._popup_rows()
        target = next((row for row, name in rows if name == label), None)
        if target is None:
            xa11y.input_sim().press("Escape")
            raise AssertionError(
                f"Write node {label!r} not in popup: {[name for _, name in rows]}\n"
                f"{self.dump_tree()}"
            )
        return rows, target

    def _select_write_node_by_click(self, label: str) -> bool:
        """Physical click on the popup row (see module notes on combos)."""
        _, target = self._open_write_node_popup(label)
        xa11y.input_sim().click(target)
        time.sleep(1.0)
        return self.selected_write_node() == label

    def _select_write_node_by_keyboard(self, label: str) -> bool:
        """Arrow keys + Enter fallback for popup-row selection."""
        rows, _ = self._open_write_node_popup(label)
        ordered = [name for _, name in rows]
        current = self.selected_write_node()
        steps = ordered.index(label) - (ordered.index(current) if current in ordered else 0)
        sim = xa11y.input_sim()
        key = "ArrowDown" if steps >= 0 else "ArrowUp"
        self._front()
        for _ in range(abs(steps)):
            sim.press(key)
            time.sleep(0.2)
        sim.press("Enter")
        time.sleep(1.0)
        return self.selected_write_node() == label

    def select_write_node(self, label: str) -> None:
        """Select *label* in the write-node combo."""
        if self.selected_write_node() == label:
            return
        if self._select_write_node_by_click(label):
            return
        if self._select_write_node_by_keyboard(label):
            return
        raise AssertionError(
            f"Write-node selection failed: wanted {label!r}, "
            f"combo shows {self.selected_write_node()!r}"
        )

    def frame_range_field(self) -> xa11y.Locator:
        self._front()
        field = self.window.descendant("text_field").nth(_TEXT_FRAME_RANGE)
        field.wait_visible(timeout=WIDGET_TIMEOUT)
        return field

    def set_override_frame_range(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_OVERRIDE_FRAME_RANGE, enabled, timeout=WIDGET_TIMEOUT)

    def override_frame_range_enabled(self) -> bool:
        """Whether the frame-range override is checked.

        Cases that verify range inheritance assert this is off rather than
        forcing it, so a change to the dialog's default surfaces as a failure
        instead of being silently overwritten.
        """
        self._front()
        box = self.window.descendant(f'check_box[name="{CHECKBOX_OVERRIDE_FRAME_RANGE}"]')
        box.wait_visible(timeout=WIDGET_TIMEOUT)
        return is_checked(box)

    def set_frame_range(self, frame_range: str) -> None:
        """Enable the override and type a frame range (e.g. ``1-5``)."""
        self.set_override_frame_range(True)
        self.frame_range_field().set_value(frame_range)

    def set_proxy_mode(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_PROXY_MODE, enabled, timeout=WIDGET_TIMEOUT)

    def set_continue_on_error(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_CONTINUE_ON_ERROR, enabled, timeout=WIDGET_TIMEOUT)

    def set_use_timeouts(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_USE_TIMEOUTS, enabled, timeout=WIDGET_TIMEOUT)

    def set_include_gizmos(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_INCLUDE_GIZMOS, enabled, timeout=WIDGET_TIMEOUT)

    def _spin(self, index: int) -> xa11y.Locator:
        self._front()
        spin = self.window.descendant("spin_button").nth(index)
        spin.wait_visible(timeout=WIDGET_TIMEOUT)
        return spin

    def _set_spin_value(
        self,
        locate: Callable[[], xa11y.Locator],
        target: int,
        description: str,
    ) -> None:
        """Set a Qt spin box without using macOS's broken AX actions."""
        self._front()
        spin = locate()
        current = _spin_value(spin.element())
        if current is None:
            raise AssertionError(f"{description} does not expose an integer value")
        if current == target:
            return

        input_sim = xa11y.input_sim()
        observed_values = {current}
        for _ in range(_MAX_SPIN_KEY_PRESSES):
            key = "ArrowUp" if current < target else "ArrowDown"
            self._front()
            spin = locate()
            spin.focus()
            spin.wait_focused(timeout=5.0)
            input_sim.press(key)
            try:
                spin.wait_until(
                    partial(_spin_value_changed, previous=current),
                    timeout=5.0,
                )
            except xa11y.TimeoutError:
                observed = _spin_value(spin.element())
                raise AssertionError(
                    f"{description} did not change from {current} after {key}; "
                    f"stopped at {observed}"
                ) from None
            current = _spin_value(spin.element())
            if current is None:
                raise AssertionError(f"{description} stopped exposing an integer value")
            if current == target:
                return
            if current in observed_values:
                raise AssertionError(
                    f"{description} cannot reach {target}; observed a value cycle at {current}"
                )
            observed_values.add(current)

        raise AssertionError(
            f"{description} did not reach {target} after {_MAX_SPIN_KEY_PRESSES} key presses; "
            f"stopped at {current}"
        )

    def _set_spin(self, index: int, target: int) -> None:
        self._set_spin_value(lambda: self._spin(index), target, f"Spin button {index}")

    def _job_properties_spin(self, index: int) -> xa11y.Locator:
        """A spin box in the shared tab's Job Properties group."""
        self._front()
        spin = (
            self.window.descendant(f'group[name="{_GROUP_JOB_PROPERTIES}"]')
            .descendant("spin_button")
            .nth(index)
        )
        spin.wait_visible(timeout=WIDGET_TIMEOUT)
        return spin

    def _set_job_properties_spin(self, index: int, value: int, description: str) -> None:
        self.switch_to_shared_tab()
        self._set_spin_value(lambda: self._job_properties_spin(index), value, description)

    def set_priority(self, value: int) -> None:
        """Set job priority.

        Not the shared fixtures' ``set_priority``, which uses the unreliable
        macOS AX increment action.
        """
        self._set_job_properties_spin(_SPIN_PRIORITY, value, "Priority")

    def set_max_failed_tasks(self, value: int) -> None:
        self._set_job_properties_spin(_SPIN_MAX_FAILED_TASKS, value, "Maximum failed tasks")

    def set_max_retries(self, value: int) -> None:
        self._set_job_properties_spin(_SPIN_MAX_RETRIES, value, "Maximum retries per task")

    def set_chunk_size(self, chunk_size: int) -> None:
        self._set_spin(_SPIN_CHUNK_SIZE, chunk_size)

    def chunk_size(self) -> int:
        return int(self._spin(_SPIN_CHUNK_SIZE).element().value or "0")

    def set_target_chunk_duration(self, seconds: int) -> None:
        self._set_spin(_SPIN_TARGET_CHUNK_DURATION, seconds)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def submit(self) -> None:
        self._front()
        submit = self.button("Submit")
        submit.wait_enabled(timeout=WIDGET_TIMEOUT)
        submit.press()

    def _submission_progress(self) -> xa11y.Locator:
        self._front()
        progress = self.app.locator(
            "dialog[name='AWS Deadline Cloud submission'], "
            "window[name='AWS Deadline Cloud submission'], "
            "sheet[name='AWS Deadline Cloud submission']"
        )
        progress.wait_visible(timeout=EXPORT_TIMEOUT)
        return progress

    def finish_submission(self, job_id: str) -> None:
        """Verify success and the returned job ID before closing the progress UI."""
        progress = self._submission_progress()
        progress.descendant("static_text[name='Submission complete']").wait_visible(
            timeout=EXPORT_TIMEOUT
        )
        progress.wait_until(
            lambda element: element is not None and job_id in element.dump(),
            timeout=EXPORT_TIMEOUT,
        )
        ok = progress.descendant("button[name='OK']")
        ok.wait_enabled(timeout=WIDGET_TIMEOUT)
        ok.press()
        progress.wait_hidden(timeout=WIDGET_TIMEOUT)
        # The Nuke submitter closes only after a successful submission.
        self.window.wait_hidden(timeout=WIDGET_TIMEOUT)

    def dismiss_submission_error(self, message: str) -> None:
        """Assert API error details, then return to the still-open submitter."""
        progress = self._submission_progress()
        progress.wait_until(
            lambda element: element is not None
            and "Error occurred:" in element.dump()
            and message in element.dump(),
            timeout=EXPORT_TIMEOUT,
        )
        assert not progress.descendant("static_text[name='Submission complete']").exists()
        close = progress.descendant("button[name='Close']")
        close.wait_enabled(timeout=WIDGET_TIMEOUT)
        close.press()
        progress.wait_hidden(timeout=WIDGET_TIMEOUT)
        self.window.wait_visible(timeout=WIDGET_TIMEOUT)
        self.button("Submit").wait_enabled(timeout=WIDGET_TIMEOUT)

    def export_bundle(self, timeout: float = EXPORT_TIMEOUT) -> None:
        """Save the bundle locally and dismiss the host-owned confirmation."""
        self._front()
        self.save_bundle_locally(timeout=timeout)
        pid = self.app.pid
        if pid is None:
            raise RuntimeError("Cannot dismiss bundle saved confirmation without a Nuke process ID")
        if not dismiss_bundle_saved_popup(pid, timeout=timeout):
            raise TimeoutError(
                f"Bundle saved confirmation did not appear in {timeout}s\n{self.dump_tree()}"
            )

    def export_bundle_expect_error(self, message: str, timeout: float = EXPORT_TIMEOUT) -> None:
        """Attempt a local export and assert the callback's validation feedback."""
        self._front()
        self.save_bundle_locally(timeout=timeout)
        # Host-owned message boxes can have no accessible title on macOS.
        # Match the body, as dismiss_bundle_saved_popup does, before pressing OK.
        body = self.app.locator("static_text[name^='Failed to export bundle:']")
        body.wait_visible(timeout=timeout)
        assert message in (body.element().name or ""), self.app.dump()
        ok = self.app.locator(
            "dialog button[name='OK'], window button[name='OK'], sheet button[name='OK']"
        )
        ok.wait_enabled(timeout=timeout)
        ok.press()
        body.wait_hidden(timeout=timeout)
        self.button("Save bundle as").wait_enabled(timeout=timeout)

    def _attachment_group(self, name: str) -> xa11y.Locator:
        self._front()
        switch_to_tab(self.window, "Job attachments", timeout=WIDGET_TIMEOUT)
        group = self.window.descendant(f'group[name="{name}"]')
        group.wait_visible(timeout=WIDGET_TIMEOUT)
        return group

    def _choose_attachment_path(self, group: str, title: str, path: Path) -> None:
        """Use the real file picker, then verify its result in the attachment list.

        Nuke can expose a Qt picker even on macOS. Prefer its path field when
        present; use Go to Folder only for a native macOS picker.
        """
        self._attachment_group(group).descendant("button[name='Add...']").press()
        picker = self.app.locator(f'dialog[name="{title}"], window[name="{title}"], sheet')
        picker.wait_visible(timeout=WIDGET_TIMEOUT)
        field = picker.descendant(
            "text_field[name^='File name'], "
            "text_field[name^='Directory'], text_field[name^='Folder']"
        )
        if field.exists() or sys.platform != "darwin":
            field.wait_visible(timeout=WIDGET_TIMEOUT)
            field.set_value(str(path))
        else:
            sim = xa11y.input_sim()
            sheets = self.app.locator("sheet")
            sheet_count = sheets.count()
            sim.chord("g", held=["Meta", "Shift"])
            # Wait for the navigation sheet and its keyboard focus. Choosing
            # the first text field could type into the outer picker's Search.
            sheets.wait_until(
                lambda _: sheets.count() > sheet_count
                and any(field.focused for field in self.app.locator("sheet text_field").elements()),
                timeout=WIDGET_TIMEOUT,
            )
            sim.chord("a", held=["Meta"])
            sim.type_text(str(path))
            sim.press("Enter")
            # The navigation sheet closes before the picker can accept.
            sheets.wait_until(lambda _: sheets.count() == sheet_count, timeout=WIDGET_TIMEOUT)
        accept_selector = "button[name='Open'], button[name='Choose'], button[name='Select Folder']"
        # The Windows native picker also exposes an Open button inside the
        # file-type combo. Invoke the dialog's action button, not that dropdown.
        accept = (
            picker.child(accept_selector)
            if sys.platform == "win32"
            else picker.descendant(accept_selector)
        )
        accept.wait_enabled(timeout=WIDGET_TIMEOUT)
        accept.press()
        picker.wait_hidden(timeout=WIDGET_TIMEOUT)
        self._wait_attachment_path(group, path, present=True)

    def _wait_attachment_path(self, group: str, path: Path, *, present: bool) -> None:
        self._attachment_group(group).wait_until(
            lambda element: element is not None and ((str(path) in element.dump()) == present),
            timeout=WIDGET_TIMEOUT,
        )

    def add_input_file(self, path: Path) -> None:
        self._choose_attachment_path(
            "Attach input files", "Select input files to attach to your job", path
        )

    def add_output_directory(self, path: Path) -> None:
        self._choose_attachment_path(
            "Specify output directories", "Select an output directory of your job", path
        )

    def remove_input_file(self, path: Path) -> None:
        group = self._attachment_group("Attach input files")
        self._wait_attachment_path("Attach input files", path, present=True)
        # Qt lists expose rows or items depending on the platform. Click the
        # path's text/row rather than assuming a platform-specific select action.
        candidates = group.descendant("list_item, table_row, static_text").elements()
        target = next((item for item in candidates if item.name == str(path)), None)
        assert target is not None, f"Cannot select attachment {path}\n{group.element().dump()}"
        xa11y.input_sim().click(target)
        group.descendant("static_text[name$='1 selected']").wait_visible(timeout=WIDGET_TIMEOUT)
        group.descendant("button[name='Remove selected']").press()
        self._wait_attachment_path("Attach input files", path, present=False)

    def dump_tree(self) -> str:
        self._front()
        try:
            return self.window.element().dump()
        except Exception as exc:
            return f"<tree dump failed: {exc!r}>"
