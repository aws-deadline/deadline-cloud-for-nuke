#!/bin/bash
set -xeuo pipefail

python depsBundle.py

rm -f dependency_bundle/deadline_submitter_for_nuke-deps-windows.zip
rm -f dependency_bundle/deadline_submitter_for_nuke-deps-linux.zip
rm -f dependency_bundle/deadline_submitter_for_nuke-deps-macos.zip

cp dependency_bundle/deadline_submitter_for_nuke-deps.zip dependency_bundle/deadline_submitter_for_nuke-deps-windows.zip
cp dependency_bundle/deadline_submitter_for_nuke-deps.zip dependency_bundle/deadline_submitter_for_nuke-deps-linux.zip
cp dependency_bundle/deadline_submitter_for_nuke-deps.zip dependency_bundle/deadline_submitter_for_nuke-deps-macos.zip
