"""WP-73's own required real proof: the real target repository stays untouched.

ADR-0055's "Amendment 2026-09-01" found that ``Dispatcher.run()`` calls
``WorkspacePort.apply_patch`` internally, unconditionally, with no seam
a wrapper could intercept before that write happens. This test proves
the fix directly, not inferred: a real ``Dispatcher`` (wired exactly
like ``tests/integration/test_cassette_replay.py``'s own real
``Dispatcher``/``EscalationLadder``/``Arbiter``/``ModelRouter``), a
real ``PytestValidator``, and a real ``LocalWorkspaceAdapter`` --
constructed not against the real target repository, but against a
:func:`~jarvis.application.coding.sandbox_workspace.make_disposable_workspace`
copy of it. After a full ``Dispatcher.run()`` call that really applies
a real patch and really runs real pytest, the real target repository's
own file is asserted, directly against the filesystem, to be byte-for-
byte unchanged -- not inferred from the disposable copy's own state,
which is asserted separately to have genuinely changed (proving the
mechanism did something real, not that nothing happened at all).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.application.coding.sandbox_workspace import make_disposable_workspace
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung, Verdict
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile, TaskBudget
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=True
)

_ORIGINAL_WIDGET_CONTENT = 'VALUE = "ORIGINAL"\n'
_PATCHED_WIDGET_CONTENT = 'VALUE = "PATCHED"\n'
_PASSING_TEST_CONTENT = (
    "from widget import VALUE\n\n\ndef test_value() -> None:\n    assert VALUE == 'PATCHED'\n"
)
_REAL_PATCH = (
    "--- a/widget.py\n"
    "+++ b/widget.py\n"
    "@@ -1 +1 @@\n"
    f"-{_ORIGINAL_WIDGET_CONTENT.rstrip(chr(10))}\n"
    f"+{_PATCHED_WIDGET_CONTENT.rstrip(chr(10))}\n"
)


class _FixedPatchReasoningProvider:
    """A minimal, test-local ReasoningPort always returning the same real, fixed patch."""

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        candidate = Candidate(author="local", content=_REAL_PATCH)
        return Tainted(candidate, Provenance.system())


def _make_real_target_repo(root: Path) -> None:
    (root / "widget.py").write_text(_ORIGINAL_WIDGET_CONTENT, encoding="utf-8")
    (root / "test_widget.py").write_text(_PASSING_TEST_CONTENT, encoding="utf-8")


async def test_dispatcher_run_against_a_disposable_workspace_leaves_the_real_repository_untouched(
    tmp_path: Path,
) -> None:
    real_target = tmp_path / "real_target_repo"
    real_target.mkdir()
    _make_real_target_repo(real_target)

    disposable = make_disposable_workspace(
        BwrapSandboxAdapter(), real_target, LocalWorkspaceAdapter
    )
    try:
        validator = PytestValidator(disposable.workspace)
        router = ModelRouter(
            AuthorizationOrchestrator(
                AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter()
            )
        )
        dispatcher = Dispatcher(
            EscalationLadder(),
            Arbiter(),
            router,
            validator,
            {EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, _FixedPatchReasoningProvider()),)},
        )
        task = Tainted(
            "fix the failing test",
            Provenance(
                trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
            ),
        )

        result = await dispatcher.run(task, TaskBudget(limit=10), _FULL_CONFIRMATION)

        # The real safety property WP-73 exists to guarantee: the real target
        # repository's own file, checked directly against the filesystem, is
        # completely unmodified -- Dispatcher.run() never saw its path at all.
        assert (real_target / "widget.py").read_text(encoding="utf-8") == _ORIGINAL_WIDGET_CONTENT

        # And the mechanism genuinely did something: the disposable copy
        # really was patched and really passed real pytest, proving this
        # isn't just "nothing happened" -- Dispatcher really ran, for real.
        self_repair_attempt = next(
            attempt for attempt in result.attempts if attempt.rung is EscalationRung.SELF_REPAIR
        )
        assert self_repair_attempt.verdict is Verdict.PASSED
        assert (disposable.workspace.root() / "widget.py").read_text(
            encoding="utf-8"
        ) == _PATCHED_WIDGET_CONTENT
    finally:
        disposable.close()
