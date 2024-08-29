# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


from deadline.nuke_submitter.deadline_submitter_for_nuke import (
    _add_gizmo_dir_to_job_template,
    _remove_gizmo_dir_from_job_template,
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

    _add_gizmo_dir_to_job_template(job_template)

    expected_environment = {
        "name": "Add Gizmos to NUKE_PATH",
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
    assert len(job_template["jobEnvironments"]) == 1
    assert job_template["jobEnvironments"][0] == expected_environment


def test_remove_gizmo_dir_from_job_template():
    job_template = {"parameterDefinitions": [{"name": "GizmoDir", "type": "PATH"}]}

    _remove_gizmo_dir_from_job_template(job_template)
    expected_job_template: dict = {"parameterDefinitions": []}

    assert len(job_template["parameterDefinitions"]) == 0
    assert job_template == expected_job_template
