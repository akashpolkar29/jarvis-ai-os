"""The composition root for job_assistance.draft: WP-84, the first real M6b capability.

:func:`authorize_and_draft_document` is the first point a real
drafting task can be authorized and run as an actual, invocable
capability -- mirroring ``kernel/memory.py``'s own
``authorize_and_remember`` composition shape exactly: registry/
storage/confirmation/orchestrator wiring, a dynamic-effect authorizer
resolves the real ``Effect`` from the task's own classification, the
real side effect only ever happens inside ``if decision.granted:``,
``storage.save(chain)`` in a ``finally`` block so a granted decision is
never lost even if the drafting task itself raises.

**``job_assistance.draft`` is deliberately not registered in
``build_default_registry()``** -- exactly the same reason
``memory.write`` never is either (see that module's own docstring):
``application/job_assistance/classification.py::draft_effect_for``'s
own real, conservative ``SECRET``-input default (reusing
``Effect.MEMORY_WRITE``'s unconditional ``DENY`` floor) means the
correct ``Effect`` genuinely varies per real invocation, which a
statically-registered ``CapabilityDescriptor`` cannot express. This is
a real deviation from ``docs/architecture/m6b-job-assistance.md``'s own
original "static, fixed-effect capability" sketch, made here because
implementing the drafting capability for real forced a concrete choice
about ``SECRET`` input the design doc had deliberately left open --
see ``classification.py``'s own docstring for the full reasoning, and
flagged for the user's own confirmation that this conservative default
is what they want long-term, not silently decided as settled policy.

**Reuses ``jarvis.application.reasoning.unverifiable.UnverifiableTaskHandler``
unmodified** (deliverable #7, ADR-0040, already built for M2) -- checked
against ``Dispatcher`` first and rejected: a cover letter has no
pass/fail validator, so the escalation-ladder/self-repair machinery
built for verifiable tasks does not fit. ``UnverifiableTaskHandler``'s
own real shape (every authorized provider asked once, in parallel, a
human picks via ``CandidatePresentationPort``) is a precise, structural
match instead. Every real provider call it makes already routes
through ``ModelRouter.authorize_provider_call`` -- the same
``Effect.EGRESS_SENSITIVE``/``Effect.EGRESS_SECRET`` classification
gate every other reasoning-provider call in this codebase already
uses. No new ``Effect``/``Tier`` decision for that part.

**``providers`` has no default, on purpose** -- mirroring
``kernel/coding.py``'s own ``dispatcher_factory`` "no implicit default
for a genuinely undecided, high-consequence choice" precedent exactly:
which real ``ReasoningPort`` providers draft a real cover letter was
never decided by any ADR here either. **``presentation`` does have a
real default** (``TtsTextCandidatePresentationAdapter`` over a real
``PiperTtsAdapter``) -- unlike provider assignment, there is exactly
one real adapter for this port with no policy ambiguity to invent, the
same "real default, overridable for tests" shape ``embedding_port``/
``browser_automation`` already use elsewhere in this ring.

**No outer, separate authorization gate the way ``coding.run_task``
has one** -- checked and rejected as unnecessary, not merely omitted:
``coding.run_task``'s own outer ``Effect.EXECUTE``/``Tier.CONFIRM`` gate
exists because the coding loop has its *own* separate, per-write
authorization inside a multi-climb loop (WP-70/WP-71), so a second,
outer gate is needed to authorize invoking the loop *at all*, distinct
from each write inside it. Drafting has no such inner loop -- its one
real side effect is a single ``DraftStoragePort.save()`` call, so
``DraftWriteAuthorizer``'s own single ``Decision`` is both the first
and only gate this capability needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.candidate_presentation import TtsTextCandidatePresentationAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.draft_storage import LocalDraftStorageAdapter
from jarvis.adapters.tts import PiperTtsAdapter
from jarvis.application.job_assistance.drafting import DraftWriteAuthorizer
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.reasoning.router import ModelRouter
from jarvis.application.reasoning.unverifiable import UnverifiableTaskHandler
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import build_default_registry

if TYPE_CHECKING:
    from jarvis.domain.policy import Decision
    from jarvis.domain.reasoning import ProviderProfile
    from jarvis.ports.candidate_presentation import CandidatePresentationPort
    from jarvis.ports.draft_storage import DraftStoragePort
    from jarvis.ports.reasoning import ReasoningPort

_DEFAULT_DRAFTS_DIR = Path("drafts")
"""A plain relative-path literal default, matching kernel/memory.py's
own _DEFAULT_MEMORY_DB_PATH precedent -- this project does not yet use
platformdirs for real default data paths anywhere."""


def _default_presentation() -> TtsTextCandidatePresentationAdapter:
    return TtsTextCandidatePresentationAdapter(tts=PiperTtsAdapter())


@dataclass(frozen=True)
class DraftOutcome:
    """The result of one authorize_and_draft_document() call.

    Attributes:
        decision: The Decision for this drafting task -- durably
            appended to the chain regardless of outcome.
        path: The real path the selected draft was saved to, if the
            decision was granted. ``None`` if denied.
    """

    decision: Decision
    path: Path | None


async def authorize_and_draft_document(  # noqa: PLR0913 -- one per composition-function pass-through
    task: str,
    providers: tuple[tuple[ProviderProfile, ReasoningPort], ...],
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    presentation: CandidatePresentationPort | None = None,
    drafts_dir: Path | None = None,
    draft_storage: DraftStoragePort | None = None,
) -> DraftOutcome:
    """Wire up the stack, authorize drafting ``task``, and run it only if granted.

    Args:
        task: The drafting task's own plain-text description, typed or
            spoken directly by the user -- wrapped as
            ``Tainted(task, Provenance.user())``, matching every other
            directly-typed/spoken argument in this codebase. A future
            caller constructing this value from a less-trusted or more
            sensitive source is responsible for giving it the correct
            provenance before calling this function -- this function
            does not, and cannot, second-guess a provenance it did not
            compute (the identical trust boundary
            ``authorize_and_remember``'s own docstring already states).
        providers: Every real ``ReasoningPort`` to try, in parallel --
            see this module's own docstring for why this has no
            default.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        presentation: Where generated candidates are presented and a
            human's choice is collected. Defaults to a real
            ``TtsTextCandidatePresentationAdapter``.
        drafts_dir: Where real drafted files are saved. Defaults to
            ``_DEFAULT_DRAFTS_DIR``. Overridable for tests.
        draft_storage: The real store a granted draft is saved to.
            Defaults to a real ``LocalDraftStorageAdapter`` over
            ``drafts_dir``. Overridable for tests.

    Returns:
        A ``DraftOutcome`` -- see its own docstring.
    """
    value: Tainted[str] = Tainted(task, Provenance.user())

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, build_default_registry(), confirmation=confirmation
    )
    authorizer = DraftWriteAuthorizer(orchestrator)

    decision = authorizer.authorize_draft(value, orchestrator.get_current_context())

    path: Path | None = None
    try:
        if decision.granted:
            router = ModelRouter(orchestrator)
            handler = UnverifiableTaskHandler(
                providers, router, presentation or _default_presentation()
            )
            candidate = await handler.handle(value, orchestrator.get_current_context())
            store = draft_storage or LocalDraftStorageAdapter(drafts_dir or _DEFAULT_DRAFTS_DIR)
            path = store.save(candidate.author, candidate.content)
    finally:
        storage.save(chain)

    return DraftOutcome(decision=decision, path=path)
