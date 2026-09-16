"""The skill registry: where a skill's static metadata becomes lookupable by id.

Mirrors :class:`~jarvis.domain.registry.CapabilityRegistry` exactly, on
purpose -- an in-memory, append-only-by-id, no-I/O collection of
:class:`~jarvis.domain.skill.SkillDescriptor`, keyed by
:class:`~jarvis.domain.skill.SkillId`. Registration never overwrites;
a lookup that misses is a loud, specific failure. No dynamic discovery
from disk, no manifest files, no plugin loading -- deferred, real
future work, matching :mod:`jarvis.domain.registry`'s own identical
scope note.

:func:`validate_skill_registry` is the one piece of real, non-trivial
logic here: it reuses the existing, real
:class:`~jarvis.domain.registry.CapabilityRegistry` to confirm every
skill's ``capability_ids`` names something that genuinely exists,
rather than inventing a second, parallel notion of what capabilities
exist. This is deliberately a free function, not baked into
:meth:`SkillRegistry.register`, because validating against a real
capability registry requires one to already be fully built -- callers
that register skills incrementally (e.g. a future out-of-tree plugin
loader adding one skill at a time) should not be forced to have a
complete, final ``CapabilityRegistry`` in hand before registering a
single skill. ``kernel.skills.build_default_skill_registry()`` (WP-173)
calls this once, immediately after building both registries in full.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import SkillAlreadyRegistered, SkillNotRegistered, SkillReferencesUnknownCapability

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .registry import CapabilityRegistry
    from .skill import SkillDescriptor, SkillId


class SkillRegistry:
    """An in-memory lookup of every currently-known skill, keyed by id."""

    def __init__(self) -> None:
        """Build an empty registry."""
        self._descriptors: dict[SkillId, SkillDescriptor] = {}

    def register(self, descriptor: SkillDescriptor) -> None:
        """Register ``descriptor`` under its own id.

        Args:
            descriptor: The skill descriptor to register.

        Raises:
            SkillAlreadyRegistered: If a descriptor is already
                registered under ``descriptor.id``. Never overwrites --
                the caller must resolve the collision itself.
        """
        if descriptor.id in self._descriptors:
            msg = f"Skill {descriptor.id} is already registered."
            raise SkillAlreadyRegistered(msg)
        self._descriptors[descriptor.id] = descriptor

    def get(self, skill_id: SkillId) -> SkillDescriptor:
        """Look up the descriptor registered under ``skill_id``.

        Args:
            skill_id: The id to look up.

        Returns:
            The descriptor registered under ``skill_id``.

        Raises:
            SkillNotRegistered: If no descriptor is registered under
                ``skill_id``.
        """
        try:
            return self._descriptors[skill_id]
        except KeyError:
            msg = f"No skill is registered under {skill_id}."
            raise SkillNotRegistered(msg) from None

    def __contains__(self, skill_id: SkillId) -> bool:
        """Return whether a descriptor is registered under ``skill_id``."""
        return skill_id in self._descriptors

    def __len__(self) -> int:
        """Return the number of registered skills."""
        return len(self._descriptors)

    def __iter__(self) -> Iterator[SkillDescriptor]:
        """Iterate over every registered descriptor, each exactly once.

        Iteration order is not part of this class's contract.
        """
        return iter(self._descriptors.values())


def validate_skill_registry(skills: SkillRegistry, capabilities: CapabilityRegistry) -> None:
    """Confirm every registered skill's ``capability_ids`` names a real, registered capability.

    Args:
        skills: The skill registry to validate.
        capabilities: The real capability registry to validate against
            (e.g. ``kernel.capabilities.build_default_registry()``).

    Raises:
        SkillReferencesUnknownCapability: If any registered skill names
            a capability id that ``capabilities`` does not contain.
            Reused, never a new, parallel definition of "exists" --
            this is the exact same ``CapabilityRegistry.__contains__``
            every real authorization call already relies on.
    """
    for skill in skills:
        for capability_id in skill.capability_ids:
            if capability_id not in capabilities:
                msg = f"Skill {skill.id} references unknown capability {capability_id!r}."
                raise SkillReferencesUnknownCapability(msg)
