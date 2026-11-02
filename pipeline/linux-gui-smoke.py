#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Verify AT-SPI discovery, window activation, and XTest without licensing Nuke."""

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


def main():
    with tempfile.TemporaryDirectory() as temporary:
        clicked = Path(temporary) / "clicked"
        artifacts = Path(os.environ["GUI_ARTIFACT_DIR"])
        with (artifacts / "smoke.log").open("w") as log:
            process = subprocess.Popen(
                ["/usr/bin/python3", "-c", FIXTURE, str(clicked)],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                app = xa11y.App.by_pid(process.pid, timeout=30)
                button = app.locator("button[name='Verify XTest']")
                button.wait_visible(timeout=30)
                app.windows()[0].activate()
                if xa11y.App.foreground(timeout=10).pid != process.pid:
                    raise RuntimeError("The smoke window did not acquire foreground focus")
                # A synthetic click proves the XTest path, unlike AT-SPI press().
                xa11y.input_sim().click(button.element())
                deadline = time.monotonic() + 10
                while not clicked.exists() and time.monotonic() < deadline:
                    time.sleep(0.1)
                if not clicked.exists():
                    raise RuntimeError("The synthetic click did not reach the GTK button")
                (artifacts / "smoke-accessibility.txt").write_text(
                    app.dump(max_depth=5), encoding="utf-8"
                )
                xa11y.screenshot().save_png(str(artifacts / "smoke-screen.png"))
                print("Linux desktop smoke passed: AT-SPI, foreground focus, and XTest")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
