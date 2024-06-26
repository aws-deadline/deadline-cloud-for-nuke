# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pathlib

from deadline.nuke_submitter.deadline_submitter_for_nuke import (
    _add_gizmo_dir_to_job_template,
)


def test_add_gizmo_dir_to_job_template():
    job_template = {
        "parameterDefinitions": [],
        "steps": [
            {
                "name": "Render",
                "stepEnvironments": [
                    {
                        "name": "OtherEnv",
                    },
                ],
            }
        ],
    }

    relative_gizmo_path = pathlib.Path("gizmos")
    _add_gizmo_dir_to_job_template(job_template, relative_gizmo_path)

    assert len(job_template["parameterDefinitions"]) == 1
    expected_definition = {
        "name": "GizmoDir",
        "type": "PATH",
        "description": "The directory containing Nuke Gizmo files used by this job.",
        "default": "gizmos",
        "objectType": "DIRECTORY",
        "dataFlow": "IN",
        "userInterface": {"control": "CHOOSE_DIRECTORY", "label": "Gizmo Directory"},
    }
    assert job_template["parameterDefinitions"][0] == expected_definition

    expected_environment = {
        "name": "AddGizmoPathsToNukePath",
        "script": {
            "actions": {"onEnter": {"command": "{{Env.File.Enter}}"}},
            "embeddedFiles": [
                {
                    "name": "Enter",
                    "type": "TEXT",
                    "runnable": True,
                    "data": """#!/bin/bash
echo 'openjd_env: NUKE_PATH=$NUKE_PATH:{{Param.GizmoDir}}'
""",
                }
            ],
        },
    }
    assert len(job_template["steps"][0]["stepEnvironments"]) == 2
    assert job_template["steps"][0]["stepEnvironments"][0] == expected_environment
