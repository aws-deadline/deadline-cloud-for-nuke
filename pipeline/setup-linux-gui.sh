#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Run as root in the pinned Rocky 9 CI container. No Nuke or license is needed.
set -euo pipefail

dnf install -y epel-release dnf-plugins-core
dnf config-manager --set-enabled crb
dnf install -y \
    git procps-ng util-linux python3.11 python3.11-pip \
    xorg-x11-server-Xvfb xorg-x11-xauth xorg-x11-utils \
    dbus-daemon dbus-tools at-spi2-core openbox ImageMagick \
    mesa-dri-drivers mesa-libGL mesa-libGLU libglvnd-opengl libglvnd-glx \
    libXrender libXrandr libXi libXcursor libXinerama libxkbcommon-x11 \
    xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm xcb-util-cursor \
    alsa-lib numactl-libs fontconfig dejavu-sans-fonts \
    gtk3 python3-gobject-base

python3.11 -m pip install "hatch==1.18.0" "awscli==1.46.2"

# Official AWS package, downloaded and hashed on 2026-11-02.
# Update URL/version and digest together.
plugin="$RUNNER_TEMP/ssm-plugin.rpm"
curl --fail --silent --show-error --location \
    https://s3.amazonaws.com/session-manager-downloads/plugin/1.2.835.0/linux_64bit/session-manager-plugin.rpm \
    --output "$plugin"
printf '%s  %s\n' \
    1dcade7435709cce65a05eba87f2a96e8aaf7318c78a21d7a2ae648ce2f2ad81 "$plugin" |
    sha256sum --check -
dnf install -y "$plugin"
rm -f "$plugin"
