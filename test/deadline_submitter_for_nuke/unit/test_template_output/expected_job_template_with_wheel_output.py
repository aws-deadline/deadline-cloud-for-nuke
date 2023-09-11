# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

EXPECTED_NUKE_JOB_TEMPLATE_WITH_WHEEL = {
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
        {
            "name": "AdaptorWheels",
            "type": "PATH",
            "objectType": "DIRECTORY",
            "dataFlow": "IN",
            "description": "A directory that contains wheels for openjd, deadline, and the overridden adaptor.",
            "default": "/test/directory/deadline-cloud-for-nuke/wheels",
        },
        {
            "name": "OverrideAdaptorName",
            "type": "STRING",
            "description": "The name of the adaptor to override, for example NukeAdaptor or MayaAdaptor.",
            "default": "NukeAdaptor",
        },
    ],
    "jobEnvironments": [
        {
            "name": "OverrideAdaptor",
            "description": "Replaces the default Adaptor in the environment's PATH with one from the packages in the AdaptorWheels attached directory.\n",
            "script": {
                "actions": {"onEnter": {"command": "{{Env.File.Enter}}"}},
                "embeddedFiles": [
                    {
                        "name": "Enter",
                        "filename": "override-adaptor-enter.sh",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/bin/env bash\n\nset -euo pipefail\n\necho "The adaptor wheels that are attached to the job:"\nls {{Param.AdaptorWheels}}/\necho ""\n\n# Create a venv and activate it in this environment\necho "Creating Python venv for the {{Param.OverrideAdaptor}} command"\n/usr/local/bin/python3 -m venv \'{{Session.WorkingDirectory}}/venv\'\n{{Env.File.InitialVars}}\n. \'{{Session.WorkingDirectory}}/venv/bin/activate\'\n{{Env.File.CaptureVars}}\necho ""\n\necho "Installing adaptor into the venv"\npip install {{Param.AdaptorWheels}}/openjd*.whl\npip install {{Param.AdaptorWheels}}/deadline*.whl\necho ""\n\nif [ ! -f \'{{Session.WorkingDirectory}}/venv/bin/{{Param.OverrideAdaptorName}}\' ]; then\n  echo "The Override Adaptor {{Param.OverrideAdaptorName}} was not installed as expected."\n  exit 1\nfi\n',
                    },
                    {
                        "name": "InitialVars",
                        "filename": "initial-vars",
                        "type": "TEXT",
                        "runnable": True,
                        "data": '#!/usr/bin/env python3\nimport os, json\nenvfile = "{{Session.WorkingDirectory}}/.envInitial"\nwith open(envfile, "w", encoding="utf8") as f:\n    json.dump(dict(os.environ), f)\n',
                    },
                    {
                        "name": "CaptureVars",
                        "filename": "capture-vars",
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
