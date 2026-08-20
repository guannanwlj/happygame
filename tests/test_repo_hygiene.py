"""Repository hygiene tests locking the round-3 merge-conflict findings (task-mt18its6gv)."""

import os
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BYTECODE_PATHSPECS = ["*.pyc", "*__pycache__*"]


def _git(*args):
    """Run a git command in the repo root and return the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _offenders(lines):
    return [
        path
        for path in lines
        if path.endswith(".pyc") or "__pycache__" in path
    ]


def test_tree_tracks_no_bytecode_artifacts():
    listed = _git("ls-files")
    assert listed.returncode == 0, listed.stderr
    offenders = _offenders(listed.stdout.splitlines())
    assert offenders == [], f"bytecode artifacts tracked in the tree: {offenders}"


def test_history_never_adds_bytecode_artifacts():
    log = _git(
        "log",
        "--diff-filter=A",
        "--name-only",
        "--pretty=format:",
        "HEAD",
        "--",
        *BYTECODE_PATHSPECS,
    )
    assert log.returncode == 0, log.stderr
    added = _offenders(log.stdout.splitlines())
    assert added == [], (
        f"commits reachable from HEAD added bytecode artifacts: {added}"
    )


def test_branch_merges_cleanly_into_origin_main():
    probe = _git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main")
    if probe.returncode != 0:
        pytest.skip("origin/main is not available locally (shallow checkout)")
    merged = _git("merge-tree", "--write-tree", "origin/main", "HEAD")
    assert merged.returncode == 0, (
        f"branch conflicts with origin/main:\n{merged.stdout}\n{merged.stderr}"
    )
