"""Capabilities: what a piece of behavior can do, and how carefully.

A capability declares its risk as a set of :class:`Effect` flags. Those
effects map to a minimum :class:`Tier` of authorization required before
the capability may run (:func:`minimum_tier_for`). A capability's
static description lives in :class:`CapabilityDescriptor`; one actual
call to it, with real arguments, is a :class:`CapabilityInvocation` --
whose ``effective_tier`` additionally escalates by one step whenever
the arguments themselves are tainted (see
:class:`jarvis.domain.provenance.Provenance`), so untrusted content
can never quietly authorize more than a trusted equivalent could.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, IntEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .provenance import Tainted


class Effect(Flag):
    """A declared side effect a capability may have.

    Members combine with ``|`` (e.g. ``Effect.READ_LOCAL | Effect.WRITE_LOCAL``).
    """

    NONE = 0
    READ_LOCAL = auto()
    WRITE_LOCAL = auto()
    EXECUTE = auto()
    DESTRUCTIVE = auto()
    IRREVERSIBLE = auto()
    CREDENTIAL = auto()
    EGRESS_LOCAL = auto()
    EGRESS_SENSITIVE = auto()
    EGRESS_SECRET = auto()


class Tier(IntEnum):
    """An authorization tier, lowest restriction first."""

    ALLOW = 0
    CONFIRM = 1
    MANUAL_ONLY = 2
    DENY = 3


_EFFECT_TIER_FLOOR: dict[Effect, Tier] = {
    Effect.DESTRUCTIVE: Tier.MANUAL_ONLY,
    Effect.IRREVERSIBLE: Tier.MANUAL_ONLY,
    Effect.CREDENTIAL: Tier.MANUAL_ONLY,
    Effect.EGRESS_SECRET: Tier.MANUAL_ONLY,
    Effect.EGRESS_SENSITIVE: Tier.CONFIRM,
    Effect.EXECUTE: Tier.CONFIRM,
    Effect.WRITE_LOCAL: Tier.CONFIRM,
    Effect.EGRESS_LOCAL: Tier.ALLOW,
    Effect.READ_LOCAL: Tier.ALLOW,
}


def minimum_tier_for(effects: Effect) -> Tier:
    """Return the minimum authorization tier required for ``effects``.

    Every effect present contributes its own floor tier; the result is
    the maximum of all of them, so combining effects never lowers the
    required tier. ``Effect.NONE`` (or any effect with no table entry)
    contributes nothing and floors at ``Tier.ALLOW``.

    Args:
        effects: The combined effects to evaluate.

    Returns:
        The minimum ``Tier`` required to invoke a capability with
        exactly these effects.
    """
    tier = Tier.ALLOW
    for effect, floor in _EFFECT_TIER_FLOOR.items():
        if effect in effects:
            tier = max(tier, floor)
    return tier


@dataclass(frozen=True)
class CapabilityId:
    """A validated, simple-token identifier for a capability.

    Used as a dict key and as an audit-log field, so it must be a
    single token: non-empty and free of whitespace (e.g. ``"fs.read_file"``,
    ``"shell.execute"``).

    Raises:
        ValueError: If ``value`` is empty or contains whitespace. This
            is a plain ``ValueError``, not a ``JarvisError`` subclass --
            it signals a malformed literal at construction time, not a
            runtime taint/security event a caller needs to catch via
            the domain error hierarchy (the same reasoning as
            ``Provenance.merge_all()``'s empty-input case).
    """

    value: str

    def __post_init__(self) -> None:
        """Validate ``value`` is a non-empty, whitespace-free token."""
        if not self.value:
            msg = "CapabilityId must not be empty."
            raise ValueError(msg)
        if any(ch.isspace() for ch in self.value):
            msg = f"CapabilityId must not contain whitespace: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return the underlying token, for log fields and messages."""
        return self.value


@dataclass(frozen=True)
class CapabilityDescriptor:
    """A capability's static, registered-once metadata.

    Attributes:
        id: The capability's identifier.
        effects: The effects this capability may have.
        description: A human-readable description shown in
            CONFIRM/MANUAL_ONLY prompts. Must be non-empty.
    """

    id: CapabilityId
    effects: Effect
    description: str

    def __post_init__(self) -> None:
        """Validate ``description`` is non-empty."""
        if not self.description:
            msg = "CapabilityDescriptor.description must not be empty."
            raise ValueError(msg)

    @property
    def required_tier(self) -> Tier:
        """Return the minimum tier this capability's effects require."""
        return minimum_tier_for(self.effects)


@dataclass(frozen=True)
class CapabilityInvocation:
    """One actual call to a capability, with real, provenance-tagged arguments.

    Attributes:
        descriptor: The capability being invoked.
        arguments: The call's arguments, tagged with their provenance.
            If any argument traces back to untrusted external content,
            the whole invocation is tainted.
    """

    descriptor: CapabilityDescriptor
    arguments: Tainted[Mapping[str, object]]

    @property
    def effective_tier(self) -> Tier:
        """Return the tier actually required for this specific invocation.

        Equal to ``descriptor.required_tier``, except that a tainted
        ``arguments`` provenance escalates it by exactly one step --
        clamped at ``Tier.DENY``, never wrapping back around to
        ``Tier.ALLOW``.
        """
        required = self.descriptor.required_tier
        if not self.arguments.provenance.is_tainted:
            return required
        escalated = min(required.value + 1, Tier.DENY.value)
        return Tier(escalated)
