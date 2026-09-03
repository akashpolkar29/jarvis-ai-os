"""Unit tests for jarvis.kernel.coding's authorize_and_run_coding_task composition root.

A fake ReasoningPort (with call tracking) is wired into a real
Dispatcher/EscalationLadder/Arbiter/ModelRouter/PytestValidator/
LocalWorkspaceAdapter/BwrapSandboxAdapter chain, mirroring
`tests/integration/test_coding_loop.py`'s own real-components
discipline -- only the true external-I/O edge (the reasoning provider)
is faked. `_local_only_dispatcher_factory` is tested structurally
here, without ever calling `.generate()` for real.

``test_real_default_dispatcher_factory_reaches_a_locally_running_ollama_server``
is the one real, live exception -- skipif-guarded on a real
reachability probe against ``localhost:11434``, mirroring
``tests/unit/adapters/reasoning/test_local.py``'s own identical guard.
Live-verified manually on this development machine 2026-09-04
(``qwen2.5:0.5b``): the real default genuinely reaches the real local
server -- the test only asserts a real, non-``None`` ``CodingLoopResult``
comes back, not that the tiny local model produces a *working* patch,
which is not a fair bar for a 0.5B-parameter model and not what this
test exists to prove.
"""

from __future__ import annotations

import urllib.request
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry
from jarvis.kernel.coding import _local_only_dispatcher_factory, authorize_and_run_coding_task

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.coding.loop import DispatcherFactory
    from jarvis.domain.evidence import Attempt
    from jarvis.ports.workspace import WorkspacePort


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError:
        return False
    return True


_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_NOT_A_REAL_PATCH = "this is not a real unified diff at all"


class _CountingProvider:
    """A minimal, test-local ReasoningPort that records every real call it receives."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        self.call_count += 1
        candidate = Candidate(author="local", content=_NOT_A_REAL_PATCH)
        return Tainted(candidate, Provenance.system())


def _fake_dispatcher_factory_for(
    provider: _CountingProvider, orchestrator: AuthorizationOrchestrator
) -> DispatcherFactory:
    def _build(workspace: WorkspacePort) -> Dispatcher:
        router = ModelRouter(orchestrator)
        validator = PytestValidator(workspace)
        providers = {EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, provider),)}
        return Dispatcher(EscalationLadder(), Arbiter(), router, validator, providers)

    return _build


async def test_granted_run_actually_invokes_the_coding_agent(tmp_path: Path) -> None:
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    chain_path = tmp_path / "audit_chain.json"
    provider = _CountingProvider()
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    decision, result = await authorize_and_run_coding_task(
        "fix the failing test",
        target_repo,
        _fake_dispatcher_factory_for(provider, orchestrator),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py", "tests/*"),
    )

    assert decision.granted is True
    assert result is not None
    assert provider.call_count == 1


async def test_denied_run_never_invokes_the_coding_agent_at_all(tmp_path: Path) -> None:
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    chain_path = tmp_path / "audit_chain.json"
    provider = _CountingProvider()
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    decision, result = await authorize_and_run_coding_task(
        "fix the failing test",
        target_repo,
        _fake_dispatcher_factory_for(provider, orchestrator),
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py", "tests/*"),
    )

    assert decision.granted is False
    assert result is None
    assert provider.call_count == 0


async def test_remote_confirmation_alone_is_sufficient_to_grant(tmp_path: Path) -> None:
    """coding.run_task is Effect.EXECUTE/Tier.CONFIRM -- remote confirmation alone suffices."""
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    provider = _CountingProvider()
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    decision, result = await authorize_and_run_coding_task(
        "fix the failing test",
        target_repo,
        _fake_dispatcher_factory_for(provider, orchestrator),
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py", "tests/*"),
    )

    assert decision.granted is True
    assert result is not None


async def test_a_single_granted_run_appends_a_verifiable_audit_record(tmp_path: Path) -> None:
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    chain_path = tmp_path / "audit_chain.json"
    provider = _CountingProvider()
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    await authorize_and_run_coding_task(
        "fix the failing test",
        target_repo,
        _fake_dispatcher_factory_for(provider, orchestrator),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py", "tests/*"),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) >= 1
    assert chain.verify().valid is True
    assert chain[0].decision.granted is True


def test_local_only_dispatcher_factory_registers_the_real_local_provider_alone() -> None:
    """No live call is made here -- see this module's own docstring for why."""
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())
    factory = _local_only_dispatcher_factory(orchestrator)

    dispatcher = factory(_DummyWorkspace())

    assert isinstance(dispatcher, Dispatcher)
    self_repair = dispatcher._providers.get(EscalationRung.SELF_REPAIR, ())
    second_provider = dispatcher._providers.get(EscalationRung.SECOND_PROVIDER, ())
    assert len(self_repair) == 1
    assert self_repair[0][0].name == "local"
    assert self_repair[0][0].is_local is True
    assert second_provider == ()


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, locally running Ollama server on localhost:11434, not assumed in CI.",
)
async def test_real_default_dispatcher_factory_reaches_a_locally_running_ollama_server(
    tmp_path: Path,
) -> None:
    """Omitting dispatcher_factory really reaches the real local model -- not a stub, not a skip."""
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()

    decision, result = await authorize_and_run_coding_task(
        "add a comment to the top of any file",
        target_repo,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py", "tests/*"),
    )

    assert decision.granted is True
    assert result is not None


class _DummyWorkspace:
    """A minimal, test-local WorkspacePort stand-in -- never actually used, just constructed."""

    def root(self) -> Path:
        raise NotImplementedError

    def apply_patch(self, patch: str) -> None:
        raise NotImplementedError
