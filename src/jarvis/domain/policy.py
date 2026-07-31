"""The policy engine: deciding whether a capability invocation may proceed.

:func:`evaluate` is a pure function -- no I/O, no logging, no side
effects -- that takes a :class:`~jarvis.domain.capability.CapabilityInvocation`
and a :class:`PolicyContext` and returns a :class:`Decision`. It is the
actual authorization boundary of the whole system: everything else
(audit logging, UI confirmation prompts, the orchestration layer in
``jarvis.application.policy``) reacts to what this function decides;
nothing upstream of it can override what it decides.

:class:`DecisionReason` is a :class:`~enum.Flag`, not a plain enum,
because more than one reason can legitimately apply to the same
:class:`Decision` at once. A capability whose tier was escalated by
tainted arguments (``TAINT_ESCALATION``) and then denied for lack of
physical confirmation (``NO_PHYSICAL_CONFIRMATION``) is genuinely both
at once -- that is a real, auditable fact a single-valued enum could
not represent, since it would force picking one cause and discarding
the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto
from typing import TYPE_CHECKING

from .capability import Tier

if TYPE_CHECKING:
    from .capability import CapabilityInvocation


@dataclass(frozen=True)
class PolicyContext:
    """Facts about the environment a Decision is being made in.

    Says nothing about the capability or its arguments -- that is
    already inside ``CapabilityInvocation``. This is purely "what
    confirmation channels exist right now."

    Attributes:
        physical_confirmation_available: Whether a human is physically
            present to confirm a MANUAL_ONLY action.
        remote_confirmation_available: Whether a CONFIRM-tier action
            can be confirmed remotely (e.g. a tappable notification).
    """

    physical_confirmation_available: bool
    remote_confirmation_available: bool


class DecisionReason(Flag):
    """Why a Decision's tier and grant/deny outcome came out as they did.

    More than one reason can legitimately apply to the same Decision:
    e.g. ``TAINT_ESCALATION`` (the tier was pushed up by untrusted
    arguments) and ``NO_PHYSICAL_CONFIRMATION`` (it was then denied for
    lack of physical confirmation) can both be true of one decision.
    """

    BASE_TIER = auto()
    TAINT_ESCALATION = auto()
    NO_PHYSICAL_CONFIRMATION = auto()
    NO_REMOTE_CONFIRMATION = auto()


@dataclass(frozen=True)
class Decision:
    """The final output of evaluating a capability invocation.

    Attributes:
        tier: The tier actually required for this invocation --
            always equal to ``invocation.effective_tier``.
        granted: Whether the action is allowed to proceed right now.
        reasons: Every reason that contributed to this outcome.
        invocation: The invocation this decision is about (kept for
            the eventual audit log).
    """

    tier: Tier
    granted: bool
    reasons: DecisionReason
    invocation: CapabilityInvocation


def evaluate(invocation: CapabilityInvocation, context: PolicyContext) -> Decision:
    """Decide whether ``invocation`` may proceed right now, and why.

    Starts from ``invocation.effective_tier`` (already reflects both
    the capability's declared effects and any taint escalation; this
    function never recomputes or duplicates that logic) and asks only:
    at this tier, right now, in this context, is the action granted?

    Args:
        invocation: The capability invocation being authorized.
        context: Facts about the environment the decision is made in.

    Returns:
        A ``Decision`` whose ``tier`` always equals
        ``invocation.effective_tier`` -- this function decides
        grant/deny at that tier, it never substitutes a different
        (e.g. lower) tier to make an invocation succeed.
    """
    tier = invocation.effective_tier
    reasons = (
        DecisionReason.TAINT_ESCALATION
        if tier > invocation.descriptor.required_tier
        else DecisionReason.BASE_TIER
    )

    if tier == Tier.DENY:
        # DENY is an absolute ceiling: no confirmation, physical or
        # remote, can override it.
        granted = False
    elif tier == Tier.MANUAL_ONLY:
        # MANUAL_ONLY is satisfied ONLY by physical confirmation.
        # context.remote_confirmation_available is deliberately never
        # read here, even if True -- per the M0 threat model, voice/
        # remote confirmation is a convenience filter, never an
        # authorization boundary (defeated by replay/cloning).
        # Reading it here, even as an "or", would punch a hole through
        # the one tier meant to require physical presence.
        granted = context.physical_confirmation_available
        if not granted:
            reasons |= DecisionReason.NO_PHYSICAL_CONFIRMATION
    elif tier == Tier.CONFIRM:
        granted = context.physical_confirmation_available or context.remote_confirmation_available
        if not granted:
            reasons |= DecisionReason.NO_REMOTE_CONFIRMATION
    elif tier == Tier.ALLOW:
        granted = True
    else:  # pragma: no cover
        msg = f"Unhandled Tier: {tier!r}"  # type: ignore[unreachable]
        raise AssertionError(msg)

    return Decision(tier=tier, granted=granted, reasons=reasons, invocation=invocation)
