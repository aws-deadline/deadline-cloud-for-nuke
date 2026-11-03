#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Verify AT-SPI discovery, window activation, and XTest without licensing Nuke."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import time

import xa11y

# Use Rocky's system Python for its distro-provided PyGObject/GTK3 bindings.
FIXTURE = """
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import pathlib, sys
window = Gtk.Window(title="Nuke CI accessibility smoke")
button = Gtk.Button(label="Verify XTest")
button.connect("clicked", lambda *_: pathlib.Path(sys.argv[1]).write_text("clicked"))
window.add(button)
window.set_default_size(400, 200)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
"""

QT_FIXTURE = """
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import QTimer, qVersion
from PySide6.QtGui import QAccessible
from PySide6.QtDBus import QDBusConnection, QDBusInterface
import pathlib, sys
app = QApplication([])
bus = QDBusConnection.sessionBus()
print("Qt version:", qVersion(), "session bus connected:", bus.isConnected(), flush=True)
interface = QDBusInterface("org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus", bus)
print("Accessibility bus:", interface.call("GetAddress").arguments(), flush=True)
window = QWidget()
window.setWindowTitle("Nuke CI accessibility smoke")
layout = QVBoxLayout(window)
button = QPushButton("Verify XTest")
layout.addWidget(button)
button.clicked.connect(lambda: pathlib.Path(sys.argv[1]).write_text("clicked"))
window.resize(400, 200)
window.show()
QTimer.singleShot(1000, lambda: print("Qt accessibility active:", QAccessible.isActive(),
                                    flush=True))
app.exec()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qt-python", type=Path, help="Probe this bundled Qt Python")
    parser.add_argument("--qt-root", type=Path, help="Nuke installation containing Qt")
    args = parser.parse_args()
    if args.qt_root and not args.qt_python:
        parser.error("--qt-root requires --qt-python")
    environment = os.environ.copy()
    if args.qt_root:
        # Use the application's own bindings and platform plugin. A system Qt
        # replacement could pass this check without testing Nuke's Qt build.
        root = args.qt_root.resolve()
        for variable, directory in (
            ("LD_LIBRARY_PATH", root),
            ("PYTHONPATH", root / "pythonextensions" / "site-packages"),
        ):
            environment[variable] = str(directory) + (
                os.pathsep + environment[variable] if environment.get(variable) else ""
            )
        environment["QT_PLUGIN_PATH"] = str(root / "qtplugins")
    prefix = "nuke-qt-smoke" if args.qt_python else "smoke"
    with tempfile.TemporaryDirectory() as temporary:
        clicked = Path(temporary) / "clicked"
        artifacts = Path(os.environ["GUI_ARTIFACT_DIR"])
        with (artifacts / f"{prefix}.log").open("w") as log:
            process = subprocess.Popen(
                [
                    str(args.qt_python or "/usr/bin/python3"),
                    "-c",
                    QT_FIXTURE if args.qt_python else FIXTURE,
                    str(clicked),
                ],
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                try:
                    app = xa11y.App.by_pid(process.pid, timeout=30)
                except xa11y.SelectorNotMatchedError as error:
                    if args.qt_python:
                        raise RuntimeError(
                            "Nuke's bundled Qt did not register with AT-SPI. "
                            "Check nuke-qt-smoke.log for startup errors and Qt accessibility "
                            "status. A Qt build with the Linux AT-SPI bridge is required; "
                            "the licensed GUI suite cannot run without it."
                        ) from error
                    raise
                button = app.locator("button[name='Verify XTest']")
                button.wait_visible(timeout=30)
                if not args.qt_python:
                    app.windows()[0].activate()
                    if xa11y.App.foreground(timeout=10).pid != process.pid:
                        raise RuntimeError("The smoke window did not acquire foreground focus")
                # A synthetic click proves the XTest path, unlike AT-SPI press().
                xa11y.input_sim().click(button.element())
                deadline = time.monotonic() + 10
                while not clicked.exists() and time.monotonic() < deadline:
                    time.sleep(0.1)
                if not clicked.exists():
                    raise RuntimeError("The synthetic click did not reach the smoke button")
                (artifacts / f"{prefix}-accessibility.txt").write_text(
                    app.dump(max_depth=5), encoding="utf-8"
                )
                print(
                    "Bundled Qt smoke passed: AT-SPI and XTest"
                    if args.qt_python
                    else "Linux desktop smoke passed: AT-SPI, foreground focus, and XTest"
                )
            finally:
                # Capture even discovery failures while the fixture is still open.
                try:
                    xa11y.screenshot().save_png(str(artifacts / f"{prefix}-screen.png"))
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()
