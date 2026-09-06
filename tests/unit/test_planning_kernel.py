"""Unit tests for jarvis.kernel.planning's authorize_and_run_plan composition root.

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_coding_kernel.py`'s own established discipline. Everything else
(the outer authorization gate, plan generation/validation, and every
real plan step's own authorization/execution) runs for real.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.application.planning.planner import PlanningError
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.planning import authorize_and_run_plan

if TYPE_CHECKING:
    import pytest

    from jarvis.domain.evidence import Attempt

_EXPECTED_RECORD_COUNT = 3


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed plan response."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[str] = []

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.calls.append(task)
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


async def test_denied_outer_gate_never_generates_a_plan(tmp_path: Path) -> None:
    """planning.run_plan is Tier.CONFIRM -- no confirmation means denied, and the provider is never called."""  # noqa: E501
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("[]")

    decision, result = await authorize_and_run_plan(
        "do something",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert decision.granted is False
    assert result is None
    assert provider.calls == []


async def test_granted_outer_gate_runs_a_real_multi_step_plan(tmp_path: Path) -> None:
    """A granted outer gate generates and runs a real plan against real, wired capabilities."""
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "a.txt").write_text("hello")
    plan_response = json.dumps(
        [{"capability_id": "fs.read_file", "arguments": {"path": str(tmp_path / "a.txt")}}]
    )
    provider = _FakeReasoningProvider(plan_response)

    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake:
        fake.return_value = mock.Mock(decision=mock.Mock(granted=True))

        decision, result = await authorize_and_run_plan(
            "read a.txt",
            provider,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    assert decision.granted is True
    assert result is not None
    assert result.aborted is False
    assert len(result.step_records) == 1
    fake.assert_called_once()


async def test_the_outer_decision_and_every_step_decision_are_all_persisted_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real regression test for a real bug caught during implementation.

    The outer gate's own decision must be saved to disk *before* the
    first real plan step's own, separately-constructed
    `authorize_and_*` call loads the same file -- otherwise that
    step's own save would never have seen the outer decision, and a
    naive final save of this function's own stale, outer-decision-only
    in-memory chain would then silently overwrite every step's own
    already-persisted record. This test proves the real, final
    on-disk chain contains all of it: the outer gate's own record,
    plus one real record per plan step.
    """
    # authorize_and_read_file is NOT mocked here, deliberately -- this test
    # exists specifically to prove real, on-disk chain persistence across
    # multiple, separately-constructed authorize_and_* calls, which a
    # mocked-away authorize_and_read_file would never exercise (a real
    # bug caught exactly this way while first writing this test: mocking
    # it away made every step a no-op that never touched chain_path at
    # all, silently passing for the wrong reason). fs.read_file's own
    # real allowed_root defaults to Path.home() -- monkeypatched to
    # tmp_path so real, scoped file reads succeed without needing a
    # real path under the real user's home directory.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    plan_response = json.dumps(
        [
            {"capability_id": "fs.read_file", "arguments": {"path": str(tmp_path / "a.txt")}},
            {"capability_id": "fs.read_file", "arguments": {"path": str(tmp_path / "b.txt")}},
        ]
    )
    provider = _FakeReasoningProvider(plan_response)

    await authorize_and_run_plan(
        "read both files",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    final_chain = JsonFileAuditStorageAdapter(chain_path).load()
    capability_ids = [record.decision.invocation.descriptor.id for record in final_chain]

    assert len(final_chain) == _EXPECTED_RECORD_COUNT
    assert capability_ids[0].value == "planning.run_plan"
    assert final_chain.verify().valid is True


async def test_a_planning_failure_still_leaves_the_outer_decision_persisted(
    tmp_path: Path,
) -> None:
    """A structurally-invalid plan raises, but the outer gate's own granted decision is not lost."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("not valid json")

    try:
        await authorize_and_run_plan(
            "do something",
            provider,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )
    except PlanningError:
        pass
    else:
        msg = "Expected PlanningError to propagate."
        raise AssertionError(msg)

    final_chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(final_chain) == 1
    assert final_chain.verify().valid is True
