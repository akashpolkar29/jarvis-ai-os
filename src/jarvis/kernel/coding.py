"""The composition root for coding.run_task: WP-71's coding-loop wrapper, made invocable.

:func:`authorize_and_run_coding_task` is the first point a real coding
task can be run against a real target repository as an actual,
invocable capability -- mirroring
:func:`~jarvis.kernel.browser.authorize_and_open_page`'s own
registry/storage/confirmation/orchestrator wiring exactly:
``orchestrator.authorize_by_id()`` first, the real side effect only
ever inside ``if decision.granted:``, ``storage.save(chain)`` in a
``finally`` block so a granted decision is never lost even if
``run_coding_task`` itself raises.

**``coding.run_task`` is a static, fixed-effect capability**
(``Effect.EXECUTE``, ``Tier.CONFIRM`` -- ``kernel/capabilities.py``),
the outer gate on invoking the coding agent *at all* against a real
repository -- the same "ask first" tier ``browser.open_page``/
``docker.stop_container`` already use for a real, consequential but
recoverable action. **This is deliberately a second, separate
authorization layer from ``run_coding_task``'s own internal, per-write
``CodeWriteAuthorizer`` calls (WP-70/WP-71/ADR-0056), not a
replacement for them** -- a granted ``coding.run_task`` only means "the
coding agent may run"; whether any specific write it eventually
proposes is itself granted is decided later, independently, per touched
path, exactly as ``run_coding_task`` already implements. Both
authorizations share one orchestrator (and therefore one audit chain)
constructed here, so every real decision this one call makes --
the outer gate, every provider-call authorization inside `Dispatcher`,
and every per-path write authorization -- lands in the same,
single, tamper-evident record.

**Updated 2026-09-04: ``dispatcher_factory`` now has a real, local-only
default** -- :func:`_local_only_dispatcher_factory`, unchanged in
shape, is what a ``None`` argument resolves to. This is a real,
deliberate widening of what was previously stated here as "no default,
on purpose," made on the user's own direct instruction after
independently re-reading this exact module: the original reasoning
conflated two separate questions -- "should a real *cloud-provider*
default be invented here" (still, correctly, no -- see below) and
"should *any* default exist at all" (the local-only option was already
real, honest, and credential-free; leaving it unused as a default was
the real gap this update closes). **What remains unchanged**: which
real ``ReasoningPort`` providers service ``SELF_REPAIR``/``SECOND_PROVIDER``
(`application/reasoning/dispatcher.py`'s own docstring: "an injected,
overridable choice, not a global policy") was never decided anywhere in
this codebase's real ADRs for the *cloud* case, and inventing a real
default cloud-provider assignment here -- which vendor-family adapter,
which model, which keyring secret reference -- remains new, undecided
policy this codebase does not make. A caller that wants real
``SECOND_PROVIDER`` cloud escalation still supplies its own explicit
``dispatcher_factory``, overriding the local-only default -- this is
additive, not a narrowing of what was already possible.
:func:`_local_only_dispatcher_factory` is a real ``LocalReasoningAdapter``
at ``SELF_REPAIR`` alone, nothing registered at ``SECOND_PROVIDER`` --
a valid, real outcome ``Dispatcher.__init__``'s own docstring already
documents ("An empty or missing entry for a rung means no provider is
tried there at all"). **Real, honest trade-off, stated plainly, not
hidden**: local-model output quality is materially unproven relative to
a cloud provider's -- ``adapters/reasoning/local.py``'s own docstring
already names the real, structurally-complete-but-live-unverified
status this default inherits; a caller invoking this default gets
whatever a real, local Ollama-compatible server at ``localhost:11434``
actually produces, not a guaranteed-competent result.

**``sandbox``/``workspace_factory`` do have real defaults**
(``BwrapSandboxAdapter()``/``LocalWorkspaceAdapter``) -- unlike the
provider-assignment question above, there is exactly one real adapter
each in this codebase, with no policy ambiguity to invent, the same
"real default, overridable for tests" shape
``browser_automation``/``embedding_port`` already use elsewhere in this
ring.

**No voice grammar added in this pass** -- checked directly against
``kernel/intent.py`` first, not assumed: no established, obvious
precedent exists to mirror. ``memory.write`` is the one capability with
real voice wiring (ADR-0053's own explicit commitment); every other
static capability added since, including all four of WP-67-69's
``browser.*`` capabilities and M4's ``memory.pin``/``memory.forget``,
was left kernel-level only. ``coding.run_task`` follows that same,
larger precedent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.reasoning.local import PROFILE as LOCAL_PROVIDER_PROFILE
from jarvis.adapters.reasoning.local import LocalReasoningAdapter
from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.application.coding.loop import (
    DEFAULT_MAX_CLIMBS,
    CodingLoopDependencies,
    CodingTaskRequest,
    run_coding_task,
)
from jarvis.application.coding.writer import CodeWriteAuthorizer
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.evidence import EscalationRung
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import CODING_RUN_TASK_CAPABILITY_ID, build_default_registry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.coding.loop import CodingLoopResult, DispatcherFactory, WorkspaceFactory
    from jarvis.domain.policy import Decision
    from jarvis.ports.sandbox import SandboxPort
    from jarvis.ports.workspace import WorkspacePort


def _local_only_dispatcher_factory(orchestrator: AuthorizationOrchestrator) -> DispatcherFactory:
    """Build a real, credential-free DispatcherFactory: local provider only, no cloud escalation.

    This module's own real default (2026-09-04) when no
    `dispatcher_factory` is supplied -- also exported for a real caller
    to reuse directly, or as a starting point for a caller that wants
    to add its own SECOND_PROVIDER entries around the same real
    ladder/arbiter/router shape.
    """

    def _build(workspace: WorkspacePort) -> Dispatcher:
        router = ModelRouter(orchestrator)
        validator = PytestValidator(workspace)
        providers = {
            EscalationRung.SELF_REPAIR: ((LOCAL_PROVIDER_PROFILE, LocalReasoningAdapter()),)
        }
        return Dispatcher(EscalationLadder(), Arbiter(), router, validator, providers)

    return _build


async def authorize_and_run_coding_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task: str,
    target_repo: Path,
    dispatcher_factory: DispatcherFactory | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    sandbox: SandboxPort | None = None,
    workspace_factory: WorkspaceFactory | None = None,
    max_climbs: int = DEFAULT_MAX_CLIMBS,
    protected_patterns: tuple[str, ...] | None = None,
    include_referenced_file_context: bool = False,
) -> tuple[Decision, CodingLoopResult | None]:
    """Wire up the stack, authorize invoking the coding agent, and run it only if granted.

    Args:
        task: The coding task's own plain-text description, typed or
            spoken directly by the user -- wrapped as
            ``Tainted(task, Provenance.user())``, matching every other
            directly-typed/spoken argument in this codebase.
        target_repo: The real target repository. Never touched by
            `Dispatcher.run()` itself (WP-73's disposable-workspace
            mechanism) -- only ever written to, at most once, by
            `run_coding_task`'s own final, separately authorized write.
        dispatcher_factory: Builds a real, fully-wired `Dispatcher`
            per climb. Defaults to `_local_only_dispatcher_factory`
            (a real, credential-free, local-model-only `Dispatcher`) --
            see module docstring for why only the *local* default
            exists, not a cloud one. Pass an explicit factory to use a
            real cloud provider instead.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            `ManualConfirmationAdapter`.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        sandbox: The real `SandboxPort` used to make each climb's own
            disposable workspace copy. Defaults to a real
            `BwrapSandboxAdapter`.
        workspace_factory: Builds a real `WorkspacePort` given a root
            directory. Defaults to `LocalWorkspaceAdapter`.
        max_climbs: The real, finite ceiling on how many full
            `Dispatcher.run()` climbs this task may attempt. Defaults
            to `run_coding_task`'s own `DEFAULT_MAX_CLIMBS`.
        protected_patterns: A real, explicit override for which paths
            are protected. `None` resolves them for real from
            `target_repo`'s own detected test convention.
        include_referenced_file_context: Real, opt-in (default
            `False`, preserving every existing caller's exact prior
            behavior) file-context injection -- see
            `CodingTaskRequest`'s own docstring for what this does and
            does not do (M7 code-context design,
            `application/coding/context.py`).

    Returns:
        `(decision, result)` -- `decision` is the outer `coding.run_task`
        gate's own real `Decision`, always durably appended to the
        chain at `chain_path` by the time this returns. `result` is
        `run_coding_task`'s own real `CodingLoopResult` if the outer
        gate was granted, `None` if denied -- the coding agent never
        runs at all on a denied outer gate, not even its first climb.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        CODING_RUN_TASK_CAPABILITY_ID,
        Tainted({"target_repo": str(target_repo), "task": task}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    result: CodingLoopResult | None = None
    try:
        if decision.granted:
            dependencies = CodingLoopDependencies(
                sandbox=sandbox or BwrapSandboxAdapter(),
                workspace_factory=workspace_factory or LocalWorkspaceAdapter,
                dispatcher_factory=dispatcher_factory
                or _local_only_dispatcher_factory(orchestrator),
                authorizer=CodeWriteAuthorizer(orchestrator),
            )
            request = CodingTaskRequest(
                task=Tainted(task, Provenance.user()),
                target_repo=target_repo,
                context=orchestrator.get_current_context(),
                max_climbs=max_climbs,
                protected_patterns=protected_patterns,
                include_referenced_file_context=include_referenced_file_context,
            )
            result = await run_coding_task(request, dependencies)
    finally:
        storage.save(chain)

    return decision, result
