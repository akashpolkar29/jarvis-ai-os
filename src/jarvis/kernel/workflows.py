"""The composition root for running a Workflow: WP-184, M9 workflow layer.

:func:`authorize_and_run_workflow` mirrors
:func:`~jarvis.kernel.planning.authorize_and_run_plan`'s own registry/
storage/confirmation/orchestrator wiring exactly: ``orchestrator.
authorize_by_id()`` first (the outer gate on running a workflow at
all), the real work only ever inside ``if decision.granted:``,
``storage.save(chain)`` in a ``finally`` block so a granted decision is
never lost even if composition or execution itself raises.

**No new ``CapabilityId``**: running a workflow reuses
``planning.run_plan``'s own outer gate completely unmodified -- a
workflow is a deterministic, hand-authored alternative to
``application/planning/planner.py::generate_plan``'s own reasoning-
generated step sequence, both producing the identical
``PlanStep`` type that flows into the identical, unmodified
``application/planning/executor.py::execute_plan``. Inventing a
separate ``workflow.run`` capability id here would describe the exact
same real action ("run a sequence of individually-authorized plan
steps") under a second name, which is not "genuinely necessary" per
this queue's own hard rule 21.

**Every runnable step is still individually authorized by
``execute_plan``, unmodified** -- this module never authorizes a
step itself, and never batches steps into one pre-approval. A step
this workflow cannot safely auto-run (unregistered capability, no
wired executor, or above ``Tier.ALLOW``) is never included in what
``execute_plan`` sees at all; see
``application/workflow/composer.py``'s own module docstring for the
full halting design.

:func:`build_default_workflow_registry` mirrors
:func:`~jarvis.kernel.skills.build_default_skill_registry` exactly:
one function registering every real, built-in workflow JARVIS
currently knows about.

**WP-185, Job Search Assistant -- the first real, built-in
workflow**: two real steps -- ``memory.retrieve`` (understand the
user's own stored profile/search-criteria context, ``Tier.ALLOW``,
runs automatically) then ``job_search.open_results`` (search
LinkedIn/Indeed via the user's own, real, ordinary browser,
``Tier.CONFIRM`` -- halts, exactly as every CONFIRM+ step must,
per ``application/workflow/composer.py``'s own halting design).
**Real, deliberately undocumented-as-steps capability gaps, named
here rather than worked around unsafely** (mirrors
``docs/OPEN_DECISIONS.md`` item 71's own already-documented finding):
no capability exists anywhere in this codebase to collect, normalize,
or de-duplicate job-search results, or to present them structurally --
every ``job_search.*`` capability is mechanically forbidden from
reading page content at all
(``tests/meta/test_job_search_no_content_reading.py``), by design, so
there is genuinely nothing safe to wire here; a human reads and picks
from the real browser window ``job_search.open_results`` opens.
Likewise, "create a task for later follow-up" is not a workflow step
here: task creation (``kernel.tasks.authorize_and_create_task``) is
built on ``memory.write``, a dynamic-effect capability deliberately
never statically registered (ADR-0049) -- it cannot be named by a
``WorkflowStep.capability_id`` at all, since
``validate_workflow_registry`` requires every step to name a real,
statically-registered capability. A caller wanting that follow-up
creates it separately, e.g. via ``jarvis task create``, after this
workflow halts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.planning.executor import execute_plan
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.workflow.composer import compose_workflow
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep
from jarvis.domain.workflow_registry import WorkflowRegistry, validate_workflow_registry
from jarvis.kernel.capabilities import (
    JOB_SEARCH_OPEN_RESULTS_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    PLANNING_RUN_PLAN_CAPABILITY_ID,
    build_default_registry,
)
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS

JOB_SEARCH_ASSISTANT_WORKFLOW_ID = WorkflowId("job_search_assistant")

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from jarvis.application.planning.executor import PlanExecutionResult
    from jarvis.application.workflow.composer import ComposedWorkflow
    from jarvis.domain.policy import Decision
    from jarvis.domain.registry import CapabilityRegistry


def build_default_workflow_registry(
    capabilities: CapabilityRegistry | None = None,
) -> WorkflowRegistry:
    """Build and return the real registry of every currently-known, built-in workflow.

    Args:
        capabilities: The capability registry to validate against.
            Defaults to ``build_default_registry()`` -- a real, live
            registry, not a synthetic one. Tests pass their own to
            validate against a deliberately smaller registry.

    Returns:
        A real, validated ``WorkflowRegistry``. Every registered
        workflow's every step is guaranteed, by
        ``validate_workflow_registry``, to name a real, registered
        capability.
    """
    registry = WorkflowRegistry()

    registry.register(
        WorkflowDescriptor(
            id=JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
            name="Job Search Assistant",
            description=(
                "Recall the user's own stored job-search profile/criteria, then open a "
                "real, assisted-browsing search on a permitted job site -- never reads or "
                "scrapes listing content, never applies automatically (ADR-0058)."
            ),
            steps=(
                WorkflowStep(
                    capability_id=MEMORY_RETRIEVE_CAPABILITY_ID,
                    arguments={"query": "${profile_query}", "limit": 5},
                    description=(
                        "Recall the user's own stored job-search profile/preferences/context."
                    ),
                ),
                WorkflowStep(
                    capability_id=JOB_SEARCH_OPEN_RESULTS_CAPABILITY_ID,
                    arguments={
                        "site": "${site}",
                        "keywords": "${keywords}",
                        "location": "${location}",
                    },
                    description=(
                        "Open a real search-results page on the requested site for the "
                        "user to search and read themselves -- Tier.CONFIRM, halts here; "
                        "this workflow never reads listing content, per "
                        "tests/meta/test_job_search_no_content_reading.py."
                    ),
                ),
            ),
            parameters=("profile_query", "site", "keywords", "location"),
            metadata={"source": "wp185-job-search-assistant"},
        )
    )

    real_capabilities = capabilities if capabilities is not None else build_default_registry()
    validate_workflow_registry(registry, real_capabilities)
    return registry


@dataclass(frozen=True)
class WorkflowRunOutcome:
    """The real, complete outcome of running one workflow.

    Attributes:
        workflow: The workflow descriptor that was run.
        composed: The real ``ComposedWorkflow`` -- which steps were
            runnable, and where (if anywhere) this workflow halted.
        execution: The real ``PlanExecutionResult`` for
            ``composed.runnable_steps``, or ``None`` if the workflow
            named zero runnable steps (e.g. it halts on its very
            first step).
    """

    workflow: WorkflowDescriptor
    composed: ComposedWorkflow
    execution: PlanExecutionResult | None


def authorize_and_run_workflow(
    workflow_id: WorkflowId,
    parameters: Mapping[str, str] | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> tuple[Decision, WorkflowRunOutcome | None]:
    """Authorize running ``workflow_id`` at all, then compose and execute it only if granted.

    Args:
        workflow_id: The real, already-registered workflow to run.
        parameters: Caller-supplied values for this workflow's own
            ``"${name}"`` placeholders. Defaults to empty.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through both to the outer gate's
            own ``ManualConfirmationAdapter`` and to every real,
            runnable step's own, separate authorization.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted -- every real
            decision this call makes (the outer gate, and every real
            runnable step's own authorization) lands in this same,
            single, tamper-evident file.

    Returns:
        ``(decision, outcome)`` -- ``decision`` is the outer gate's own
        real ``Decision`` (``planning.run_plan``'s own capability id,
        reused unmodified -- see module docstring), always durably
        appended to the chain by the time this returns. ``outcome`` is
        a real ``WorkflowRunOutcome`` if the outer gate was granted,
        ``None`` if denied -- the workflow is never even composed on a
        denied outer gate.

    Raises:
        jarvis.domain.errors.WorkflowNotRegistered: If ``workflow_id``
            names no real, registered workflow.
        jarvis.application.planning.executor.PlanValidationError: If
            ``compose_workflow`` somehow produces a runnable-step
            sequence ``execute_plan``'s own pre-flight validation still
            rejects -- structurally should not happen, since
            ``compose_workflow`` applies the identical ``Tier.ALLOW``/
            executor-membership checks itself, but not re-derived here
            to avoid two, possibly-diverging copies of that check.
    """
    workflows = build_default_workflow_registry()
    workflow = workflows.get(workflow_id)

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

    real_parameters: Mapping[str, str] = parameters or {}
    decision = orchestrator.authorize_by_id(
        PLANNING_RUN_PLAN_CAPABILITY_ID,
        Tainted(
            {"workflow_id": str(workflow_id), "parameters": dict(real_parameters)},
            Provenance.user(),
        ),
        orchestrator.get_current_context(),
    )
    # Saved immediately, before any runnable step's own, separately-
    # constructed dispatch call loads and re-saves this same file --
    # mirrors kernel/planning.py::authorize_and_run_plan's own,
    # already-documented reasoning exactly (see that module's own
    # comment at the identical point in its own flow).
    storage.save(chain)

    outcome: WorkflowRunOutcome | None = None
    if decision.granted:
        composed = compose_workflow(workflow, real_parameters, orchestrator, PLAN_STEP_EXECUTORS)
        execution = execute_plan(
            composed.runnable_steps,
            orchestrator,
            PLAN_STEP_EXECUTORS,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )
        outcome = WorkflowRunOutcome(workflow=workflow, composed=composed, execution=execution)

    return decision, outcome
