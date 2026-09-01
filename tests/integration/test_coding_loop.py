"""WP-71's own required real proofs: the coding-loop wrapper's safety properties.

Every test here wires a real `Dispatcher`/`EscalationLadder`/`Arbiter`/
`ModelRouter`/`PytestValidator`/`LocalWorkspaceAdapter`/`BwrapSandboxAdapter`
-- matching `test_dispatcher_against_disposable_workspace.py`'s (WP-73)
own real-components discipline. Only the `ReasoningPort` provider is
faked, since it is the actual external-service boundary this whole
system exists to abstract over -- the same "fake only the true I/O
edge" precedent `tests/unit/application/reasoning/test_dispatcher.py`
and `tests/integration/test_cassette_replay.py` both already establish.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.application.coding.loop import (
    CodingLoopDependencies,
    CodingLoopOutcome,
    CodingTaskRequest,
    run_coding_task,
)
from jarvis.application.coding.writer import CodeWriteAuthorizer
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.coding.loop import DispatcherFactory
    from jarvis.domain.evidence import Attempt
    from jarvis.ports.reasoning import ReasoningPort
    from jarvis.ports.workspace import WorkspacePort

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=True
)
_PROTECTED_PATTERNS = ("test_*.py", "*_test.py", "tests/*")
_EXHAUSTED_MAX_CLIMBS = 2
_TWO_TOUCHED_PATHS = 2
_TWO_CLIMBS_TO_SUCCEED = 2

_ORIGINAL_WIDGET_CONTENT = 'VALUE = "ORIGINAL"\n'
_PATCHED_WIDGET_CONTENT = 'VALUE = "PATCHED"\n'
_WRONG_WIDGET_CONTENT = 'VALUE = "WRONG"\n'
_FAILING_TEST_CONTENT = (
    "from widget import VALUE\n\n\ndef test_value() -> None:\n    assert VALUE == 'PATCHED'\n"
)

_WRONG_PATCH = (
    "--- a/widget.py\n"
    "+++ b/widget.py\n"
    "@@ -1 +1 @@\n"
    f"-{_ORIGINAL_WIDGET_CONTENT.rstrip(chr(10))}\n"
    f"+{_WRONG_WIDGET_CONTENT.rstrip(chr(10))}\n"
)
_CORRECT_PATCH = (
    "--- a/widget.py\n"
    "+++ b/widget.py\n"
    "@@ -1 +1 @@\n"
    f"-{_ORIGINAL_WIDGET_CONTENT.rstrip(chr(10))}\n"
    f"+{_PATCHED_WIDGET_CONTENT.rstrip(chr(10))}\n"
)
# Verified live against a real `git apply` before use here (see this work
# package's own commit message) -- touches BOTH widget.py (an ordinary
# path) and test_widget.py (a protected path under _PROTECTED_PATTERNS),
# and, if applied, leaves both real pytest tests passing.
_TWO_FILE_WINNING_PATCH = (
    "--- a/widget.py\n"
    "+++ b/widget.py\n"
    "@@ -1 +1 @@\n"
    '-VALUE = "ORIGINAL"\n'
    '+VALUE = "PATCHED"\n'
    "--- a/test_widget.py\n"
    "+++ b/test_widget.py\n"
    "@@ -1,5 +1,9 @@\n"
    " from widget import VALUE\n"
    " \n"
    " \n"
    " def test_value() -> None:\n"
    "     assert VALUE == 'PATCHED'\n"
    "+\n"
    "+\n"
    "+def test_value_is_string() -> None:\n"
    "+    assert isinstance(VALUE, str)\n"
)


def _make_real_target_repo(root: Path) -> None:
    (root / "widget.py").write_text(_ORIGINAL_WIDGET_CONTENT, encoding="utf-8")
    (root / "test_widget.py").write_text(_FAILING_TEST_CONTENT, encoding="utf-8")


class _AlwaysWrongProvider:
    """A minimal, test-local ReasoningPort that never produces a passing candidate."""

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        candidate = Candidate(author="local", content=_WRONG_PATCH)
        return Tainted(candidate, Provenance.system())


class _TwoFileWinningProvider:
    """A minimal, test-local ReasoningPort whose one candidate touches two real files."""

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        candidate = Candidate(author="local", content=_TWO_FILE_WINNING_PATCH)
        return Tainted(candidate, Provenance.system())


class _FlakyThenPassingProvider:
    """A minimal, test-local ReasoningPort: wrong on its first call, correct after.

    Real, stateful proof that the *wrapper's own* retry (not
    `Dispatcher`'s internal rung escalation) is what makes a second
    climb see a different candidate -- the same provider instance is
    reused, unmodified, across every climb `dispatcher_factory` builds.
    """

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        self.call_count += 1
        content = _WRONG_PATCH if self.call_count == 1 else _CORRECT_PATCH
        return Tainted(Candidate(author="local", content=content), Provenance.system())


def _dispatcher_factory_for(provider: ReasoningPort) -> DispatcherFactory:
    def _build(workspace: WorkspacePort) -> Dispatcher:
        router = ModelRouter(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))
        validator = PytestValidator(workspace)
        providers = {EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, provider),)}
        return Dispatcher(EscalationLadder(), Arbiter(), router, validator, providers)

    return _build


def _dependencies_for(provider: ReasoningPort) -> CodingLoopDependencies:
    authorizer = CodeWriteAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))
    return CodingLoopDependencies(
        sandbox=BwrapSandboxAdapter(),
        workspace_factory=LocalWorkspaceAdapter,
        dispatcher_factory=_dispatcher_factory_for(provider),
        authorizer=authorizer,
    )


def _task() -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted("fix the failing test", provenance)


async def test_a_fully_exhausted_retry_budget_stops_and_reports_it(tmp_path: Path) -> None:
    """Required test (item 3): the wrapper actually stops at the real, finite budget."""
    real_target = tmp_path / "real_target_repo"
    real_target.mkdir()
    _make_real_target_repo(real_target)

    request = CodingTaskRequest(
        _task(),
        real_target,
        _FULL_CONFIRMATION,
        max_climbs=_EXHAUSTED_MAX_CLIMBS,
        protected_patterns=_PROTECTED_PATTERNS,
    )

    result = await run_coding_task(request, _dependencies_for(_AlwaysWrongProvider()))

    assert result.outcome is CodingLoopOutcome.RETRY_BUDGET_EXHAUSTED
    assert len(result.climbs) == _EXHAUSTED_MAX_CLIMBS


async def test_a_fully_exhausted_retry_budget_leaves_the_real_repository_untouched(
    tmp_path: Path,
) -> None:
    """Required test: exhaustion never writes to the real repo, even partially."""
    real_target = tmp_path / "real_target_repo"
    real_target.mkdir()
    _make_real_target_repo(real_target)

    request = CodingTaskRequest(
        _task(),
        real_target,
        _FULL_CONFIRMATION,
        max_climbs=_EXHAUSTED_MAX_CLIMBS,
        protected_patterns=_PROTECTED_PATTERNS,
    )

    result = await run_coding_task(request, _dependencies_for(_AlwaysWrongProvider()))

    assert result.outcome is CodingLoopOutcome.RETRY_BUDGET_EXHAUSTED
    assert (real_target / "widget.py").read_text(encoding="utf-8") == _ORIGINAL_WIDGET_CONTENT
    assert (real_target / "test_widget.py").read_text(encoding="utf-8") == _FAILING_TEST_CONTENT


async def test_a_winning_patch_touching_one_protected_path_is_rejected_wholesale(
    tmp_path: Path,
) -> None:
    """Required test (item 4): all-or-nothing -- rejected entirely, not partially applied."""
    real_target = tmp_path / "real_target_repo"
    real_target.mkdir()
    _make_real_target_repo(real_target)

    request = CodingTaskRequest(
        _task(), real_target, _FULL_CONFIRMATION, protected_patterns=_PROTECTED_PATTERNS
    )

    result = await run_coding_task(request, _dependencies_for(_TwoFileWinningProvider()))

    assert result.outcome is CodingLoopOutcome.WRITE_DENIED
    # widget.py (granted) and test_widget.py (denied):
    assert len(result.write_decisions) == _TWO_TOUCHED_PATHS
    assert any(not decision.granted for decision in result.write_decisions)
    # Rejected wholesale: the ordinary file is untouched too, not just the protected one.
    assert (real_target / "widget.py").read_text(encoding="utf-8") == _ORIGINAL_WIDGET_CONTENT
    assert (real_target / "test_widget.py").read_text(encoding="utf-8") == _FAILING_TEST_CONTENT


async def test_the_wrapper_retries_and_writes_exactly_once_to_the_real_repo(
    tmp_path: Path,
) -> None:
    """Required end-to-end test: real retries, real PASSED, exactly one real write."""
    real_target = tmp_path / "real_target_repo"
    real_target.mkdir()
    _make_real_target_repo(real_target)
    provider = _FlakyThenPassingProvider()

    request = CodingTaskRequest(
        _task(), real_target, _FULL_CONFIRMATION, protected_patterns=_PROTECTED_PATTERNS
    )

    result = await run_coding_task(request, _dependencies_for(provider))

    assert result.outcome is CodingLoopOutcome.WRITTEN
    # climb 1 failed (wrong patch), climb 2 passed:
    assert len(result.climbs) == _TWO_CLIMBS_TO_SUCCEED
    assert provider.call_count == _TWO_CLIMBS_TO_SUCCEED
    assert (real_target / "widget.py").read_text(encoding="utf-8") == _PATCHED_WIDGET_CONTENT
    # Only widget.py was in the winning (single-file) patch -- the real
    # test file is untouched by this real write, proving it applied
    # exactly the winning candidate's own content, nothing more.
    assert (real_target / "test_widget.py").read_text(encoding="utf-8") == _FAILING_TEST_CONTENT
