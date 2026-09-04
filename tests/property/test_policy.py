"""Property-based tests for jarvis.domain.policy."""

from __future__ import annotations

from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.policy import DecisionReason, PolicyContext, evaluate
from jarvis.domain.provenance import Classification, Provenance, Tainted


def _invocation(effects: Effect, *, tainted: bool) -> CapabilityInvocation:
    """Build a CapabilityInvocation with the given effects and taint state."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId("test.capability"),
        effects=effects,
        description="A test capability.",
    )
    provenance = (
        Provenance.external("test-source", Classification.PUBLIC) if tainted else Provenance.user()
    )
    return CapabilityInvocation(descriptor, Tainted({}, provenance))


# One fixed, representative invocation per tier. _DENY_INVOCATION
# reaches DENY via taint escalation from MANUAL_ONLY, not directly --
# kept this way since it's exercising the *escalation* path
# specifically. As of ADR-0038, minimum_tier_for can also return DENY
# directly (EGRESS_SECRET) without any taint escalation at all --
# see _EGRESS_SECRET_INVOCATION and test_egress_secret_never_reaches_a_cloud_provider
# below for that path, not this fixture.
_ALLOW_INVOCATION = _invocation(Effect.READ_LOCAL, tainted=False)
_CONFIRM_INVOCATION = _invocation(Effect.EXECUTE, tainted=False)
_MANUAL_ONLY_INVOCATION = _invocation(Effect.DESTRUCTIVE, tainted=False)
_DENY_INVOCATION = _invocation(Effect.DESTRUCTIVE, tainted=True)
_EGRESS_SECRET_INVOCATION = _invocation(Effect.EGRESS_SECRET, tainted=False)

CONTEXT = st.builds(
    PolicyContext,
    physical_confirmation_available=st.booleans(),
    remote_confirmation_available=st.booleans(),
)


@given(CONTEXT)
def test_deny_is_absolute(context: PolicyContext) -> None:
    """No confirmation, of any kind, can override a DENY-tier invocation."""
    assert evaluate(_DENY_INVOCATION, context).granted is False


@given(CONTEXT)
def test_egress_secret_never_reaches_a_cloud_provider(context: PolicyContext) -> None:
    """A SECRET-classified task never reaches a cloud provider, under any confirmation state.

    M2 acceptance criterion #9 (WP-28 planning pass), the concrete
    regression test ADR-0038 requires: even with
    physical_confirmation_available=True (which satisfies MANUAL_ONLY),
    an EGRESS_SECRET-effect invocation must still be denied, because it
    floors at DENY, not MANUAL_ONLY. Distinct from test_deny_is_absolute
    below -- that test proves DENY is absolute for a DENY reached via
    taint escalation; this one proves the same for DENY reached
    directly from the effect table, which is the path ADR-0038 exists
    to fix.
    """
    assert evaluate(_EGRESS_SECRET_INVOCATION, context).granted is False


@given(CONTEXT)
def test_manual_only_requires_physical_confirmation_specifically(context: PolicyContext) -> None:
    """MANUAL_ONLY tracks physical_confirmation_available, ignoring remote entirely."""
    decision = evaluate(_MANUAL_ONLY_INVOCATION, context)
    assert decision.granted == context.physical_confirmation_available


@given(CONTEXT)
def test_confirm_is_satisfied_by_either_confirmation_type(context: PolicyContext) -> None:
    """CONFIRM is granted whenever either confirmation channel is available."""
    decision = evaluate(_CONFIRM_INVOCATION, context)
    expected = context.physical_confirmation_available or context.remote_confirmation_available
    assert decision.granted == expected


@given(CONTEXT)
def test_allow_always_grants(context: PolicyContext) -> None:
    """ALLOW never needs any confirmation."""
    assert evaluate(_ALLOW_INVOCATION, context).granted is True


@given(CONTEXT)
def test_decision_tier_always_equals_effective_tier(context: PolicyContext) -> None:
    """evaluate() never substitutes a different tier than effective_tier."""
    for invocation in (
        _ALLOW_INVOCATION,
        _CONFIRM_INVOCATION,
        _MANUAL_ONLY_INVOCATION,
        _DENY_INVOCATION,
    ):
        decision = evaluate(invocation, context)
        assert decision.tier == invocation.effective_tier


@given(CONTEXT)
def test_granted_is_non_increasing_across_tiers(context: PolicyContext) -> None:
    """For a fixed context, granted-ness never rises again once it's False.

    The "no shell" property one level up the stack from WP-03's
    minimum_tier_for monotonicity: as effective_tier climbs from ALLOW
    to DENY, evaluate() must never re-grant an action it already denied
    at a lower tier.
    """
    granted_by_tier = [
        evaluate(invocation, context).granted
        for invocation in (
            _ALLOW_INVOCATION,
            _CONFIRM_INVOCATION,
            _MANUAL_ONLY_INVOCATION,
            _DENY_INVOCATION,
        )
    ]
    for earlier, later in pairwise(granted_by_tier):
        assert earlier >= later


@given(CONTEXT)
def test_taint_escalation_reason_tracks_whether_the_tier_was_actually_escalated(
    context: PolicyContext,
) -> None:
    """A real, previously-uncovered gap (found by mutation testing, overnight Track 2,
    2026-09-04): every mutant on evaluate()'s own `tier > invocation.descriptor.required_tier`
    comparison (line 107, deciding TAINT_ESCALATION vs BASE_TIER) survived the full test
    suite -- nothing anywhere asserted this reason at all, despite _DENY_INVOCATION's own
    docstring already stating it exists specifically to exercise the escalation path.

    Proves both directions precisely, for every real tier this codebase's own capability
    registry can produce: a tainted invocation whose tier was genuinely pushed up by
    taint gets TAINT_ESCALATION, never BASE_TIER; a non-tainted invocation (which can
    never be escalated -- effective_tier only escalates when tainted) always gets
    BASE_TIER, never TAINT_ESCALATION. This is exactly the property that kills every one
    of the eight surviving comparison-operator/AddNot mutants at once, not just one of
    them -- the real bug each represents (a wrong TAINT_ESCALATION/BASE_TIER reason
    reaching a real audit log entry) is a single real property, not eight separate ones.
    """
    for effects, expect_escalation in (
        # required_tier is ALLOW/CONFIRM/MANUAL_ONLY respectively --
        # each genuinely has room to climb one real step when tainted.
        (Effect.READ_LOCAL, True),
        (Effect.EXECUTE, True),
        (Effect.DESTRUCTIVE, True),
        # required_tier is already DENY -- min(required + 1, DENY)
        # clamps to the same value, so taint changes nothing real here,
        # even though the invocation itself is genuinely tainted.
        (Effect.EGRESS_SECRET, False),
    ):
        non_tainted = _invocation(effects, tainted=False)
        decision = evaluate(non_tainted, context)
        assert DecisionReason.BASE_TIER in decision.reasons
        assert DecisionReason.TAINT_ESCALATION not in decision.reasons

        tainted = _invocation(effects, tainted=True)
        decision = evaluate(tainted, context)
        if expect_escalation:
            assert DecisionReason.TAINT_ESCALATION in decision.reasons
            assert DecisionReason.BASE_TIER not in decision.reasons
        else:
            assert DecisionReason.BASE_TIER in decision.reasons
            assert DecisionReason.TAINT_ESCALATION not in decision.reasons
