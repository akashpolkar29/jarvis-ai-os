"""Unit tests for jarvis.adapters.validation.user_script.UserScriptValidator.

Nothing is mocked -- see test_build.py's module docstring for why.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from jarvis.adapters.validation.user_script import UserScriptValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.domain.evidence import Candidate, Verdict

if TYPE_CHECKING:
    from pathlib import Path

_PATCH = "--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-original\n+patched\n"


async def test_validate_passes_when_the_patch_applies_and_the_script_exits_zero(
    tmp_path: Path,
) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = UserScriptValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(0)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, evidence = await validator.validate(candidate)

    assert verdict == Verdict.PASSED
    assert evidence[0].author == "user_script"


async def test_validate_fails_when_the_script_exits_nonzero(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = UserScriptValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(1)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, _evidence = await validator.validate(candidate)

    assert verdict == Verdict.FAILED
