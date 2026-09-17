"""WP-197: real security/regression hardening tests for the Job Search Assistant workflow.

Every property tested here was investigated directly against the real
code before writing a test for it (see each test's own docstring for
what was actually checked) -- this file proves already-true structural
properties, rather than building new mechanism, matching this queue's
own "improve only real deficiencies" instruction: no real deficiency
was found in memory/classification handling, halting, or parameter
validation, so nothing besides tests was added here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from jarvis.application.workflow.composer import WorkflowCompositionError
from jarvis.domain.capability import CapabilityId
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.kernel.memory import MemoryRecallOutcome
from jarvis.kernel.workflows import JOB_SEARCH_ASSISTANT_WORKFLOW_ID, authorize_and_run_workflow

if TYPE_CHECKING:
    from pathlib import Path

_VALID_PARAMETERS = {
    "profile_query": "job search preferences",
    "site": "linkedin",
    "keywords": "python",
    "location": "remote",
}


@pytest.mark.parametrize(
    ("physical_confirmation_available", "remote_confirmation_available"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_job_search_open_results_never_runs_regardless_of_confirmation(
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    tmp_path: Path,
) -> None:
    """No hidden browser action: job_search.open_results halts under every confirmation combination.

    Real, direct reason this holds structurally, not just empirically:
    `job_search.open_results` is not an entry in
    `kernel.capability_dispatch.PLAN_STEP_EXECUTORS` at all, so
    `compose_workflow` halts at it before any confirmation flag is
    even consulted for that step -- `execute_plan` never sees it,
    regardless of how permissive the caller's own confirmation
    arguments are.
    """
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall:
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        decision, outcome = authorize_and_run_workflow(
            JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
            _VALID_PARAMETERS,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=tmp_path / "chain.json",
        )

    if not decision.granted:
        # The outer planning.run_plan gate itself is Tier.CONFIRM -- only the
        # physical=True combinations reach composition at all; the others are
        # correctly denied before anything is composed, which is itself a real,
        # honest proof no browser action happened (nothing ran at all).
        assert outcome is None
        return
    assert outcome is not None
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("job_search.open_results")


def test_typo_d_parameter_for_job_search_assistant_is_rejected_not_silently_ignored(
    tmp_path: Path,
) -> None:
    """WP-194 regression, workflow-specific: a real typo in a job-search parameter is caught.

    Confirmed live before this queue's own WP-194 fix: a typo'd key
    for this exact workflow's own halted-step parameters
    (site/keywords/location) was previously silently accepted and
    never used at all. This proves the fix holds for the real,
    built-in workflow, not only a synthetic test fixture.
    """
    with pytest.raises(WorkflowCompositionError, match="siet"):
        authorize_and_run_workflow(
            JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
            {"profile_query": "ok", "siet": "linkedin", "keywords": "x", "location": "y"},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )


def test_recalled_memory_records_real_provenance_passes_through_unmodified(tmp_path: Path) -> None:
    """Provenance is preserved: the workflow engine never re-wraps or strips a recalled record.

    Uses a real `Tainted`/`Provenance`-carrying `MemoryRecord` (the
    exact shape `authorize_and_recall` itself returns) to prove the
    workflow layer passes `MemoryRecallOutcome` through as opaque,
    untouched step-result data -- identity-preserved, not copied or
    reconstructed -- exactly matching ADR-0050's own "never re-wrapped
    with a fresh, unclassified provenance" requirement.
    """
    real_provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PERSONAL, sources=frozenset()
    )
    real_record = MemoryRecord(
        identifier="mem:real-1",
        value=Tainted("prefers remote roles", real_provenance),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=None,
    )
    real_decision = Decision(
        tier=mock.Mock(),  # not inspected by this test
        granted=True,
        reasons=DecisionReason.BASE_TIER,
        invocation=mock.Mock(),
    )
    real_outcome = MemoryRecallOutcome(decision=real_decision, records=(real_record,))

    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall:
        fake_recall.return_value = real_outcome
        decision, outcome = authorize_and_run_workflow(
            JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
            _VALID_PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is True
    assert outcome is not None
    assert outcome.execution is not None
    recall_result = outcome.execution.step_records[0].result
    assert recall_result is real_outcome
    assert recall_result.records[0].value.provenance.classification == Classification.PERSONAL
    assert recall_result.records[0].value.value == "prefers remote roles"
