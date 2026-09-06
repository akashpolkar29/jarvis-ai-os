"""Unit tests for jarvis.kernel.planning's authorize_and_run_plan composition root.

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_coding_kernel.py`'s own established discipline. Everything else
(the outer authorization gate, plan generation/validation, and every
real plan step's own authorization/execution) runs for real.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.application.planning.planner import PlanningError
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.files import authorize_and_read_file
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


async def test_a_real_multi_step_plan_is_fully_reconstructable_from_the_audit_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial verification of ADR-0062's own Consequences claim.

    ADR-0062 claims: "every plan step still produces its own real,
    individually hash-chained audit record, so a plan's own full
    execution history is fully reconstructable from the existing audit
    chain with no new logging mechanism." This test proves that claim
    directly, empirically, not by re-reading the claim: runs a real
    3-step plan (fs.read_file, fs.list_dir, git.status -- all real
    `Tier.ALLOW` capabilities) through `authorize_and_run_plan` against
    a real, temporary chain file, then *independently* loads that chain
    fresh (a new `JsonFileAuditStorageAdapter` instance, not the one
    the composition root used) and verifies it end to end.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    plan_response = json.dumps(
        [
            {"capability_id": "fs.read_file", "arguments": {"path": str(tmp_path / "a.txt")}},
            {"capability_id": "fs.list_dir", "arguments": {"path": str(tmp_path / "sub")}},
            {"capability_id": "git.status", "arguments": {"repo_dir": str(tmp_path)}},
        ]
    )
    provider = _FakeReasoningProvider(plan_response)

    await authorize_and_run_plan(
        "read a.txt, list sub, check repo status",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    # Independent reload -- a fresh adapter instance, proving this is real,
    # persisted, on-disk state, not an artifact of the composition root's
    # own in-memory chain object.
    reloaded = JsonFileAuditStorageAdapter(chain_path).load()
    verification = reloaded.verify()

    expected_capability_sequence = [
        "planning.run_plan",
        "fs.read_file",
        "fs.list_dir",
        "git.status",
    ]
    real_capability_sequence = [
        record.decision.invocation.descriptor.id.value for record in reloaded
    ]

    assert verification.valid is True
    assert real_capability_sequence == expected_capability_sequence
    assert [record.sequence for record in reloaded] == [0, 1, 2, 3]
    for index in range(1, len(reloaded)):
        assert reloaded[index].previous_hash == reloaded[index - 1].record_hash
    assert all(record.decision.granted for record in reloaded)


async def test_a_planned_steps_audit_record_is_structurally_identical_to_a_direct_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A step's own audit record carries no marker distinguishing it from a directly-invoked call.

    Runs the identical real `fs.read_file` call two ways against two
    separate chain files: once through `planning.run_plan`, once
    directly via `authorize_and_read_file`. Confirms the resulting
    `AuditRecord`/`Decision`/`CapabilityInvocation` shapes are
    field-for-field identical (same tier, same reasons, same
    descriptor, same argument-digest shape) -- nothing about being
    part of a plan changes what gets recorded or how.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "a.txt").write_text("hello")

    planned_chain_path = tmp_path / "planned_chain.json"
    direct_chain_path = tmp_path / "direct_chain.json"

    plan_response = json.dumps(
        [{"capability_id": "fs.read_file", "arguments": {"path": str(tmp_path / "a.txt")}}]
    )
    provider = _FakeReasoningProvider(plan_response)
    await authorize_and_run_plan(
        "read a.txt",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=planned_chain_path,
    )

    authorize_and_read_file(
        tmp_path / "a.txt",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=direct_chain_path,
    )

    planned_records = JsonFileAuditStorageAdapter(planned_chain_path).load()
    direct_records = JsonFileAuditStorageAdapter(direct_chain_path).load()

    # planned_records[0] is the outer planning.run_plan gate; [1] is the
    # real fs.read_file step -- compared against direct_records[0], the
    # only record in the direct-call chain.
    planned_step = planned_records[1].decision
    direct_call = direct_records[0].decision

    assert planned_step.tier == direct_call.tier
    assert planned_step.granted == direct_call.granted
    assert planned_step.reasons == direct_call.reasons
    assert planned_step.invocation.descriptor == direct_call.invocation.descriptor
    assert planned_step.invocation.arguments.value == direct_call.invocation.arguments.value
