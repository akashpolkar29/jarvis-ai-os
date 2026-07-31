"""Unit tests for jarvis.domain.policy."""

from __future__ import annotations

import pytest

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


_ALLOW_INV = _invocation(Effect.READ_LOCAL, tainted=False)
_CONFIRM_INV = _invocation(Effect.EXECUTE, tainted=False)
_MANUAL_ONLY_INV = _invocation(Effect.DESTRUCTIVE, tainted=False)
_DENY_INV = _invocation(Effect.DESTRUCTIVE, tainted=True)

# This table IS the specification of evaluate(): every tier/physical/
# remote combination, with the exact expected granted/reason outcome.
# Rows 10 and 16 are the two that prove the load-bearing security
# properties -- remote alone never satisfies MANUAL_ONLY, and DENY is
# never overridden even by both confirmations being available.
# Columns: invocation, physical, remote, expected_granted, expect_no_physical, expect_no_remote.
TABLE = [
    (_ALLOW_INV, False, False, True, False, False),
    (_ALLOW_INV, False, True, True, False, False),
    (_ALLOW_INV, True, False, True, False, False),
    (_ALLOW_INV, True, True, True, False, False),
    (_CONFIRM_INV, False, False, False, False, True),
    (_CONFIRM_INV, False, True, True, False, False),
    (_CONFIRM_INV, True, False, True, False, False),
    (_CONFIRM_INV, True, True, True, False, False),
    (_MANUAL_ONLY_INV, False, False, False, True, False),
    (_MANUAL_ONLY_INV, False, True, False, True, False),  # remote alone: still denied
    (_MANUAL_ONLY_INV, True, False, True, False, False),
    (_MANUAL_ONLY_INV, True, True, True, False, False),
    (_DENY_INV, False, False, False, False, False),
    (_DENY_INV, False, True, False, False, False),
    (_DENY_INV, True, False, False, False, False),
    (_DENY_INV, True, True, False, False, False),  # both available: still denied
]


@pytest.mark.parametrize(
    (
        "invocation",
        "physical",
        "remote",
        "expected_granted",
        "expect_no_physical",
        "expect_no_remote",
    ),
    TABLE,
)
def test_evaluate_boundary_table(  # noqa: PLR0913, PLR0917 -- one param per table column, by design
    invocation: CapabilityInvocation,
    physical: bool,
    remote: bool,
    expected_granted: bool,
    expect_no_physical: bool,
    expect_no_remote: bool,
) -> None:
    """evaluate() matches the full (tier x physical x remote) boundary table exactly."""
    context = PolicyContext(
        physical_confirmation_available=physical,
        remote_confirmation_available=remote,
    )
    decision = evaluate(invocation, context)
    assert decision.granted == expected_granted
    assert (DecisionReason.NO_PHYSICAL_CONFIRMATION in decision.reasons) == expect_no_physical
    assert (DecisionReason.NO_REMOTE_CONFIRMATION in decision.reasons) == expect_no_remote
