# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


from deadline.nuke_submitter.deadline_submitter_for_nuke import (
    _add_ocio_path_to_job_template,
    _remove_ocio_path_from_job_template,
)


def test_add__dir_to_job_template():
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

    _add_ocio_path_to_job_template(job_template)

    expected_environment = {
        "name": "Add OCIO Path to Environment Variable",
        "variables": {"OCIO": "{{Param.OCIOConfigPath}}"},
    }

    assert len(job_template["jobEnvironments"]) == 1
    assert job_template["jobEnvironments"][0] == expected_environment


def test_remove_ocio_path_from_job_template():
    job_template = {"parameterDefinitions": [{"name": "OCIOConfigPath", "type": "PATH"}]}

    _remove_ocio_path_from_job_template(job_template)
    expected_job_template: dict = {"parameterDefinitions": []}

    assert len(job_template["parameterDefinitions"]) == 0
    assert job_template == expected_job_template
