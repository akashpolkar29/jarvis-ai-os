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

CURRENT_WORK_PACKAGE = 34

# Work package at which each import-linter contract becomes configurable.
# A contract can only be added once every package it names exists on
# disk — import-linter errors on a contract naming a nonexistent
# package. C3 is estimated from the roadmap concept described in
# CLAUDE.md (plugin isolation once plugins/* is a real workspace
# member) and should be corrected against docs/ROADMAP.md once its
# milestone plan is more concrete than a placeholder -- pushed forward,
# not implemented early, since that package (a real plugins/* member)
# does not exist on disk yet. C5 (ui privilege) was one such estimate
# too, until WP-24 made jarvis.ui real and configured it for real
# below, which is why C5's number was corrected down to when that
# concretely happened rather than left at its original guess. C4
# (adapter independence) is the same story, corrected down here: WP-32
# created jarvis.adapters.reasoning.{family_a,family_b,local} -- the
# first real per-adapter subpackage in this repo, and exactly the
# scenario C4 was written for -- and configured C4 in pyproject.toml in
# the same change, per the note that used to live here telling whoever
# built it to do exactly that. WP-33 extended C4's own modules list to
# also cover jarvis.adapters.validation's five sibling modules, the
# second per-adapter subpackage this repo's had -- same contract,
# still due at 32, just wider now.
CONTRACT_SCHEDULE: dict[str, int] = {
    "C1 layered architecture": 1,
    "C2 domain purity": 1,
    "C6 no GLib in the core": 1,
    "C7 plugin_api depends only on domain": 1,
    "C5 ui privilege": 24,
    "C4 adapter independence": 32,
    # Still a placeholder, pushed forward from 30 now that WP-32 has
    # passed and plugins/* still does not exist on disk -- M2 (through
    # WP-42) never creates it (see m2-reasoning-layer.md section 8:
    # "individual agent capability sets" are explicitly M5+). 50 is a
    # round, deliberately-past-M2 guess, correct this again once a real
    # milestone plan places plugins/* concretely.
    "C3 plugin isolation": 50,
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
        'coverage report --include="src/jarvis/application/reasoning/*"',
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
