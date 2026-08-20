# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Backend scenario for conda_queue_environment.

The shared mock serves a queue with no queue environments, so the fields under
test would not exist. Template is the console-equivalent Conda queue
environment from deadline-cloud-samples; only its parameter definitions
matter here, since these tests export a bundle rather than render.
"""

from deadline_test_fixtures.deadline_mock import MockDeadlineScenario

QUEUE_ENVIRONMENT_NAME = "Conda"

_CONDA_QUEUE_ENVIRONMENT_TEMPLATE = """
specificationVersion: 'environment-2023-09'
parameterDefinitions:
- name: CondaPackages
  type: STRING
  description: >
    This is a space-separated list of Conda package match specifications to
    install for the job. E.g. "blender=4.3" for a job that renders frames in
    Blender 4.3.
  default: ""
  userInterface:
    control: LINE_EDIT
    label: Conda Packages
- name: CondaChannels
  type: STRING
  description: >
    This is a space-separated list of Conda channels from which to install
    packages.
  default: "deadline-cloud"
  userInterface:
    control: LINE_EDIT
    label: Conda Channels
environment:
  name: Conda
  script:
    actions:
      onEnter:
        command: "conda-queue-env-enter"
        args:
        - "{{Session.WorkingDirectory}}/.env"
        - "--packages"
        - "{{Param.CondaPackages}}"
        - "--channels"
        - "{{Param.CondaChannels}}"
      onExit:
        command: "conda-queue-env-exit"
"""


def scenario() -> MockDeadlineScenario:
    return MockDeadlineScenario(
        queue_environments=(
            {
                "queueEnvironmentId": "queueenv-conda",
                "name": QUEUE_ENVIRONMENT_NAME,
                "priority": 1,
                "templateType": "YAML",
                "template": _CONDA_QUEUE_ENVIRONMENT_TEMPLATE,
            },
        ),
    )
