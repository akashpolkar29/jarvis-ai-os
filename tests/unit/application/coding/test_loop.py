"""Unit tests for the pure/near-pure helpers inside jarvis.application.coding.loop.

The real, multi-component safety properties (finite retry budget,
all-or-nothing protected-path rejection, exactly-one-real-write) are
proven end-to-end in `tests/integration/test_coding_loop.py` -- these
tests cover `_seed_next_climb_task`'s and `_authorize_patch_write`'s
own edge-case branches directly, matching this codebase's own
precedent for testing private, pure helpers in isolation
(`adapters/sandbox.py`'s `_build_bwrap_argv`, tested directly in
`tests/unit/adapters/test_sandbox.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.coding.loop import _authorize_patch_write, _seed_next_climb_task
from jarvis.application.reasoning.dispatcher import DispatchResult
from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import TaskBudget

if TYPE_CHECKING:
    from pathlib import Path


def _task() -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted("original task", provenance)


def test_seeding_with_no_attempts_at_all_returns_the_task_unchanged() -> None:
    """An immediately budget-exhausted climb has zero attempts -- nothing to feed back."""
    empty_result = DispatchResult(attempts=(), budget=TaskBudget(limit=0))

    seeded = _seed_next_climb_task(_task(), empty_result)

    assert seeded.value == "original task"


def test_seeding_with_attempts_that_have_no_evidence_returns_the_task_unchanged() -> None:
    """The DETERMINISTIC_FIX stub attempt has empty evidence -- still nothing real to feed back."""
    candidate = Candidate(author="dispatcher", content="stub")
    stub_only = DispatchResult(
        attempts=(
            Attempt(
                rung=EscalationRung.DETERMINISTIC_FIX,
                candidate=candidate,
                evidence=(),
                verdict=Verdict.FAILED,
            ),
        ),
        budget=TaskBudget(limit=2),
    )

    seeded = _seed_next_climb_task(_task(), stub_only)

    assert seeded.value == "original task"


def test_seeding_with_real_evidence_appends_it_to_the_task_and_keeps_provenance() -> None:
    candidate = Candidate(author="local", content="a patch")
    evidence = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT,
        author="pytest",
        weight=1.0,
        description="pytest exited 1.",
    )
    failed = DispatchResult(
        attempts=(
            Attempt(
                rung=EscalationRung.SELF_REPAIR,
                candidate=candidate,
                evidence=(evidence,),
                verdict=Verdict.FAILED,
            ),
        ),
        budget=TaskBudget(limit=2),
    )
    original = _task()

    seeded = _seed_next_climb_task(original, failed)

    assert "original task" in seeded.value
    assert "pytest exited 1." in seeded.value
    assert seeded.provenance == original.provenance


def test_authorize_patch_write_returns_none_for_a_patch_touching_no_real_paths(
    tmp_path: Path,
) -> None:
    # authorizer/context are never actually reached -- the function short-circuits
    # before touching either -- so a real instance of each is not needed here.
    result = _authorize_patch_write(
        authorizer=None,  # type: ignore[arg-type]
        repo_root=tmp_path,
        patch="not a real diff at all",
        protected_patterns=(),
        context=None,  # type: ignore[arg-type]
    )

    assert result is None


def test_authorize_patch_write_returns_none_when_a_touched_path_escapes_the_repo(
    tmp_path: Path,
) -> None:
    escaping_patch = "--- a/../../etc/passwd\n+++ b/../../etc/passwd\n@@ -1 +1 @@\n-a\n+b\n"

    # authorizer/context are never actually reached -- see the test above.
    result = _authorize_patch_write(
        authorizer=None,  # type: ignore[arg-type]
        repo_root=tmp_path,
        patch=escaping_patch,
        protected_patterns=(),
        context=None,  # type: ignore[arg-type]
    )

    assert result is None
