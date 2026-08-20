"""Tooling tests for the review-fix rounds (bare pytest invocation + CI workflow)."""

import configparser
import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")


def _run_pytest(command, *args):
    """Run a pytest command from the repo root and return the completed process."""
    completed = subprocess.run(
        command + list(args),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        f"{' '.join(command)} failed:\n{completed.stdout}\n{completed.stderr}"
    )
    assert "ModuleNotFoundError" not in completed.stdout + completed.stderr
    return completed


def _run_collect(command, *opts, path="tests/test_primes.py"):
    """Collect tests with the given pytest command (defaults to the primes module)."""
    args = ["--collect-only", "-q", *opts]
    if path is not None:
        args.append(path)
    return _run_pytest(command, *args)


def _python_m_pytest():
    return [sys.executable, "-m", "pytest"]


def _pytest_command():
    """Prefer the bare pytest executable; fall back to `python -m pytest`."""
    pytest_exe = shutil.which("pytest")
    return [pytest_exe] if pytest_exe else _python_m_pytest()


def _bare_pytest_or_skip():
    pytest_exe = shutil.which("pytest")
    if pytest_exe is None:
        pytest.skip("bare 'pytest' executable not on PATH")
    return [pytest_exe]


def test_root_conftest_exists():
    assert os.path.isfile(os.path.join(REPO_ROOT, "conftest.py")), (
        "missing root conftest.py (import-path defense-in-depth)"
    )


def test_bare_pytest_collects_from_repo_root():
    _run_collect(_bare_pytest_or_skip())


def test_python_m_pytest_collects_from_repo_root():
    _run_collect(_python_m_pytest())


def test_collection_works_without_pythonpath_ini():
    _run_collect(_pytest_command(), "-o", "pythonpath=")


def test_bare_pytest_with_no_args_collects_suite():
    """The reviewer's literal scenario: plain `pytest` with no path arguments."""
    completed = _run_collect(_pytest_command(), path=None)
    for module in ("tests/test_primes.py", "tests/test_tooling.py"):
        assert module in completed.stdout, f"{module} not collected by bare pytest"


def test_ci_workflow_runs_pytest_on_push_and_pr():
    assert os.path.isfile(WORKFLOW_PATH), "missing .github/workflows/ci.yml"
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        workflow = f.read()
    for expected in (
        "push",
        "pull_request",
        "actions/checkout",
        "actions/setup-python",
        "pytest",
    ):
        assert expected in workflow, f"ci.yml missing {expected!r}"


def test_pytest_ini_pins_pythonpath_and_testpaths():
    ini_path = os.path.join(REPO_ROOT, "pytest.ini")
    assert os.path.isfile(ini_path), "missing pytest.ini (bare-pytest import fix)"
    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding="utf-8")
    assert parser.has_section("pytest")
    assert parser.get("pytest", "pythonpath").split() == ["."]
    assert parser.get("pytest", "testpaths").split() == ["tests"]


def test_ci_workflow_parses_with_expected_shape():
    yaml = pytest.importorskip("yaml")
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        workflow = yaml.safe_load(f)
    triggers = workflow.get(True) or workflow.get("on")
    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]
    job = workflow["jobs"]["test"]
    uses = [step.get("uses") for step in job["steps"]]
    assert "actions/checkout@v4" in uses
    assert "actions/setup-python@v5" in uses
    run_script = "\n".join(step.get("run", "") for step in job["steps"])
    assert "pytest" in run_script
    assert "pyyaml" in run_script, "CI must install pyyaml so the YAML parse test runs there"
