"""Tooling tests for the round-2 review fixes (bare pytest invocation + CI workflow)."""

import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_collect(command):
    """Run a pytest command that collects tests/test_primes.py from the repo root."""
    completed = subprocess.run(
        command + ["--collect-only", "-q", "tests/test_primes.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        f"{' '.join(command)} failed:\n{completed.stdout}\n{completed.stderr}"
    )
    assert "ModuleNotFoundError" not in completed.stdout + completed.stderr


def test_bare_pytest_collects_from_repo_root():
    pytest_exe = shutil.which("pytest")
    if pytest_exe is None:
        pytest.skip("bare 'pytest' executable not on PATH")
    _run_collect([pytest_exe])


def test_python_m_pytest_collects_from_repo_root():
    _run_collect([sys.executable, "-m", "pytest"])


def test_ci_workflow_runs_pytest_on_push_and_pr():
    workflow_path = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
    assert os.path.isfile(workflow_path), "missing .github/workflows/ci.yml"
    with open(workflow_path, encoding="utf-8") as f:
        workflow = f.read()
    assert "push" in workflow
    assert "pull_request" in workflow
    assert "pytest" in workflow
