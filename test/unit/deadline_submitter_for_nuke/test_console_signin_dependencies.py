# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the dependency declarations that AWS Console sign-in depends on.

Console sign-in is not exercised by the integration tests: CI authenticates by assuming a
role, so the console path is never taken there. What can break silently is the dependency
declaration, which is what these tests pin.

Reads ``pyproject.toml`` directly rather than installed distribution metadata, since
``importlib.metadata`` would not see an edit until the environment is reinstalled.

Splits into a negative guard (the console extra and awscrt must be absent from
project.dependencies) and a positive guard (the extra must still reach pip via
``_add_console_extra`` and ``_build_base_environment``, and ``NATIVE_DEPENDENCIES`` must
still be correct) -- so removing either side's target breaks console sign-in without
failing the other side's tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.9 and 3.10 only
    import tomli as tomllib

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

import depsBundle  # noqa: E402  # importable only after the sys.path append above

PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"

# 0.60.1-0.60.3 have no AWS_CONSOLE_LOGIN credentials source and declare no `console`
# extra; 0.60.3 is the highest version that must stay excluded.
HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN = "0.60.3"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _base_dependencies() -> list[Requirement]:
    project_dict = _pyproject()
    assert "project" in project_dict, "pyproject.toml has no project table"
    assert "dependencies" in project_dict["project"], "pyproject.toml has no dependencies"
    return [Requirement(r) for r in project_dict["project"]["dependencies"]]


def _console_extra_dependencies() -> list[Requirement]:
    optional_groups = _pyproject()["project"].get("optional-dependencies", {})
    assert "console" in optional_groups, (
        "pyproject.toml declares no `console` optional group, so a direct `pip install "
        "deadline-cloud-for-nuke[console]` has no way to get awscrt and AWS Console "
        "sign-in breaks there"
    )
    return [Requirement(r) for r in optional_groups["console"]]


def _named(requirements: list[Requirement], name: str) -> list[Requirement]:
    # canonicalize_name on both sides: packaging preserves pyproject's spelling in
    # Requirement.name, so "Deadline[console]>=x" has name "Deadline", not "deadline" --
    # a raw comparison would let a re-spelling pass the calling assertions vacuously.
    target = canonicalize_name(name)
    return [r for r in requirements if canonicalize_name(r.name) == target]


def test_deadline_floor_excludes_releases_without_console_signin():
    """Pins the declared deadline floor, independent of whatever a resolver selects."""
    deadline_reqs = _named(_base_dependencies(), "deadline")
    assert deadline_reqs, "pyproject.toml declares no requirement on deadline"
    for req in deadline_reqs:
        assert not req.specifier.contains(HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN), (
            f"allows deadline {HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN}, which has no "
            f"console sign-in support: {req}"
        )


def test_base_dependencies_do_not_request_the_console_extra():
    """Keeps the console extra, and awscrt directly, out of the adaptor's dependencies."""
    base_dependencies = _base_dependencies()
    deadline_reqs = _named(base_dependencies, "deadline")
    assert deadline_reqs, "pyproject.toml declares no requirement on deadline"
    for req in deadline_reqs:
        assert (
            "console" not in req.extras
        ), f"console extra leaks into the adaptor's dependency closure via: {req}"

    # Copying the requirement in directly is the likelier mistake, and has the same effect.
    assert not _named(
        base_dependencies, "awscrt"
    ), "awscrt must not be a base dependency; it would be resolved into the adaptor package"


def test_console_extra_matches_the_deadline_floor():
    """Keeps the pip-installable `console` extra's deadline pin in step with the base pin."""
    deadline_reqs = _named(_base_dependencies(), "deadline")
    assert deadline_reqs, "pyproject.toml declares no requirement on deadline"
    assert len(deadline_reqs) == 1, f"expected exactly one deadline requirement: {deadline_reqs}"
    base_deadline = deadline_reqs[0]

    console_deadline_reqs = _named(_console_extra_dependencies(), "deadline")
    assert console_deadline_reqs, "the console optional group declares no requirement on deadline"
    assert (
        len(console_deadline_reqs) == 1
    ), f"expected exactly one deadline requirement in the console group: {console_deadline_reqs}"
    console_deadline = console_deadline_reqs[0]

    assert "console" in console_deadline.extras, (
        f"the console group's deadline requirement does not request deadline's own console "
        f"extra, so it would not pull awscrt: {console_deadline}"
    )
    assert console_deadline.specifier == base_deadline.specifier, (
        f"the console group pins deadline as `{console_deadline}` but dependencies "
        f"declares `{base_deadline}`; the two must agree or the extra can admit a "
        f"deadline version the base install forbids"
    )


def test_native_dependencies_include_awscrt_and_pyyaml():
    """Pins that awscrt and pyyaml stay in NATIVE_DEPENDENCIES."""
    assert "awscrt" in depsBundle.NATIVE_DEPENDENCIES
    assert "pyyaml" in depsBundle.NATIVE_DEPENDENCIES


def test_build_base_environment_requests_the_console_extra(tmp_path, monkeypatch):
    """Pins that _build_base_environment passes the console extra to pip."""
    captured_args: list[str] = []

    def record(args, **kwargs):
        captured_args.extend(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(depsBundle.subprocess, "run", record)

    depsBundle._build_base_environment(tmp_path, ["deadline>=0.60.4,<0.61", "xxhash"])

    console_reqs = [arg for arg in captured_args if arg.lower().startswith("deadline[")]
    assert console_reqs, f"no deadline requirement with an extra was passed to pip: {captured_args}"
    assert "console" in console_reqs[0], f"console extra missing from pip argv: {console_reqs[0]}"


@pytest.mark.parametrize(
    "requirement,expected",
    [
        ("deadline>=0.60.4,<0.61", "deadline[console]>=0.60.4,<0.61"),
        ("deadline[gui]>=0.60.4", "deadline[gui,console]>=0.60.4"),
        ("deadline[gui,console]>=0.60.4", "deadline[gui,console]>=0.60.4"),
        ("deadline[console]>=0.60.4", "deadline[console]>=0.60.4"),
        ("xxhash>=3.0", "xxhash>=3.0"),
    ],
)
def test_add_console_extra_pins_behavior(requirement, expected):
    """Pins _add_console_extra's contract: preserve extras, be idempotent, ignore others."""
    assert depsBundle._add_console_extra(requirement) == expected


def test_add_console_extra_changes_the_real_base_dependencies():
    """Pins that _add_console_extra actually changes pyproject.toml's real dependencies,
    not just a synthetic requirement string like the parametrized test above.
    """
    dependencies = depsBundle._get_dependencies(_pyproject())
    dependencies_for_pip = [depsBundle._add_console_extra(dep) for dep in dependencies]

    assert dependencies_for_pip != dependencies, (
        "_add_console_extra left every real base dependency unchanged; the `deadline` "
        "requirement it targets may have been renamed, wrapped, or removed from "
        "project.dependencies"
    )
