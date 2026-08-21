#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Install Nuke on an ephemeral macOS integration-test runner."""

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_NUKE_VERSION_PATTERN = re.compile(r"\d+\.\d+v\d+")


@dataclass(frozen=True)
class NukeInstallation:
    """Paths derived from one validated Nuke version."""

    version: str
    install_dir: Path
    app: Path
    executable: Path
    python: Path


def nuke_installation(version: str) -> NukeInstallation:
    """Build the expected macOS installation paths for *version*."""
    version = version.strip()
    if not _NUKE_VERSION_PATTERN.fullmatch(version):
        raise ValueError("Nuke version must have the form MAJOR.MINORvREVISION")

    major_minor = version.split("v", 1)[0]
    install_dir = Path("/Applications") / f"Nuke{version}"
    app = install_dir / f"Nuke{version}.app"
    return NukeInstallation(
        version=version,
        install_dir=install_dir,
        app=app,
        executable=app / "Contents" / "MacOS" / f"Nuke{major_minor}",
        python=app / "Contents" / "MacOS" / "python",
    )


def run(
    command: List[str], check: bool = True, input_data: Optional[bytes] = None
) -> subprocess.CompletedProcess:
    """Run a command and return its result."""
    print(f"Running: {subprocess.list2cmdline(command)}")
    return subprocess.run(command, check=check, input=input_data)


def required_environment_variable(name: str) -> str:
    """Return a required, non-empty environment variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def download_installer(destination: Path) -> None:
    """Download the installer while verifying the expected bucket owner."""
    bucket = required_environment_variable("INSTALLER_BUCKET")
    key = required_environment_variable("NUKE_INSTALLER_S3_KEY")
    expected_owner = required_environment_variable("INSTALLER_BUCKET_EXPECTED_OWNER")
    if not (expected_owner.isdigit() and len(expected_owner) == 12):
        raise ValueError("INSTALLER_BUCKET_EXPECTED_OWNER must be a 12-digit AWS account ID")

    print(f"Downloading s3://{bucket}/{key} to {destination}")
    run(
        [
            "aws",
            "s3api",
            "get-object",
            "--bucket",
            bucket,
            "--key",
            key,
            "--expected-bucket-owner",
            expected_owner,
            "--no-cli-pager",
            str(destination),
        ]
    )


def verify_checksum(installer: Path) -> None:
    """Verify the downloaded installer against the configured SHA-256."""
    expected = required_environment_variable("NUKE_INSTALLER_SHA256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("NUKE_INSTALLER_SHA256 must be a 64-character hexadecimal digest")

    digest = hashlib.sha256()
    with installer.open("rb") as installer_file:
        for chunk in iter(lambda: installer_file.read(1024 * 1024), b""):
            digest.update(chunk)

    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(f"Installer checksum mismatch: expected {expected}, got {actual}")
    print("Installer checksum verified")


def install_from_dmg(installer: Path, installation: NukeInstallation) -> None:
    """Mount a Foundry DMG and copy its Nuke application."""
    mount_point = Path(tempfile.mkdtemp(prefix="nuke-installer-"))
    attached = False
    try:
        run(
            [
                "hdiutil",
                "attach",
                "-nobrowse",
                "-readonly",
                "-mountpoint",
                str(mount_point),
                str(installer),
            ],
            input_data=b"Y\n",
        )
        attached = True

        product_app = (
            mount_point / f"Nuke{installation.version}" / f"Nuke{installation.version}.app"
        )
        if not product_app.is_dir():
            contents = "\n".join(
                str(path.relative_to(mount_point)) for path in mount_point.iterdir()
            )
            raise FileNotFoundError(
                f"Expected Nuke application at {product_app}\nDMG contents:\n{contents}"
            )

        run(["sudo", "mkdir", "-p", str(installation.install_dir)])
        run(["sudo", "ditto", str(product_app), str(installation.app)])
    finally:
        if attached:
            run(["hdiutil", "detach", str(mount_point)], check=False)
        if mount_point.exists() and not mount_point.is_mount():
            shutil.rmtree(mount_point)


def verify_installation(installation: NukeInstallation) -> None:
    """Verify the executable and bundled Python required by the workflow."""
    required_files = {
        "Nuke executable": installation.executable,
        "Nuke Python": installation.python,
    }
    missing = [
        f"{description}: {path}"
        for description, path in required_files.items()
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError("Nuke installation is incomplete:\n" + "\n".join(missing))

    non_executable = [
        f"{description}: {path}"
        for description, path in required_files.items()
        if not os.access(path, os.X_OK)
    ]
    if non_executable:
        raise PermissionError(
            "Nuke installation files are not executable:\n" + "\n".join(non_executable)
        )


def write_github_environment(destination: Path, installation: NukeInstallation) -> None:
    """Expose the validated Nuke paths to later GitHub Actions steps."""
    with destination.open("a", encoding="utf-8") as environment_file:
        environment_file.write(f"NUKE_EXECUTABLE={installation.executable}\n")
        environment_file.write(f"NUKE_PYTHON={installation.python}\n")


def parse_args(arguments: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Nuke version, for example 16.0v7")
    parser.add_argument(
        "--github-env",
        type=Path,
        help="Optional GitHub Actions environment file to append validated paths to",
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[List[str]] = None) -> None:
    """Install and verify the configured Nuke version."""
    args = parse_args(arguments)
    installation = nuke_installation(args.version)

    if platform.system() != "Darwin":
        raise RuntimeError("Nuke integration-test setup currently supports only macOS")

    if installation.executable.is_file() and installation.python.is_file():
        print(f"Nuke {installation.version} is already installed at {installation.install_dir}")
    else:
        runner_temp = Path(required_environment_variable("RUNNER_TEMP"))
        installer_key = required_environment_variable("NUKE_INSTALLER_S3_KEY")
        installer_name = Path(installer_key).name
        if not installer_name.lower().endswith(".dmg"):
            raise ValueError("NUKE_INSTALLER_S3_KEY must identify a .dmg file")

        installer = runner_temp / installer_name
        try:
            download_installer(installer)
            verify_checksum(installer)
            install_from_dmg(installer, installation)
        finally:
            installer.unlink(missing_ok=True)

    verify_installation(installation)
    if args.github_env:
        write_github_environment(args.github_env, installation)
    print(f"Nuke {installation.version} installed successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
