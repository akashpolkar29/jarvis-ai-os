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

**WP-186, Research -- a real, cross-cutting second workflow**: three
real steps -- ``memory.retrieve`` and ``fs.search_content`` (both
``Tier.ALLOW``, run automatically, sharing one ``${query}``
parameter -- recall prior research/context, then search local notes
for the same query) then ``browser.open_page`` (``Tier.CONFIRM`` --
halts; opens an already-known URL, never a bare search query, matching
``kernel/skills.py``'s own Research skill instructions verbatim: "an
already-known local path... or an already-known URL"). **A real,
structural limitation, named here rather than hidden**: a
``WorkflowStep``'s own arguments (WP-182) are resolved only from the
caller-supplied ``parameters`` mapping, never from an earlier step's
own real result -- there is no data-flow mechanism between steps in
this v1 workflow layer (mirrors ``application/planning/executor.py``'s
own per-step, independently-authorized model, which has the identical
property for a reasoning-generated plan). Concretely: this workflow
cannot itself decide *which* local file ``fs.read_file`` should read
next based on what ``fs.search_content`` just found -- a caller reads
``outcome.execution``'s own real step results and issues any
necessary follow-up call itself. "Synthesis" (reasoning over gathered
content) is deliberately not a step either, for the same reason
WP-185 excludes task creation: ``planning.run_plan`` is this
workflow's own outer gate capability id, and is itself ``Tier.CONFIRM``
-- naming it as an inner step would both halt immediately and be a
confusing, self-referential nesting; a caller runs
``jarvis task create``/``coding.run_task`` separately once it has real
findings to reason over.

**WP-187, Coding Assistant -- a real, controlled development
workflow**: three real steps -- ``git.status``, ``fs.find``, and
``fs.search_content`` (all ``Tier.ALLOW``, run automatically --
inspect a repository's real state, then locate relevant files by name
and by content) then ``coding.run_task`` (``Tier.CONFIRM`` -- halts;
the outer gate on invoking WP-71's real autonomous coding-agent loop,
which runs its own real tests internally, in its own disposable,
sandboxed workspace, once manually invoked). **Never a second shell
executor, and ``terminal.run`` is never touched**: nothing in this
workflow, or in ``coding.run_task`` itself, runs an arbitrary shell
command -- ``terminal.run`` remains ADR-0046's own deliberate,
narrow, always-``Tier.MANUAL_ONLY`` exception to this project's
no-shell principle, completely outside this workflow's scope, exactly
matching the Coding skill's own instructions. **Never destructive by
default**: the coding-agent loop this halts in front of writes only
inside its own disposable workspace (ADR-0055) until a caller
separately, explicitly runs it; this workflow performs no write of
its own. Shares the same real, structural inter-step data-flow gap
named in the Research workflow's own docstring above -- ``fs.find``'s
own real matches are not threaded into ``coding.run_task``'s own
``task`` argument automatically.

**WP-188, memory-context integration -- no new mechanism, closing one
real asymmetry**: Job Search Assistant and Research already opened
with a real ``memory.retrieve`` step; Coding Assistant did not.
``Coding Assistant`` now opens with one too (``project_context_query``),
recalling relevant prior project context before inspecting the
repository. **Every real requirement this closes is already satisfied
by reuse, not by anything built here**: "explicit context selection"
and "minimal relevant memory" are the caller-supplied ``query`` plus a
small, fixed ``limit=5`` on every one of these three steps (never "all
memory," structurally -- ``RetrievalPort.retrieve()`` has no
"everything" mode at all); "no secret leakage" is
``adapters/memory.py::SqliteMemoryAdapter.retrieve()``'s own real,
already-existing, unconditional
``application/memory/retrieval_guard.py::exclude_secret_records()``
call (ADR-0050) -- applied at the storage-adapter layer itself, below
every composition function, so a workflow's own ``memory.retrieve``
step cannot bypass it any more than a direct ``jarvis memory retrieve``
CLI call already cannot; already proven by
``tests/unit/application/memory/test_retrieval_guard.py`` and
``tests/property/test_retrieval_guard.py``, not re-proven here. "No
new memory store" and "no duplicate retrieval system": true by
construction -- every memory-context step above names the real,
already-statically-registered ``memory.retrieve`` capability id,
completely unmodified.
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
    BROWSER_OPEN_PAGE_CAPABILITY_ID,
    CODING_RUN_TASK_CAPABILITY_ID,
    FIND_FILES_CAPABILITY_ID,
    GIT_STATUS_CAPABILITY_ID,
    JOB_SEARCH_OPEN_RESULTS_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    PLANNING_RUN_PLAN_CAPABILITY_ID,
    SEARCH_CONTENT_CAPABILITY_ID,
    build_default_registry,
)
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS

JOB_SEARCH_ASSISTANT_WORKFLOW_ID = WorkflowId("job_search_assistant")
RESEARCH_WORKFLOW_ID = WorkflowId("research")
CODING_ASSISTANT_WORKFLOW_ID = WorkflowId("coding_assistant")

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

    registry.register(
        WorkflowDescriptor(
            id=RESEARCH_WORKFLOW_ID,
            name="Research",
            description=(
                "Recall prior research/context and search local notes for a query, then "
                "open an already-known source URL -- never a second reasoning engine; "
                "synthesis over what this workflow gathers is a real, separate follow-up "
                "call the caller makes itself."
            ),
            steps=(
                WorkflowStep(
                    capability_id=MEMORY_RETRIEVE_CAPABILITY_ID,
                    arguments={"query": "${query}", "limit": 5},
                    description="Recall prior research/context relevant to the query.",
                ),
                WorkflowStep(
                    capability_id=SEARCH_CONTENT_CAPABILITY_ID,
                    arguments={"query": "${query}"},
                    description="Search local notes/files for content matching the query.",
                ),
                WorkflowStep(
                    capability_id=BROWSER_OPEN_PAGE_CAPABILITY_ID,
                    arguments={"url": "${url}"},
                    description=(
                        "Open an already-known source URL -- Tier.CONFIRM, halts here; "
                        "this workflow builds no search query of its own, matching "
                        "docs/OPEN_DECISIONS.md item 71's own documented gap (no generic "
                        "web-search capability exists)."
                    ),
                ),
            ),
            parameters=("query", "url"),
            metadata={"source": "wp186-research"},
        )
    )

    registry.register(
        WorkflowDescriptor(
            id=CODING_ASSISTANT_WORKFLOW_ID,
            name="Coding Assistant",
            description=(
                "Inspect a repository's real state and locate relevant files, then invoke "
                "the real, already-built autonomous coding-agent task -- never a second "
                "shell executor, never a bypass of its own, separate authorization."
            ),
            steps=(
                WorkflowStep(
                    capability_id=MEMORY_RETRIEVE_CAPABILITY_ID,
                    arguments={"query": "${project_context_query}", "limit": 5},
                    description="Recall relevant prior project context, if any.",
                ),
                WorkflowStep(
                    capability_id=GIT_STATUS_CAPABILITY_ID,
                    arguments={"repo_dir": "${repo_dir}"},
                    description="Inspect the target repository's real, current git status.",
                ),
                WorkflowStep(
                    capability_id=FIND_FILES_CAPABILITY_ID,
                    arguments={"pattern": "${file_pattern}"},
                    description="Locate relevant files by name.",
                ),
                WorkflowStep(
                    capability_id=SEARCH_CONTENT_CAPABILITY_ID,
                    arguments={"query": "${code_query}"},
                    description="Locate relevant code by content.",
                ),
                WorkflowStep(
                    capability_id=CODING_RUN_TASK_CAPABILITY_ID,
                    arguments={"task": "${task}", "target_repo": "${repo_dir}"},
                    description=(
                        "Run the real, autonomous coding-agent task (WP-71) against the "
                        "target repository, including its own real, internal test "
                        "execution -- Tier.CONFIRM, halts here; never auto-invoked."
                    ),
                ),
            ),
            parameters=(
                "project_context_query",
                "repo_dir",
                "file_pattern",
                "code_query",
                "task",
            ),
            metadata={"source": "wp187-coding-assistant", "updated_by": "wp188-memory-context"},
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
