"""Unit tests for jarvis.adapters.validation.build.BuildValidator.

Nothing is mocked: a real LocalWorkspaceAdapter applies a real patch,
and ``sys.executable`` runs a real subprocess -- matching
``adapters/workspace.py``'s own reasoning for why this is safe here.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from jarvis.adapters.validation.build import BuildValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.domain.evidence import Candidate, Verdict

if TYPE_CHECKING:
    from pathlib import Path

_PATCH = "--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-original\n+patched\n"


async def test_validate_passes_when_the_patch_applies_and_the_build_exits_zero(
    tmp_path: Path,
) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = BuildValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(0)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, evidence = await validator.validate(candidate)

    assert verdict == Verdict.PASSED
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "patched\n"
    assert evidence[0].author == "build"


async def test_validate_fails_when_the_build_exits_nonzero(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")
    validator = BuildValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(1)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, _evidence = await validator.validate(candidate)

    assert verdict == Verdict.FAILED


async def test_validate_reports_unverifiable_when_the_patch_does_not_apply(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("nothing like the patch context\n", encoding="utf-8")
    validator = BuildValidator(
        LocalWorkspaceAdapter(tmp_path), command=(sys.executable, "-c", "import sys; sys.exit(0)")
    )
    candidate = Candidate(author="local", content=_PATCH)

    verdict, _evidence = await validator.validate(candidate)

    assert verdict == Verdict.UNVERIFIABLE
