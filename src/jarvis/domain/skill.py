"""Skills: discoverable, named groupings of already-existing capabilities.

A :class:`SkillDescriptor` is pure, static, "what can I do" metadata --
identity, a human-readable description, the intent/domain it covers,
and the real, already-registered :class:`~jarvis.domain.capability.CapabilityId`
values it groups together, plus optional free-text instructions/context
and discoverability tags. It never carries an ``Effect``/``Tier`` of its
own and never executes anything: a skill points at capabilities, it does
not replace or bypass them. Every real action a skill describes still
goes through exactly the same ``CapabilityDescriptor``/``Effect``/
``Tier``/``AuthorizationOrchestrator`` choke point it always did --
this module adds a discovery layer above that boundary, never a second
one beside it (WP-171, M8 skills-platform scoping).

**Why this lives in ``domain``, not ``application`` or ``kernel``**:
mirrors :class:`~jarvis.domain.capability.CapabilityDescriptor`/
:class:`~jarvis.domain.registry.CapabilityRegistry` exactly -- pure,
frozen, stdlib-only data describing *what exists*, with no I/O, no
async, no wall-clock/randomness. A ``SkillRegistry`` (WP-172) will be
just as stateful-but-I/O-free as ``CapabilityRegistry`` already is, for
the identical reason that class gives for living here despite being
mutable: the real constraint is no I/O, not immutability.

**What this explicitly does NOT do, checked against the existing
architecture before writing any of it (WP-171 reconnaissance)**: no
existing abstraction already covers this. ``CapabilityDescriptor``
describes one directly-invocable, effect/tier-classified unit of
behavior -- it has no notion of grouping several capabilities under one
discoverable, human-facing concept. ``jarvis.plugin_api`` is a stable
import surface for capability authors, not a discovery layer.
``jarvis.application.routing.router`` maps free text to one capability
id or a new task -- it has no "what can I do in this domain" listing.
Nothing here changes any of that; a skill's ``capability_ids`` must
always be real, already-registered capability ids (validated by
WP-172's registry against the real ``CapabilityRegistry``, reusing it
rather than inventing a parallel one) -- a skill can describe only what
already, genuinely exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .capability import CapabilityId


@dataclass(frozen=True)
class SkillId:
    """A validated, simple-token identifier for a skill.

    Mirrors :class:`~jarvis.domain.capability.CapabilityId` exactly --
    used as a dict key, so it must be a single token: non-empty and
    free of whitespace (e.g. ``"filesystem"``, ``"job_research"``).

    Raises:
        ValueError: If ``value`` is empty or contains whitespace.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate ``value`` is a non-empty, whitespace-free token."""
        if not self.value:
            msg = "SkillId must not be empty."
            raise ValueError(msg)
        if any(ch.isspace() for ch in self.value):
            msg = f"SkillId must not contain whitespace: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return the underlying token, for log fields and messages."""
        return self.value


@dataclass(frozen=True)
class SkillDescriptor:
    """A skill's static, registered-once metadata.

    Attributes:
        id: The skill's identifier.
        name: A short, human-readable display name (e.g. "Filesystem").
            Must be non-empty.
        description: What this skill covers, shown in discovery output
            (e.g. ``jarvis skills list``/``jarvis skills show``). Must
            be non-empty.
        domain: The intent/domain this skill groups (e.g.
            ``"filesystem"``, ``"tasks"``, ``"memory"``). A plain,
            free-form label, not a closed enum -- new domains are added
            by registering a new skill, never by editing this type.
        capability_ids: The real, already-existing capability ids this
            skill groups together. Must be non-empty -- a skill with no
            real capability behind it describes nothing invocable, and
            is never itself a new execution path: invoking any of these
            ids still goes through the exact same authorization choke
            point it always did.
        instructions: Optional free-text guidance/context for a
            reasoning caller (e.g. WP-175's compact skill-aware
            context) -- never executable instructions, never a prompt
            that can invent a capability id outside ``capability_ids``.
            ``None`` means no additional guidance beyond ``description``.
        tags: Optional discoverability keywords (e.g. ``("files",
            "search")``), for filtering/search in a future discovery
            command. Defaults to empty.
    """

    id: SkillId
    name: str
    description: str
    domain: str
    capability_ids: tuple[CapabilityId, ...]
    instructions: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate the required text fields and that capability_ids is non-empty."""
        if not self.name:
            msg = "SkillDescriptor.name must not be empty."
            raise ValueError(msg)
        if not self.description:
            msg = "SkillDescriptor.description must not be empty."
            raise ValueError(msg)
        if not self.domain:
            msg = "SkillDescriptor.domain must not be empty."
            raise ValueError(msg)
        if not self.capability_ids:
            msg = (
                "SkillDescriptor.capability_ids must not be empty -- a skill "
                "must group at least one real, existing capability."
            )
            raise ValueError(msg)
