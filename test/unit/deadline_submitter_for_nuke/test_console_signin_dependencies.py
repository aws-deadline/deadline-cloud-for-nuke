# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the dependency declarations that AWS Console sign-in depends on.

Console sign-in is not exercised by the integration tests: it needs an interactive
browser OAuth handshake and Deadline Cloud Monitor, while CI authenticates by
assuming a role, so credentials are host-provided and the console path is never
taken. What can break silently is the dependency declaration, which is what these
tests pin.

The tests read ``pyproject.toml`` rather than installed distribution metadata.
``importlib.metadata`` reflects what was captured at install time, so an edit to
``pyproject.toml`` would not be seen until the environment is reinstalled -- and
"somebody edited that line" is precisely the regression being guarded.

Scope matters as much as the versions. The ``console`` extra belongs in
``scripts/depsBundle.py`` and not in the base dependencies: the base list is
resolved into the adaptor package by ``scripts/create_adaptor_packaging_artifact.sh``
under ``--only-binary=:all: --platform <tag>``, and no awscrt wheel meeting
botocore's floor exists for the ``macosx_10_9_x86_64`` tag that script uses, so pip
would silently walk back to a release with no usable crypto support.

The tests above guard the negative side: the extra and awscrt must be absent from
project.dependencies. The tests below guard the positive side -- that
``_build_base_environment`` still adds the extra back before calling pip, that
``_add_console_extra`` does so correctly, and that ``NATIVE_DEPENDENCIES`` still
carries awscrt and pyyaml -- so that removing any of those silently breaks console
sign-in in the shipped bundle without failing the negative-side tests above.
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

# Console sign-in landed in deadline 0.60.4 and nowhere earlier: 0.60.1 through
# 0.60.3 have no AWS_CONSOLE_LOGIN credentials source and do not declare a
# `console` extra at all. 0.60.3 is the highest version that must be excluded.
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
    # Requirement.name rather than normalizing it, so "Deadline[console]>=x" has name
    # "Deadline", not "deadline". Comparing raw names would let a re-spelling of the
    # requirement make the calling assertions pass vacuously against an empty list.
    target = canonicalize_name(name)
    return [r for r in requirements if canonicalize_name(r.name) == target]


def test_deadline_floor_excludes_releases_without_console_signin():
    """Guards the floor itself, not whatever a resolver happened to select.

    An installed-version check cannot do this: with a loosened ">= 0.60.2"
    requirement, pip still resolves the newest 0.60.x, so the regression passes
    unnoticed. Below 0.60.4, deadline[console] is not even a valid request, and pip
    backtracks past the extra, drops awscrt, warns once, and exits 0.
    """
    deadline_reqs = _named(_base_dependencies(), "deadline")
    assert deadline_reqs, "pyproject.toml declares no requirement on deadline"
    for req in deadline_reqs:
        assert not req.specifier.contains(HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN), (
            f"allows deadline {HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN}, which has no "
            f"console sign-in support: {req}"
        )


def test_base_dependencies_do_not_request_the_console_extra():
    """Keeps awscrt out of the adaptor package.

    The base list is resolved into the adaptor artifact for three platform tags under
    --only-binary=:all:. For macosx_10_9_x86_64 no awscrt wheel meets botocore's floor,
    so pip resolves backwards to one whose crypto support botocore will not accept --
    the build succeeds and console sign-in is quietly broken. The adaptor never signs
    in interactively, so it has no use for the extra; the submitter's dependency bundle
    requests it in scripts/depsBundle.py instead.
    """
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
    """Keeps the pip-installable `console` extra in step with the base deadline pin.

    DEVELOPMENT.md's submitter workflow installs this package directly with pip, into
    Nuke's own Python distribution, rather than through scripts/depsBundle.py's dependency
    bundle -- so it needs its own supported way to request the console extra, or console
    sign-in silently would not work there either. The extra restates deadline's specifier
    rather than inheriting it, so a floor bump in `dependencies` that is not mirrored here
    would let the extra install a `deadline` version older than the base pin allows.
    """
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
    """Pins the packages depsBundle.py fetches per-version for their compiled artifacts.

    Console sign-in needs awscrt to be importable under whichever Python Nuke embeds; pyyaml
    needs the same because it silently falls back to a pure-Python parser otherwise. Dropping
    either from NATIVE_DEPENDENCIES would ship a bundle where a subset of interpreters cannot
    load one of them, with nothing here to catch it.
    """
    assert "awscrt" in depsBundle.NATIVE_DEPENDENCIES
    assert "pyyaml" in depsBundle.NATIVE_DEPENDENCIES


def test_build_base_environment_requests_the_console_extra(tmp_path, monkeypatch):
    """Pins the positive half of the console sign-in fix: the extra actually reaches pip.

    test_base_dependencies_do_not_request_the_console_extra guards that the extra is absent
    from project.dependencies; this guards that _build_base_environment still adds it back
    before invoking pip, mirroring the subprocess.run monkeypatch already used in
    test_deps_bundle_native_merge.py. If the _add_console_extra call here were dropped, that
    other test would stay green while the shipped bundle silently lost console sign-in.
    """
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
    """Pins _add_console_extra's contract: preserve existing extras, be idempotent, and leave
    non-deadline requirements untouched.
    """
    assert depsBundle._add_console_extra(requirement) == expected


def test_add_console_extra_changes_the_real_base_dependencies():
    """Stronger than the parametrized behavior test above: proves the injection takes effect
    against pyproject.toml's actual dependencies, not just a synthetic requirement string.

    _add_console_extra no-ops on any requirement it does not recognize as `deadline`. If
    that requirement were ever renamed, wrapped, or split -- say the base dependency became
    `deadline-cloud` -- this test fails, whereas test_add_console_extra_pins_behavior above
    would keep passing forever since it never exercises the real declaration. A rename
    passing silently here is exactly how the bundle would ship with no awscrt: the same
    no-op would also leave awscrt absent from the base environment, and
    _download_native_dependencies's _get_package_version call for it fails loudly at build
    time -- but nothing in the unit suite catches it before that.
    """
    dependencies = depsBundle._get_dependencies(_pyproject())
    dependencies_for_pip = [depsBundle._add_console_extra(dep) for dep in dependencies]

    assert dependencies_for_pip != dependencies, (
        "_add_console_extra left every real base dependency unchanged; the `deadline` "
        "requirement it targets may have been renamed, wrapped, or removed from "
        "project.dependencies"
    )
