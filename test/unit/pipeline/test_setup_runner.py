# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Unlicensed checks for installer selection, archive handling, and secret hygiene."""

import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import Mock

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[3] / "pipeline" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def setup():
    return load_script("setup-runner")


def make_archive(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, kind, contents in members:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(contents) if kind == tarfile.REGTYPE else 0
            archive.addfile(member, io.BytesIO(contents))


def test_platform_paths_and_version_validation(setup):
    mac = setup.nuke_installation("16.0v7")
    assert mac.executable == Path("/Applications/Nuke16.0v7/Nuke16.0v7.app/Contents/MacOS/Nuke16.0")
    linux = setup.nuke_installation("16.0v7", "Linux")
    assert linux.executable == Path("/usr/local/Nuke16.0v7/Nuke16.0")
    assert linux.python == Path("/usr/local/Nuke16.0v7/python")
    for version in ("../16.0v7", "16.0v7\nother=value", "16"):
        with pytest.raises(ValueError):
            setup.nuke_installation(version, "Linux")
    with pytest.raises(RuntimeError):
        setup.nuke_installation("16.0v7", "Windows")


def test_linux_installer_uses_prefix_parent_without_extracting_paths(setup, tmp_path, monkeypatch):
    archive = tmp_path / "installer.tgz"
    contents = b"#!/bin/sh\nexit 0\n"
    make_archive(
        archive,
        [
            ("../../outside.run", tarfile.REGTYPE, contents),
            ("ignored-device", tarfile.CHRTYPE, b""),
        ],
    )
    commands = []

    def run(command):
        assert Path(command[0]).read_bytes() == contents
        assert Path(command[0]).stat().st_mode & 0o777 == 0o700
        commands.append(command)

    monkeypatch.setattr(setup, "run", run)
    monkeypatch.setattr(setup.os, "geteuid", lambda: 0)
    setup.install_from_tgz(archive, setup.nuke_installation("16.0v7", "Linux"))
    assert commands[0][1:] == ["--prefix", "/usr/local", "--accept-foundry-eula"]
    assert not Path(commands[0][0]).exists()  # staging removed
    assert not (tmp_path / "outside.run").exists()


@pytest.mark.parametrize(
    "members",
    [
        [],
        [("installer.run", tarfile.SYMTYPE, b"")],
        [("one.run", tarfile.REGTYPE, b""), ("two.run", tarfile.REGTYPE, b"")],
    ],
)
def test_rejects_ambiguous_or_link_installers(setup, tmp_path, members):
    archive = tmp_path / "installer.tgz"
    make_archive(archive, members)
    with pytest.raises(ValueError, match="exactly one regular"):
        setup.install_from_tgz(archive, setup.nuke_installation("16.0v7", "Linux"))


def test_download_failure_and_checksum_do_not_print_secrets(setup, tmp_path, monkeypatch, capsys):
    secrets = {
        "INSTALLER_BUCKET": "private-bucket",
        "NUKE_INSTALLER_S3_KEY": "private/key.tgz",
        "INSTALLER_BUCKET_EXPECTED_OWNER": "123456789012",
        "NUKE_INSTALLER_SHA256": "a" * 64,
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        Mock(side_effect=subprocess.CalledProcessError(1, ["aws", *secrets.values()])),
    )
    installer = tmp_path / "installer.tgz"
    installer.write_bytes(b"bad installer")
    with pytest.raises(RuntimeError) as download:
        setup.download_installer(installer)
    with pytest.raises(ValueError) as checksum:
        setup.verify_checksum(installer)
    output = capsys.readouterr().out + str(download.value) + str(checksum.value)
    assert all(value not in output for value in secrets.values())


@pytest.mark.parametrize(
    "system,extension,installer_function",
    [
        ("Darwin", ".dmg", "install_from_dmg"),
        ("Linux", ".tgz", "install_from_tgz"),
    ],
)
def test_main_selects_installer_and_always_removes_download(
    setup,
    tmp_path,
    monkeypatch,
    system,
    extension,
    installer_function,
):
    monkeypatch.setattr(setup.platform, "system", lambda: system)
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    installation = setup.NukeInstallation(
        "16.0v7", tmp_path, tmp_path, tmp_path / "Nuke", tmp_path / "python"
    )
    monkeypatch.setattr(setup, "nuke_installation", lambda *_: installation)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("NUKE_INSTALLER_S3_KEY", f"private/key{extension}")
    monkeypatch.setenv("NUKE_INSTALLER_SHA256", hashlib.sha256(b"installer").hexdigest())
    monkeypatch.setattr(setup, "download_installer", lambda path: path.write_bytes(b"installer"))
    monkeypatch.setattr(setup, installer_function, Mock(side_effect=RuntimeError("install failed")))
    with pytest.raises(RuntimeError, match="install failed"):
        setup.main(["--version", "16.0v7"])
    assert not (tmp_path / f"nuke-installer{extension}").exists()


def test_dmg_detaches_on_copy_failure(setup, tmp_path, monkeypatch):
    installation = setup.nuke_installation("16.0v7")
    mount = tmp_path / "mount"
    (mount / "Nuke16.0v7" / "Nuke16.0v7.app").mkdir(parents=True)
    monkeypatch.setattr(setup.tempfile, "mkdtemp", lambda **_: str(mount))
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if "ditto" in command:
            raise RuntimeError("copy failed")

    monkeypatch.setattr(setup, "run", run)
    with pytest.raises(RuntimeError, match="copy failed"):
        setup.install_from_dmg(tmp_path / "installer.dmg", installation)
    assert commands[-1] == ["hdiutil", "detach", str(mount)]
    assert not mount.exists()
