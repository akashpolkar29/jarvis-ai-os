"""Tests that the CI/tooling gates themselves are correctly configured.

This is deliberately meta: it doesn't test JARVIS's behavior, it tests
that the safety net around JARVIS's behavior hasn't quietly eroded (a
contract deleted from ``pyproject.toml``, a gate dropped from CI, a
scheduled contract added before its package exists).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

CURRENT_WORK_PACKAGE = 24

# Work package at which each import-linter contract becomes configurable.
# A contract can only be added once every package it names exists on
# disk — import-linter errors on a contract naming a nonexistent
# package. C4/C3 are estimated from the roadmap concept described in
# CLAUDE.md (adapters arrive once there is more than one adapter to keep
# independent; plugin isolation once plugins/* is a real workspace
# member) and should be corrected against docs/architecture/roadmap.md
# once that document lands -- pushed forward, not implemented early,
# since neither package (per-adapter subpackages, a real plugins/*
# member) exists on disk yet. C5 (ui privilege) was one such estimate
# too, until WP-24 made jarvis.ui real and configured it for real
# below, which is why C5's number was corrected down to when that
# concretely happened rather than left at its original guess.
CONTRACT_SCHEDULE: dict[str, int] = {
    "C1 layered architecture": 1,
    "C2 domain purity": 1,
    "C6 no GLib in the core": 1,
    "C7 plugin_api depends only on domain": 1,
    "C5 ui privilege": 24,
    "C4 adapter independence": 30,
    "C3 plugin isolation": 30,
}


def _configured_contract_names() -> set[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    contracts = data["tool"]["importlinter"]["contracts"]
    return {contract["name"] for contract in contracts}


def test_configured_contracts_match_schedule() -> None:
    """Configured contracts must be exactly those due by the current work package.

    Fails in both directions: a contract missing though it is due is a
    regression; a contract present before its package exists is a
    landmine for the next ``uv run lint-imports`` invocation.
    """
    due = {
        name
        for name, work_package in CONTRACT_SCHEDULE.items()
        if work_package <= CURRENT_WORK_PACKAGE
    }
    assert _configured_contract_names() == due


def test_ci_invokes_every_gate() -> None:
    """The CI workflow must actually run every gate listed in CLAUDE.md."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    required_snippets = (
        "ruff check",
        "ruff format --check",
        "mypy --strict",
        "lint-imports",
        "pytest",
        'coverage report --include="src/jarvis/domain/*"',
        'coverage report --include="src/jarvis/application/policy/*"',
    )
    for snippet in required_snippets:
        assert snippet in text, f"CI workflow is missing gate: {snippet!r}"


def test_ci_uses_locked_sync() -> None:
    """CI must install dependencies with ``uv sync --locked`` (no silent drift)."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "uv sync --locked" in text


def test_ci_matrix_covers_both_supported_python_versions() -> None:
    """CI must test both Python 3.12 and 3.13."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "3.12" in text
    assert "3.13" in text
