"""Property-based tests for jarvis.domain.capability."""

from __future__ import annotations

import functools
import operator
import string

from hypothesis import given
from hypothesis import strategies as st

from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
    minimum_tier_for,
)
from jarvis.domain.provenance import Classification, Provenance, Tainted

_ALL_EFFECTS: list[Effect] = [
    member for member in Effect.__members__.values() if member != Effect.NONE
]
_HIGH_RISK_EFFECTS: list[Effect] = [
    Effect.DESTRUCTIVE,
    Effect.IRREVERSIBLE,
    Effect.CREDENTIAL,
]


def _combine(members: set[Effect]) -> Effect:
    """Fold a set of individual Effect members into one combined Effect."""
    return functools.reduce(operator.or_, members, Effect.NONE)


EFFECT_MEMBER_SET = st.sets(st.sampled_from(_ALL_EFFECTS))

CAPABILITY_ID = st.text(
    alphabet=string.ascii_lowercase + "._",
    min_size=1,
    max_size=20,
).map(CapabilityId)
CLASSIFICATION = st.sampled_from(Classification)
UNTAINTED_PROVENANCE = st.just(Provenance.user())
TAINTED_PROVENANCE = st.builds(
    Provenance.external,
    source=st.text(min_size=1, max_size=10),
    classification=CLASSIFICATION,
)
ARGUMENTS_VALUE = st.dictionaries(st.text(max_size=5), st.integers(), max_size=3)


def _descriptor(effects: Effect) -> CapabilityDescriptor:
    """Build a valid CapabilityDescriptor with the given effects."""
    return CapabilityDescriptor(
        id=CapabilityId("test.capability"),
        effects=effects,
        description="A test capability.",
    )


DESCRIPTOR = EFFECT_MEMBER_SET.map(_combine).map(_descriptor)


@given(EFFECT_MEMBER_SET, EFFECT_MEMBER_SET)
def test_minimum_tier_for_is_monotonic(a_members: set[Effect], extra_members: set[Effect]) -> None:
    """Adding effects never lowers the required tier."""
    b_members = a_members | extra_members
    a_tier = minimum_tier_for(_combine(a_members))
    b_tier = minimum_tier_for(_combine(b_members))
    assert b_tier >= a_tier


@given(st.sampled_from(_HIGH_RISK_EFFECTS), EFFECT_MEMBER_SET)
def test_high_risk_effect_always_at_least_manual_only(
    high_risk_effect: Effect, other_members: set[Effect]
) -> None:
    """DESTRUCTIVE/IRREVERSIBLE/CREDENTIAL always floor at MANUAL_ONLY."""
    combined = _combine(other_members) | high_risk_effect
    assert minimum_tier_for(combined) >= Tier.MANUAL_ONLY


@given(EFFECT_MEMBER_SET)
def test_egress_secret_always_denies_unconditionally(other_members: set[Effect]) -> None:
    """EGRESS_SECRET always floors at DENY, regardless of what else is combined with it.

    Stricter than the other high-risk effects (ADR-0038): DENY is an
    absolute ceiling evaluate() never grants, unlike MANUAL_ONLY, which
    physical confirmation can satisfy. Kept as its own property test,
    not folded back into test_high_risk_effect_always_at_least_manual_only,
    so this exact guarantee -- not just ">= MANUAL_ONLY" -- has its own
    assertion.
    """
    combined = _combine(other_members) | Effect.EGRESS_SECRET
    assert minimum_tier_for(combined) == Tier.DENY


@given(DESCRIPTOR, ARGUMENTS_VALUE, UNTAINTED_PROVENANCE | TAINTED_PROVENANCE)
def test_effective_tier_never_below_required(
    descriptor: CapabilityDescriptor,
    arguments_value: dict[str, int],
    provenance: Provenance,
) -> None:
    """effective_tier is never lower than descriptor.required_tier."""
    invocation = CapabilityInvocation(descriptor, Tainted(arguments_value, provenance))
    assert invocation.effective_tier >= descriptor.required_tier


@given(DESCRIPTOR, ARGUMENTS_VALUE, TAINTED_PROVENANCE)
def test_tainted_escalates_unless_already_deny(
    descriptor: CapabilityDescriptor,
    arguments_value: dict[str, int],
    tainted_provenance: Provenance,
) -> None:
    """Tainted arguments strictly escalate effective_tier, unless already DENY."""
    untainted = CapabilityInvocation(descriptor, Tainted(arguments_value, Provenance.user()))
    tainted = CapabilityInvocation(descriptor, Tainted(arguments_value, tainted_provenance))
    if untainted.effective_tier == Tier.DENY:
        assert tainted.effective_tier == Tier.DENY
    else:
        assert tainted.effective_tier > untainted.effective_tier


@given(DESCRIPTOR, ARGUMENTS_VALUE, UNTAINTED_PROVENANCE | TAINTED_PROVENANCE)
def test_effective_tier_never_exceeds_deny(
    descriptor: CapabilityDescriptor,
    arguments_value: dict[str, int],
    provenance: Provenance,
) -> None:
    """effective_tier is clamped: it can never exceed Tier.DENY."""
    invocation = CapabilityInvocation(descriptor, Tainted(arguments_value, provenance))
    assert invocation.effective_tier <= Tier.DENY
