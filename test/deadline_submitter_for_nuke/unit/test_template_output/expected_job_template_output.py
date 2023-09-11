# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

EXPECTED_NUKE_JOB_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "TestName",
    "parameterDefinitions": [
        {
            "name": "NukeScriptFile",
            "type": "PATH",
            "objectType": "FILE",
            "dataFlow": "IN",
            "userInterface": {
                "control": "CHOOSE_INPUT_FILE",
                "label": "Nuke Script File",
                "fileFilters": [
                    {"label": "Nuke Script Files", "patterns": ["*.nk"]},
                    {"label": "All Files", "patterns": ["*"]},
                ],
            },
            "description": "The Nuke script file to render.",
        },
        {
            "name": "Frames",
            "type": "STRING",
            "description": "The frames to render. E.g. 1-3,8,11-15",
            "minLength": 1,
        },
        {
            "name": "WriteNode",
            "type": "STRING",
            "userInterface": {"control": "DROPDOWN_LIST", "label": "Write Node"},
            "description": "Which write node to render ('All Write Nodes' for all of them)",
            "default": "All Write Nodes",
            "allowedValues": ["All Write Nodes"],
        },
        {
            "name": "View",
            "type": "STRING",
            "userInterface": {"control": "DROPDOWN_LIST"},
            "description": "Which view to render ('All Views' for all of them)",
            "default": "All Views",
            "allowedValues": ["All Views"],
        },
        {
            "name": "ProxyMode",
            "type": "STRING",
            "userInterface": {"control": "CHECK_BOX", "label": "Proxy Mode"},
            "description": "Render in Proxy Mode.",
            "default": "false",
            "allowedValues": ["true", "false"],
        },
        {
            "name": "ContinueOnError",
            "type": "STRING",
            "userInterface": {"control": "CHECK_BOX", "label": "Continue On Error"},
            "description": "Continue processing when errors occur.",
            "default": "false",
            "allowedValues": ["true", "false"],
        },
        {
            "name": "NukeVersion",
            "type": "STRING",
            "userInterface": {"control": "LINE_EDIT", "label": "Nuke Version"},
            "description": "The version of Nuke.",
        },
        {
            "name": "RezPackages",
            "type": "STRING",
            "userInterface": {"control": "LINE_EDIT", "label": "Rez Packages"},
            "description": "A space-separated list of Rez packages to install",
            "default": "nuke-13 deadline_cloud_for_nuke",
        },
    ],
    "jobEnvironments": [
        {
            "name": "Rez",
            "description": "Initializes and destroys the Rez environment for the job.",
            "script": {
                "actions": {
                    "onEnter": {"command": "{{ Env.File.Enter }}"},
                    "onExit": {"command": "{{ Env.File.Exit }}"},
                },
                "embeddedFiles": [
                    {
                        "name": "Enter",
                        "filename": "rez-enter.sh",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/bin/env bash\n\nset -euo pipefail\n\nif [ ! -z "{{Param.RezPackages}}" ]; then\n    echo "Rez Package List:"\n    echo "   {{Param.RezPackages}}"\n\n    # Create the environment\n    /usr/local/bin/deadline-rez init \\\n        -d "{{Session.WorkingDirectory}}" \\\n        {{Param.RezPackages}}\n\n    # Capture the environment\'s vars\n    {{Env.File.InitialVars}}\n    . /usr/local/bin/deadline-rez activate \\\n        -d "{{Session.WorkingDirectory}}"\n    {{Env.File.CaptureVars}}\nelse\n    echo "No Rez Packages, skipping environment creation."\nfi\n',
                    },
                    {
                        "name": "Exit",
                        "filename": "rez-exit.sh",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/bin/env bash\n\nset -euo pipefail\n\nif [ ! -z "{{Param.RezPackages}}" ]; then\n    echo "Rez Package List:"\n    echo "   {{Param.RezPackages}}"\n\n    /usr/local/bin/deadline-rez destroy \\\n        -d "{{ Session.WorkingDirectory }}"\nelse\n    echo "No Rez Packages, skipping environment teardown."\nfi\n',
                    },
                    {
                        "name": "InitialVars",
                        "filename": "initial-vars.sh",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/usr/bin/env python3\nimport os, json\nenvfile = "{{Session.WorkingDirectory}}/.envInitial"\nwith open(envfile, "w", encoding="utf8") as f:\n    json.dump(dict(os.environ), f)\n',
                    },
                    {
                        "name": "CaptureVars",
                        "filename": "capture-vars.sh",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/usr/bin/env python3\nimport os, json, sys\nenvfile = "{{Session.WorkingDirectory}}/.envInitial"\nif os.path.isfile(envfile):\n    with open(envfile, "r", encoding="utf8") as f:\n        before = json.load(f)\nelse:\n    print("No initial environment found, must run Env.File.CaptureVars script first")\n    sys.exit(1)\nafter = dict(os.environ)\n\nput = {k: v for k, v in after.items() if v != before.get(k)}\ndelete = {k for k in before if k not in after}\n\nfor k, v in put.items():\n    print(f"updating {k}={v}")\n    print(f"openjd_env: {k}={v}")\nfor k in delete:\n    print(f"openjd_unset_env: {k}")\n',
                    },
                ],
            },
        }
    ],
    "steps": [
        {
            "name": "Render",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"}
                ]
            },
            "stepEnvironments": [
                {
                    "name": "Nuke",
                    "description": "Runs Nuke in the background with a script file loaded.",
                    "script": {
                        "embeddedFiles": [
                            {
                                "name": "initData",
                                "filename": "init-data.yaml",
                                "type": "TEXT",
                                "data": "continue_on_error: {{Param.ContinueOnError}}\nproxy: {{Param.ProxyMode}}\nscript_file: '{{Param.NukeScriptFile}}'\nversion: '{{Param.NukeVersion}}'\nwrite_nodes:\n- '{{Param.WriteNode}}'\nviews:\n- '{{Param.View}}'\n",
                            }
                        ],
                        "actions": {
                            "onEnter": {
                                "command": "NukeAdaptor",
                                "args": [
                                    "daemon",
                                    "start",
                                    "--path-mapping-rules",
                                    "file://{{Session.PathMappingRulesFile}}",
                                    "--connection-file",
                                    "{{Session.WorkingDirectory}}/connection.json",
                                    "--init-data",
                                    "file://{{ Env.File.initData }}",
                                ],
                                "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                            },
                            "onExit": {
                                "command": "NukeAdaptor",
                                "args": [
                                    "daemon",
                                    "stop",
                                    "--connection-file",
                                    "{{ Session.WorkingDirectory }}/connection.json",
                                ],
                                "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                            },
                        },
                    },
                }
            ],
            "script": {
                "embeddedFiles": [
                    {
                        "name": "runData",
                        "filename": "run-data.yaml",
                        "type": "TEXT",
                        "data": "frame: {{Task.Param.Frame}}",
                    }
                ],
                "actions": {
                    "onRun": {
                        "command": "NukeAdaptor",
                        "args": [
                            "daemon",
                            "run",
                            "--connection-file",
                            "{{Session.WorkingDirectory}}/connection.json",
                            "--run-data",
                            "file://{{ Task.File.runData }}",
                        ],
                        "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                    }
                },
            },
        }
    ],
}
