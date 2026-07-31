"""The capability registry: where a capability's static metadata becomes lookupable by id.

:class:`CapabilityRegistry` is a mutable, in-memory, append-only-by-id
collection of :class:`~jarvis.domain.capability.CapabilityDescriptor`,
keyed by :class:`~jarvis.domain.capability.CapabilityId`. It has no I/O
of its own -- capabilities are registered by whatever loaded them (a
plugin's own module, eventually a plugin loader) calling
:meth:`register` with an already-constructed descriptor -- so, like
:class:`~jarvis.domain.audit.AuditChain`, it stays in ``domain`` despite
being stateful: the constraint that actually governs this ring is no
I/O, no async, no wall-clock/randomness, not immutability.

Registration never overwrites: a duplicate id is a real conflict (a
capability id silently coming to mean something different than what it
first meant is a security-relevant event, not a config nuisance), and
a lookup that misses is a loud, specific failure rather than
``None`` -- see :class:`~jarvis.domain.errors.CapabilityAlreadyRegistered`
and :class:`~jarvis.domain.errors.CapabilityNotRegistered`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import CapabilityAlreadyRegistered, CapabilityNotRegistered

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .capability import CapabilityDescriptor, CapabilityId


class CapabilityRegistry:
    """An in-memory lookup of every currently-known capability, keyed by id."""

    def __init__(self) -> None:
        """Build an empty registry."""
        self._descriptors: dict[CapabilityId, CapabilityDescriptor] = {}

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Register ``descriptor`` under its own id.

        Args:
            descriptor: The capability descriptor to register.

        Raises:
            CapabilityAlreadyRegistered: If a descriptor is already
                registered under ``descriptor.id``. Never overwrites --
                the caller must resolve the collision itself.
        """
        if descriptor.id in self._descriptors:
            msg = f"Capability {descriptor.id} is already registered."
            raise CapabilityAlreadyRegistered(msg)
        self._descriptors[descriptor.id] = descriptor

    def get(self, capability_id: CapabilityId) -> CapabilityDescriptor:
        """Look up the descriptor registered under ``capability_id``.

        Args:
            capability_id: The id to look up.

        Returns:
            The descriptor registered under ``capability_id``.

        Raises:
            CapabilityNotRegistered: If no descriptor is registered
                under ``capability_id``.
        """
        try:
            return self._descriptors[capability_id]
        except KeyError:
            msg = f"No capability is registered under {capability_id}."
            raise CapabilityNotRegistered(msg) from None

    def __contains__(self, capability_id: CapabilityId) -> bool:
        """Return whether a descriptor is registered under ``capability_id``."""
        return capability_id in self._descriptors

    def __len__(self) -> int:
        """Return the number of registered capabilities."""
        return len(self._descriptors)

    def __iter__(self) -> Iterator[CapabilityDescriptor]:
        """Iterate over every registered descriptor, each exactly once.

        Iteration order is not part of this class's contract.
        """
        return iter(self._descriptors.values())
