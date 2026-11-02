#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Run one serial GUI command through the existing SSM license tunnel.

The private SSM log and session state stay in RUNNER_TEMP, outside GUI artifacts.
An always() workflow step can retry remote termination after cancellation.
"""

import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def session_id(log):
    if not log.exists():
        return None
    match = re.search(r"SessionId: ([A-Za-z0-9._-]+)", log.read_text(errors="replace"))
    return match.group(1) if match else None


def aws(arguments, environment):
    result = subprocess.run(
        ["aws", *arguments, "--profile", "license"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        # Do not expose role, region, bastion, or command values in exceptions.
        raise RuntimeError("License AWS command failed; check tunnel access/configuration")
    return result.stdout


def signal_group(process, signum):
    # Once wait/poll reaps the leader, a live owner of its ID is another process.
    # An existing group with surviving children retains its ID without a live leader.
    if process.returncode is not None:
        try:
            os.kill(process.pid, 0)
        except ProcessLookupError:
            pass
        except PermissionError:
            return
        else:
            return
    try:
        os.killpg(process.pid, signum)
    except (ProcessLookupError, PermissionError):
        pass


def stop_process(process):
    if process is None:
        return
    # SSM spawns session-manager-plugin; pytest can spawn additional helpers.
    signal_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        signal_group(process, signal.SIGKILL)
        process.wait()
    # A group leader may exit before its plugin does.
    signal_group(process, signal.SIGKILL)


def terminate_remote(log, environment):
    identifier = session_id(log)
    if identifier:
        aws(["ssm", "terminate-session", "--session-id", identifier], environment)


def cleanup_state(log, config, environment):
    terminate_remote(log, environment)
    # Retain state only when AWS termination fails and the always() step must retry.
    # Successful teardown must not try to terminate an already-ended session again.
    log.unlink(missing_ok=True)
    config.unlink(missing_ok=True)


def wait_for_tunnel(process, port, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("SSM tunnel exited before readiness")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError("SSM license tunnel did not become ready within 60 seconds")


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(arguments)
    temporary = Path(required("RUNNER_TEMP"))
    config = temporary / "nuke-license-config"
    log = temporary / "nuke-license-ssm.log"
    environment = {**os.environ, "AWS_CONFIG_FILE": str(config), "AWS_PAGER": ""}
    if args.cleanup:
        if config.exists():
            cleanup_state(log, config, environment)
        return 0
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a test command is required")
    region = required("AWS_REGION")
    role = required("LICENSE_ROLE_ARN")
    tag = required("BASTION_INSTANCE_TAG")
    if any("\n" in value or "\r" in value for value in (region, role)):
        raise ValueError("License configuration must be single-line")
    port = int(required("FOUNDRY_LICENSE_PORT"))
    if not 1024 <= port <= 65535:
        raise ValueError("License port must be between 1024 and 65535")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            raise RuntimeError("License port is already occupied")
    except OSError:
        pass

    config.write_text(
        f"[profile license]\nrole_arn = {role}\ncredential_source = Environment\nregion = {region}\n"
    )
    config.chmod(0o600)
    instances = json.loads(
        aws(
            [
                "ec2",
                "describe-instances",
                "--filters",
                f"Name=tag:Name,Values={tag}",
                "Name=instance-state-name,Values=running",
                "--query",
                "Reservations[].Instances[].InstanceId",
                "--output",
                "json",
            ],
            environment,
        )
    )
    if len(instances) != 1 or not re.fullmatch(r"i-[0-9a-f]{8}(?:[0-9a-f]{9})?", instances[0]):
        raise RuntimeError("Expected exactly one running license bastion")

    previous_handlers = {
        signum: signal.signal(signum, interrupted) for signum in (signal.SIGTERM, signal.SIGINT)
    }
    tunnel = None
    tests = None
    try:
        with log.open("w") as output:
            log.chmod(0o600)
            tunnel = subprocess.Popen(
                [
                    "aws",
                    "ssm",
                    "start-session",
                    "--target",
                    instances[0],
                    "--document-name",
                    "DccInteg-PortForwardToLicenseServer",
                    "--parameters",
                    json.dumps(
                        {
                            "portNumber": [str(port)],
                            "localPortNumber": [str(port)],
                        }
                    ),
                    "--profile",
                    "license",
                ],
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_for_tunnel(tunnel, port)
            print("Foundry license tunnel is ready", flush=True)
            tests = subprocess.Popen(command, start_new_session=True)
            while tests.poll() is None:
                if tunnel.poll() is not None:
                    raise RuntimeError("SSM tunnel exited during the GUI test run")
                time.sleep(0.5)
            return tests.returncode
    finally:
        # Complete all local cleanup even if AWS remote termination fails.
        stop_process(tests)
        stop_process(tunnel)
        try:
            cleanup_state(log, config, environment)
        except RuntimeError:
            print(
                "Remote SSM cleanup failed; the workflow cleanup step will retry", file=sys.stderr
            )
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
