#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Keep the display, window manager, AT-SPI, and command in ONE D-Bus session.
set -euo pipefail

if [[ "${1:-}" != "--in-session" ]]; then
    # Discard an inherited bus so a reused developer session cannot interfere.
    exec env -u DBUS_SESSION_BUS_ADDRESS dbus-run-session -- bash "$0" --in-session "$@"
fi
shift
[[ $# -gt 0 ]] || { echo "A GUI test command is required" >&2; exit 2; }

artifacts="${GUI_ARTIFACT_DIR:?GUI_ARTIFACT_DIR is required}"
mkdir -p "$artifacts"
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR=$(mktemp -d)
chmod 700 "$XDG_RUNTIME_DIR"
export XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=xcb
export QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
export NO_AT_BRIDGE=0 AT_SPI_CLIENT=true ACCESSIBILITY_ENABLED=1
export LIBGL_ALWAYS_SOFTWARE=1
unset WAYLAND_DISPLAY

pids=()
cleanup() {
    local result=$?
    local pid group name
    local nuke_groups=()
    trap - EXIT INT TERM
    # Capture the last screen while the server still exists, including on timeout.
    if [[ $result -ne 0 ]]; then
        timeout 10s import -window root "$artifacts/failure-screen.png" 2>/dev/null ||
            echo "Could not capture the final desktop screenshot" >&2
    fi
    # The suite gives Nuke its own process group. Kill survivors on cancellation too.
    if [[ -n "${NUKE_VERSION:-}" ]]; then
        name="Nuke${NUKE_VERSION%v*}"
        for pid in $(pgrep -x "$name" || true); do
            group=$(ps -o pgid= -p "$pid" | tr -d '[:space:]' || true)
            if [[ "$group" == "$pid" ]]; then
                nuke_groups+=("$group")
                kill -TERM -- "-$group" 2>/dev/null || true
            else
                kill -TERM "$pid" 2>/dev/null || true
            fi
        done
        sleep 1
        for group in "${nuke_groups[@]}"; do
            # Avoid a recycled leader ID now owned by an unrelated process.
            pid=$(ps -o comm= -p "$group" || true)
            if [[ -z "$pid" || "$pid" == "$name" ]]; then
                kill -KILL -- "-$group" 2>/dev/null || true
            fi
        done
        pkill -KILL -x "$name" 2>/dev/null || true
    fi
    for ((group=${#pids[@]}-1; group>=0; group--)); do
        pid="${pids[group]}"
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    rm -rf "$XDG_RUNTIME_DIR"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# X authority protects the UNIX socket; never enable TCP listening or -ac.
export DISPLAY=:99 XAUTHORITY="$XDG_RUNTIME_DIR/Xauthority"
touch "$XAUTHORITY"
chmod 600 "$XAUTHORITY"
xauth add "$DISPLAY" . "$(mcookie)"
Xvfb "$DISPLAY" -screen 0 1920x1080x24 -auth "$XAUTHORITY" \
    -nolisten tcp +extension XTEST > "$artifacts/xvfb.log" 2>&1 &
pids+=("$!")
display_ready=false
for _ in {1..30}; do
    kill -0 "${pids[0]}"
    if xdpyinfo -queryExtensions > "$artifacts/display.txt" 2>/dev/null; then
        display_ready=true
        break
    fi
    sleep 1
done
[[ "$display_ready" == true ]] || { echo "X display did not become ready" >&2; exit 1; }
grep -q XTEST "$artifacts/display.txt"
openbox > "$artifacts/window-manager.log" 2>&1 &
pids+=("$!")
wm_ready=false
for _ in {1..30}; do
    kill -0 "${pids[1]}"
    if xprop -root _NET_SUPPORTING_WM_CHECK | grep -q 'window id'; then
        wm_ready=true
        break
    fi
    sleep 1
done
[[ "$wm_ready" == true ]] || { echo "Window manager did not become ready" >&2; exit 1; }

/usr/libexec/at-spi-bus-launcher --launch-immediately > "$artifacts/accessibility.log" 2>&1 &
pids+=("$!")
bus_ready=false
for _ in {1..30}; do
    kill -0 "${pids[2]}"
    if dbus-send --session --print-reply --dest=org.a11y.Bus /org/a11y/bus \
        org.a11y.Bus.GetAddress > /dev/null 2>&1; then
        bus_ready=true
        break
    fi
    sleep 1
done
[[ "$bus_ready" == true ]] || { echo "AT-SPI bus did not become ready" >&2; exit 1; }
for property in IsEnabled ScreenReaderEnabled; do
    dbus-send --session --print-reply --dest=org.a11y.Bus /org/a11y/bus \
        org.freedesktop.DBus.Properties.Set \
        string:org.a11y.Status "string:$property" variant:boolean:true > /dev/null
done
/usr/libexec/at-spi2-registryd >> "$artifacts/accessibility.log" 2>&1 &
pids+=("$!")
export XA11Y_A11Y_READY=1

# timeout covers the command; traps collect artifacts and close the desktop on failure.
timeout --signal=TERM --kill-after=90s 40m "$@" &
pids+=("$!")
wait "${pids[4]}"
