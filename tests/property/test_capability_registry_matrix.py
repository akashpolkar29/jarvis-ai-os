"""An exhaustive property-test matrix over every real, statically-registered capability.

Closes a real, previously-open gap: tests/unit/test_capabilities.py already
proves each capability's real Effect/required_tier pairing against
build_default_registry(); tests/property/test_policy.py and
test_capability.py already prove evaluate()'s own tier-granting properties
against synthetic descriptors built by hand. Neither proves that going
through the REAL AuthorizationOrchestrator.authorize_by_id() with a REAL
capability id, looked up from the REAL registry, actually produces the
correct granted/denied behavior end to end -- a wiring bug in
authorize_by_id()'s own registry lookup or CapabilityInvocation
construction could slip past all three of those tests individually while
still failing here. This file exercises the real integration seam.

Every dynamic-effect capability (memory.write, communications.send_email/
create_calendar_event, job_assistance.draft, coding.run_task's own inner
CODE_WRITE/PROTECTED_PATH_WRITE gate) is deliberately out of scope here --
each already has its own dedicated property-test file
(test_memory_writer.py, test_communications_writer.py, test_coding_writer.py,
test_drafting_writer.py) proving the same granted/physical-confirmation
properties for its own real classification function. This file covers
exactly the 40 capabilities build_default_registry() registers statically.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import CapabilityId, Tier
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import build_default_registry

CONTEXT = st.builds(
    PolicyContext,
    physical_confirmation_available=st.booleans(),
    remote_confirmation_available=st.booleans(),
)

_REGISTRY = build_default_registry()
_ALL_CAPABILITY_IDS = tuple(descriptor.id for descriptor in _REGISTRY)

# Real, current tier assignment for every one of the 40 statically-registered
# capabilities, as of this pass -- read directly from build_default_registry(),
# not hand-guessed. Any future change to a capability's Effect combination
# that shifts its required_tier will show up here as a real, visible diff in
# this dict rather than only as a passing/failing property below, making a
# real tier-classification change impossible to make silently.
_EXPECTED_TIER_BY_CAPABILITY: dict[str, Tier] = {
    "audit.history": Tier.ALLOW,
    "browser.close_page": Tier.CONFIRM,
    "browser.inspect_dom": Tier.ALLOW,
    "browser.open_page": Tier.CONFIRM,
    "browser.screenshot": Tier.ALLOW,
    "coding.run_task": Tier.CONFIRM,
    "communications.list_calendar_events": Tier.ALLOW,
    "communications.list_email": Tier.ALLOW,
    "communications.read_email": Tier.ALLOW,
    "desktop.brave_open_url": Tier.CONFIRM,
    "desktop.chatgpt_app_send_text": Tier.CONFIRM,
    "desktop.claude_app_send_text": Tier.CONFIRM,
    "desktop.vscode_open_file": Tier.CONFIRM,
    "docker.build_image": Tier.MANUAL_ONLY,
    "docker.list_containers": Tier.ALLOW,
    "docker.run_container": Tier.MANUAL_ONLY,
    "docker.stop_container": Tier.CONFIRM,
    "fs.delete_file": Tier.MANUAL_ONLY,
    "fs.list_dir": Tier.ALLOW,
    "fs.move_file": Tier.CONFIRM,
    "fs.read_file": Tier.ALLOW,
    "git.commit": Tier.CONFIRM,
    "git.create_branch": Tier.CONFIRM,
    "git.force_push": Tier.MANUAL_ONLY,
    "git.push": Tier.CONFIRM,
    "git.status": Tier.ALLOW,
    "job_search.open_results": Tier.CONFIRM,
    "memory.backup": Tier.CONFIRM,
    "memory.forget": Tier.MANUAL_ONLY,
    "memory.pin": Tier.CONFIRM,
    "memory.restore": Tier.MANUAL_ONLY,
    "memory.retrieve": Tier.ALLOW,
    "memory.wipe": Tier.MANUAL_ONLY,
    "music.next": Tier.CONFIRM,
    "music.pause": Tier.CONFIRM,
    "music.play": Tier.CONFIRM,
    "music.previous": Tier.CONFIRM,
    "ping": Tier.ALLOW,
    "planning.run_plan": Tier.CONFIRM,
    "terminal.run": Tier.MANUAL_ONLY,
}


def _orchestrator() -> AuthorizationOrchestrator:
    return AuthorizationOrchestrator(AuditChain(), build_default_registry())


def test_expected_tier_table_covers_every_registered_capability_exactly() -> None:
    """The hand-curated table above matches the real registry exactly -- no id added or missing.

    A capability added to build_default_registry() without a matching entry
    here fails this test immediately, forcing this table (and this pass's
    own real-tier-classification review) to be updated deliberately rather
    than the matrix below silently skipping it.
    """
    assert {cid.value for cid in _ALL_CAPABILITY_IDS} == set(_EXPECTED_TIER_BY_CAPABILITY)


@given(st.sampled_from(_ALL_CAPABILITY_IDS), CONTEXT)
def test_every_registered_capability_grants_exactly_per_its_real_required_tier(
    capability_id: CapabilityId, context: PolicyContext
) -> None:
    """decision.granted, from the REAL orchestrator + REAL registry, matches the real tier rule.

    ALLOW: always granted. CONFIRM: granted iff either confirmation channel
    is available. MANUAL_ONLY: granted iff physical confirmation
    specifically -- remote alone never satisfies it (ADR-0013). This is the
    exhaustive matrix this pass's own instructions require: every one of
    the 38 real, statically-registered capabilities, proven through the
    real end-to-end authorize_by_id() path, not a synthetic descriptor.
    """
    descriptor = _REGISTRY.get(capability_id)
    required = descriptor.required_tier
    assert required == _EXPECTED_TIER_BY_CAPABILITY[capability_id.value]

    decision = _orchestrator().authorize_by_id(
        capability_id, Tainted({}, Provenance.user()), context
    )

    if required == Tier.ALLOW:
        assert decision.granted is True
    elif required == Tier.CONFIRM:
        assert decision.granted == (
            context.physical_confirmation_available or context.remote_confirmation_available
        )
    elif required == Tier.MANUAL_ONLY:
        assert decision.granted == context.physical_confirmation_available
    else:  # pragma: no cover -- no real capability in this registry is registered at DENY
        assert decision.granted is False


@given(st.sampled_from(_ALL_CAPABILITY_IDS))
def test_manual_only_capabilities_never_granted_by_remote_confirmation_alone(
    capability_id: CapabilityId,
) -> None:
    """The specific, named ADR-0013 property for every real MANUAL_ONLY capability.

    A separate, narrower test from the general matrix above so this exact
    guarantee -- remote confirmation alone is never enough for
    terminal.run/docker.run_container/docker.build_image/fs.delete_file/
    git.force_push/memory.forget -- has its own dedicated assertion, not
    folded only into the combined property.
    """
    descriptor = _REGISTRY.get(capability_id)
    if descriptor.required_tier != Tier.MANUAL_ONLY:
        return
    context = PolicyContext(
        physical_confirmation_available=False, remote_confirmation_available=True
    )

    decision = _orchestrator().authorize_by_id(
        capability_id, Tainted({}, Provenance.user()), context
    )

    assert decision.granted is False
