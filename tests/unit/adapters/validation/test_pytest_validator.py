"""Unit tests for jarvis.adapters.validation.pytest_validator.PytestValidator.

Nothing is mocked -- see test_build.py's module docstring for why.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.domain.evidence import Candidate, Verdict

if TYPE_CHECKING:
    from pathlib import Path

_PATCH = "--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-original\n+patched\n"


async def test_validate_passes_when_the_patch_applies_and_pytest_exits_zero(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = PytestValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(0)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, evidence = await validator.validate(candidate)

    assert verdict == Verdict.PASSED
    assert evidence[0].author == "pytest"


async def test_validate_fails_when_pytest_exits_one(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = PytestValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(1)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, _evidence = await validator.validate(candidate)

    assert verdict == Verdict.FAILED


async def test_validate_reports_unverifiable_when_pytest_exits_five_no_tests_collected(
    tmp_path: Path,
) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = PytestValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(5)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, evidence = await validator.validate(candidate)

    assert verdict == Verdict.UNVERIFIABLE
    assert "no tests" in evidence[0].description.lower()
