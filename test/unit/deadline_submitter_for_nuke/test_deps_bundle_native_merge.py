# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards which compiled artifact the dependency bundle ships for each interpreter.

The bundle is one flat ``PYTHONPATH`` directory, so it holds a single file per name no
matter how many Python versions Nuke might embed. When two per-version installs supply the
same filename, only one survives the merge, and a copy built for a newer Python fails to
import on an older one.

These tests drive the merge over synthetic trees named like the real wheels' extension
modules. They assert which artifact is selected, not that it loads -- that needs the target
interpreter, which the unit suite has no access to.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

import depsBundle  # noqa: E402  # importable only after the sys.path append above

# awscrt's abi3 wheels all install this one name, whatever Python they were built for.
ABI3_ARTIFACT = "_awscrt.abi3.so"

# awscrt publishes version-specific (non-abi3) wheels for Pythons below this, and abi3
# wheels from here up.
FIRST_AWSCRT_ABI3_VERSION = (3, 11)

# Seeded into the base environment's abi3 artifact: stands in for a copy resolved for the
# build host's own interpreter, which is not a version the bundle targets.
HOST_SENTINEL = "host"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _tag(version: str) -> str:
    """The interpreter tag a wheel puts in a version-specific extension module name."""
    return version.replace(".", "")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def supported_versions() -> list[str]:
    versions = sorted(depsBundle.SUPPORTED_PYTHON_VERSIONS, key=_version_key)
    assert len(versions) >= 2, "a filename collision needs at least two supported versions"
    assert _version_key(versions[-1]) >= FIRST_AWSCRT_ABI3_VERSION, (
        "no supported version gets an abi3 awscrt wheel; the base-environment-vs-native-tree "
        "collision these tests guard cannot occur. This does not by itself require two abi3 "
        "trees -- see test_colliding_abi3_artifact_prefers_the_first_tree_over_later_ones for "
        "the tree-vs-tree case, which today's supported set has only one version for."
    )
    return versions


@pytest.fixture
def merged_bundle(tmp_path, supported_versions) -> Path:
    """Run the merge over trees named the way the real wheels name their artifacts.

    awscrt is version-specific below 3.11 and shares the abi3 name from 3.11 up; xxhash and
    pyyaml are version-specific for every version; psutil ships one shared abi3 wheel, so
    every tree holds identical bytes for it. Each file's content records which version
    produced it. The base environment is seeded with a host sentinel, standing in for the
    build host's own interpreter.
    """
    base_env = tmp_path / "base_env"
    _write(base_env / ABI3_ARTIFACT, HOST_SENTINEL)

    native_paths = []
    for version in supported_versions:
        tree = tmp_path / "native" / _tag(version)
        native_paths.append(tree)
        if _version_key(version) < FIRST_AWSCRT_ABI3_VERSION:
            _write(tree / f"_awscrt.cpython-{_tag(version)}-darwin.so", version)
        else:
            _write(tree / ABI3_ARTIFACT, version)
        _write(tree / "xxhash" / f"_xxhash.cpython-{_tag(version)}-darwin.so", version)
        _write(tree / "yaml" / f"_yaml.cpython-{_tag(version)}-darwin.so", version)
        _write(tree / "psutil" / "_psutil_osx.abi3.so", "shared")

    depsBundle._copy_native_to_base_env(base_env, native_paths)
    return base_env


def test_colliding_abi3_artifact_comes_from_the_lowest_supported_abi(
    merged_bundle, supported_versions
):
    """abi3 is forward-compatible only, so the lowest supported version's copy must win.

    Only proves a native tree beats the base environment -- with one abi3-era version
    today, tree-vs-tree ordering is pinned separately by
    test_colliding_abi3_artifact_prefers_the_first_tree_over_later_ones below.
    """
    lowest_abi3_version = next(
        version
        for version in supported_versions
        if _version_key(version) >= FIRST_AWSCRT_ABI3_VERSION
    )
    shipped = (merged_bundle / ABI3_ARTIFACT).read_text()

    assert shipped != HOST_SENTINEL, (
        f"{ABI3_ARTIFACT} is the build host's own copy; the host interpreter is not a "
        f"version the bundle targets, so it must not decide which artifact ships"
    )
    assert shipped == lowest_abi3_version, (
        f"{ABI3_ARTIFACT} was built for Python {shipped}, so it cannot be imported by "
        f"Python {lowest_abi3_version}; the copy built for the lowest supported abi3 "
        f"version is the one every supported interpreter can load"
    )


def test_colliding_abi3_artifact_prefers_the_first_tree_over_later_ones(tmp_path):
    """Tree-vs-tree abi3 collision, pinned independently of SUPPORTED_PYTHON_VERSIONS.

    The first (lowest-version) tree must win: a last-writer merge would ship the copy built
    for the newer Python, which the older one cannot import.
    """
    base_env = tmp_path / "base_env"
    _write(base_env / ABI3_ARTIFACT, HOST_SENTINEL)

    native_paths = []
    for version in ("3.11", "3.12"):
        tree = tmp_path / "native" / _tag(version)
        native_paths.append(tree)
        _write(tree / ABI3_ARTIFACT, version)

    depsBundle._copy_native_to_base_env(base_env, native_paths)

    shipped = (base_env / ABI3_ARTIFACT).read_text()
    assert shipped == "3.11", (
        f"{ABI3_ARTIFACT} came from Python {shipped}; the merge must keep the first "
        f"(lowest-version) native tree's copy, the only one every supported abi3 "
        f"interpreter can load"
    )


def test_version_specific_artifacts_are_kept_for_every_supported_version(
    merged_bundle, supported_versions
):
    """Version-specific names never collide, so every supported version keeps its copy."""
    for version in supported_versions:
        for package, module in (("xxhash", "_xxhash"), ("yaml", "_yaml")):
            artifact = merged_bundle / package / f"{module}.cpython-{_tag(version)}-darwin.so"
            assert (
                artifact.exists()
            ), f"the bundle carries no {package} artifact for Python {version}"
            assert artifact.read_text() == version

    for version in supported_versions:
        if _version_key(version) >= FIRST_AWSCRT_ABI3_VERSION:
            continue
        awscrt_non_abi3 = merged_bundle / f"_awscrt.cpython-{_tag(version)}-darwin.so"
        assert (
            awscrt_non_abi3.exists()
        ), f"the bundle carries no awscrt artifact for Python {version}"


def test_native_trees_are_merged_lowest_python_version_first(tmp_path, monkeypatch):
    """Downloads happen in ascending numeric order (string-sort would put "3.9" after "3.10")."""
    monkeypatch.setattr(depsBundle, "SUPPORTED_PYTHON_VERSIONS", ["3.13", "3.9", "3.11", "3.10"])
    monkeypatch.setattr(depsBundle, "_get_package_version", lambda package, install_path: "1.2.3")

    requested_versions: list[str] = []

    def record(args, **kwargs):
        requested_versions.append(args[args.index("--python-version") + 1])
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(depsBundle.subprocess, "run", record)

    tree_paths = depsBundle._download_native_dependencies(tmp_path, tmp_path / "base_env")

    assert requested_versions == ["3.9", "3.10", "3.11", "3.13"]
    assert [path.name for path in tree_paths] == ["3_9", "3_10", "3_11", "3_13"]


def test_get_package_version_matches_pip_list_casing(monkeypatch):
    """`pip list` prints the distribution's own casing (`PyYAML`), not the requirement's."""
    output = b"Package  Version\n-------- -------\nPyYAML   6.0.3\nxxhash   3.6.0\n"
    monkeypatch.setattr(
        depsBundle.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=output),
    )

    assert depsBundle._get_package_version("pyyaml", Path("/unused")) == "6.0.3"
