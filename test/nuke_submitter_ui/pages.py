# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Page object for the Nuke render submitter dialog.

Extends the shared-dialog page object from ``deadline-cloud-test-fixtures``
with accessors for the Nuke ``SceneSettingsWidget`` (Job-specific settings
tab).

Selector notes (macOS AX ground truth from the 2026-07-20 spike):

* The dialog window title is ``Submit Rendering to AWS Deadline Cloud``
  (Nuke overrides the shared default).
* The submitter is a ``Qt.Tool`` window: macOS REMOVES it from the AX
  tree whenever Nuke is not the frontmost application (e.g. someone
  touches another window mid-test). Every accessor therefore calls the
  ``ensure_frontmost`` hook first, making tests self-healing after brief
  focus steals. Synthetic input still requires Nuke frontmost at the
  moment it fires — don't use the machine while these tests run.
* Most scene-settings widgets are ANONYMOUS in the accessibility tree
  (no ``setAccessibleName``/``setBuddy`` in ``scene_settings_tab.py``),
  and Qt tab pages drop out of the tree when inactive, so accessors are
  positional (``nth``, 1-BASED) scoped to the active Job-specific tab.
  Positions follow the layout order of ``scene_settings_tab.py``;
  revisit after UI changes there (an accessible-naming pass will make
  these robust).
* QComboBox accessible names mirror their current text, so combos are
  addressed positionally, never by name. Popup items expose no working
  AX press/select action (verified: rows accept only ``focus``; pressing
  their text is a no-op) — selection uses ``show_menu`` plus PHYSICAL
  input: a real click at the row's screen bounds, falling back to arrow
  keys + Enter.
* QSpinBox AX increment/decrement jump by 10% OF THE RANGE (Qt maps them
  to PageUp/PageDown semantics; chunk size 1-150 steps by 15), so exact
  values are typed instead: AX ``focus`` (verifiable), clear the line
  edit with End+Backspaces, type digits, commit with Tab — wrapped in a
  read-back-verify retry loop.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import xa11y
from deadline_test_fixtures.xa11y import SharedSubmitterDialog
from deadline_test_fixtures.xa11y.controls import (
    TAB_JOB_SPECIFIC,
    TAB_SHARED,
    set_checkbox,
    set_text_field,
    switch_to_tab,
)

DIALOG_TITLE = "Submit Rendering to AWS Deadline Cloud"

WIDGET_TIMEOUT = 30.0
FARM_RESOLVE_TIMEOUT = 30.0
EXPORT_TIMEOUT = 60.0
POPUP_TIMEOUT = 10.0

# Positional indexes on the ACTIVE Job-specific tab, in document order.
# NOTE: xa11y Locator.nth is 1-BASED.
_COMBO_WRITE_NODES = 1
_COMBO_VIEWS = 2
_SPIN_CHUNK_SIZE = 1
_SPIN_TARGET_CHUNK_DURATION = 2
_TEXT_FRAME_RANGE = 1

# Accessible names that exist today (Qt auto-derived from label/text).
CHECKBOX_OVERRIDE_FRAME_RANGE = "Override frame range"
CHECKBOX_PROXY_MODE = "Use proxy mode"
CHECKBOX_CONTINUE_ON_ERROR = "Continue on error"
CHECKBOX_USE_TIMEOUTS = "Use timeouts"
CHECKBOX_INCLUDE_GIZMOS = "Include gizmos in job bundle"
# The Description field's AX name is inherited from its QGroupBox — an
# artifact, not a real name (see spike anonymous-widget list).
_DESCRIPTION_FIELD_AX_NAME = "Job Properties"

WRITE_NODES_ALL = "All write nodes"


class NukeSubmitterDialog(SharedSubmitterDialog):
    """Drives the Nuke submitter dialog through the accessibility tree.

    Rooted at the dialog WINDOW locator so selectors cannot leak into
    Nuke's main window; keeps the app handle for popups (message boxes,
    combo popups) that surface outside the dialog window.
    """

    def __init__(
        self,
        app: xa11y.App,
        window: xa11y.Locator,
        ensure_frontmost: Optional[Callable[[], object]] = None,
    ) -> None:
        super().__init__(window)
        self.app = app
        self.window = window
        self._ensure_frontmost = ensure_frontmost or (lambda: None)

    @classmethod
    def wait_for(
        cls,
        app: xa11y.App,
        timeout: float = WIDGET_TIMEOUT,
        ensure_frontmost: Optional[Callable[[], object]] = None,
    ) -> "NukeSubmitterDialog":
        if ensure_frontmost is not None:
            ensure_frontmost()
        window = app.locator(f'window[name="{DIALOG_TITLE}"]')
        window.wait_visible(timeout=timeout)
        return cls(app, window, ensure_frontmost)

    def _front(self) -> None:
        """Re-assert Nuke frontmost; the Qt.Tool window otherwise drops
        out of the AX tree entirely."""
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

    def wait_farm_resolved(
        self, farm_name: str = "TestFarm", timeout: float = FARM_RESOLVE_TIMEOUT
    ) -> None:
        """Wait until the farm display name appears in the dialog tree,
        i.e. ListFarms against the (mock) backend succeeded."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._front()
            try:
                if farm_name in self.window.element().dump():
                    return
            except Exception:
                # The window drops out of the AX tree while Nuke is
                # backgrounded; _front() re-asserts it next iteration.
                pass
            time.sleep(0.5)
        raise TimeoutError(
            f"Farm {farm_name!r} did not resolve within {timeout}s\n{self.dump_tree()}"
        )

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

    def selected_write_node(self, retries: int = 10) -> str:
        """Current write-node selection (the combo's AX name mirrors it).

        Retries with re-activation: the whole window vanishes from the AX
        tree while Nuke is momentarily backgrounded.
        """
        last_error: Exception | None = None
        for _ in range(retries):
            self._front()
            try:
                return self.write_nodes_combo().element().name or ""
            except Exception as exc:
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
                for row in self.app.locator("table_row").elements():
                    label = next(
                        (c.name or "" for c in row.children() if (c.name or "").strip()), ""
                    )
                    if label and label not in seen:
                        seen.add(label)
                        rows.append((row, label))
            except Exception:
                rows = []
            if rows:
                return rows
            time.sleep(0.5)
        return []

    def select_write_node(self, label: str) -> None:
        """Select *label* in the write-node combo.

        Popup rows expose no functional AX activation action, so this uses
        physical input: click at the target row's screen bounds; if the
        readback disagrees, retry with arrow keys + Enter.
        """
        if self.selected_write_node() == label:
            return
        sim = xa11y.input_sim()

        # Strategy 1: physical click on the popup row.
        self._front()
        self.write_nodes_combo().show_menu()
        rows = self._popup_rows()
        target = next((row for row, name in rows if name == label), None)
        if target is None:
            sim.press("Escape")
            raise AssertionError(
                f"Write node {label!r} not in popup: {[name for _, name in rows]}\n"
                f"{self.dump_tree()}"
            )
        sim.click(target)  # InputSim accepts an Element: clicks centre bounds
        time.sleep(1.0)
        if self.selected_write_node() == label:
            return

        # Strategy 2: keyboard navigation from the top of the popup.
        self._front()
        self.write_nodes_combo().show_menu()
        rows = self._popup_rows()
        ordered = [name for _, name in rows]
        if label not in ordered:
            sim.press("Escape")
            raise AssertionError(f"Write node {label!r} vanished from popup: {ordered}")
        current = self.selected_write_node()
        steps = ordered.index(label) - (ordered.index(current) if current in ordered else 0)
        key = "ArrowDown" if steps >= 0 else "ArrowUp"
        self._front()
        for _ in range(abs(steps)):
            sim.press(key)
            time.sleep(0.2)
        sim.press("Enter")
        time.sleep(1.0)
        selected = self.selected_write_node()
        if selected != label:
            raise AssertionError(
                f"Write-node selection failed: wanted {label!r}, combo shows {selected!r}"
            )

    def frame_range_field(self) -> xa11y.Locator:
        self._front()
        field = self.window.descendant("text_field").nth(_TEXT_FRAME_RANGE)
        field.wait_visible(timeout=WIDGET_TIMEOUT)
        return field

    def set_override_frame_range(self, enabled: bool) -> None:
        self._front()
        set_checkbox(self.window, CHECKBOX_OVERRIDE_FRAME_RANGE, enabled, timeout=WIDGET_TIMEOUT)

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

    def _spin(self, index: int) -> xa11y.Locator:
        self._front()
        spin = self.window.descendant("spin_button").nth(index)
        spin.wait_visible(timeout=WIDGET_TIMEOUT)
        return spin

    def _set_spin(self, index: int, target: int, attempts: int = 5) -> None:
        """Type *target* into the spin box at *index* (see module notes:
        AX increment/decrement step by 10% of range, so typing it is).

        Keyboard events go to the KEY window, and AX ``focus()`` does not
        make a Qt.Tool window key — a real click does. So: click into the
        line edit (left of the arrow buttons), double-click to select the
        number, type the replacement, commit with Tab, read back; retry.
        """
        sim = xa11y.input_sim()
        last_seen = "<never read>"
        for _ in range(attempts):
            self._front()
            try:
                element = self._spin(index).element()
                bounds = element.bounds
                text_spot = (int(bounds.x + bounds.width * 0.3), int(bounds.y + bounds.height / 2))
                sim.click(text_spot)
                time.sleep(0.3)
                sim.double_click(text_spot)  # select the numeric content
                time.sleep(0.2)
                sim.type_text(str(target))
                time.sleep(0.2)
                sim.press("Tab")
                time.sleep(0.5)
                self._front()
                last_seen = str(self._spin(index).element().value or "")
                if last_seen == str(target):
                    return
            except Exception as exc:
                last_seen = f"<error: {exc!r}>"
                time.sleep(1.0)
        raise AssertionError(f"Spin button {index} did not reach {target}; last: {last_seen}")

    def set_chunk_size(self, chunk_size: int) -> None:
        self._set_spin(_SPIN_CHUNK_SIZE, chunk_size)

    def chunk_size(self) -> int:
        return int(self._spin(_SPIN_CHUNK_SIZE).element().value or "0")

    def set_target_chunk_duration(self, seconds: int) -> None:
        self._set_spin(_SPIN_TARGET_CHUNK_DURATION, seconds)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def export_bundle(self, timeout: float = EXPORT_TIMEOUT) -> None:
        """Press 'Export bundle' and dismiss the confirmation message box.

        No file dialog is involved: the bundle is written to the configured
        ``job_history_dir``. The confirmation QMessageBox is a separate
        window, hence the app-scoped OK lookup.
        """
        self._front()
        self.button("Export bundle").press()
        ok = self.app.locator('button[name="OK"]')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._front()
            try:
                if ok.exists():
                    ok.press()
                    return
            except Exception:
                # The message box may be mid-animation or the tree mid-churn
                # after the export; poll again until the deadline.
                pass
            time.sleep(0.5)
        raise TimeoutError(f"Export confirmation did not appear in {timeout}s\n{self.dump_tree()}")

    def dump_tree(self) -> str:
        self._front()
        try:
            return self.window.element().dump()
        except Exception as exc:
            return f"<tree dump failed: {exc!r}>"
