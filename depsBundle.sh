#!/bin/bash
set -xeuo pipefail

python depsBundle.py

rm -f dependency_bundle/deadline_cloud_for_nuke_submitter-deps-windows.zip
rm -f dependency_bundle/deadline_cloud_for_nuke_submitter-deps-linux.zip
rm -f dependency_bundle/deadline_cloud_for_nuke_submitter-deps-macos.zip

cp dependency_bundle/deadline_cloud_for_nuke_submitter-deps.zip dependency_bundle/deadline_cloud_for_nuke_submitter-deps-windows.zip
cp dependency_bundle/deadline_cloud_for_nuke_submitter-deps.zip dependency_bundle/deadline_cloud_for_nuke_submitter-deps-linux.zip
cp dependency_bundle/deadline_cloud_for_nuke_submitter-deps.zip dependency_bundle/deadline_cloud_for_nuke_submitter-deps-macos.zip
