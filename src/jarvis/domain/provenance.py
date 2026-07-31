"""Provenance tracking: how much to trust a value, and where it came from.

Two building blocks live here. :class:`Provenance` is an immutable
record of a value's trust level, sensitivity classification, and
contributing sources. :class:`Tainted` pairs an arbitrary value with
the :class:`Provenance` that produced it, and propagates that
provenance through ``map``/``combine`` transformations so a value
derived from untrusted input cannot quietly lose its taint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from .errors import TaintViolation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class Trust(IntEnum):
    """How much a value's origin should be trusted, lowest risk first."""

    USER_DIRECT = 0
    SYSTEM = 1
    UNTRUSTED_EXTERNAL = 2


class Classification(IntEnum):
    """How sensitive a value's content is, least sensitive first."""

    PUBLIC = 0
    PERSONAL = 1
    SENSITIVE = 2
    SECRET = 3


@dataclass(frozen=True)
class Provenance:
    """An immutable record of a value's trust level, sensitivity, and origin.

    Attributes:
        trust: How much the value's origin should be trusted.
        classification: How sensitive the value's content is.
        sources: Identifiers of everything that contributed to the value.
    """

    trust: Trust
    classification: Classification
    sources: frozenset[str]

    def merge(self, other: Provenance) -> Provenance:
        """Combine two provenances, keeping the more cautious of each field.

        Risk and sensitivity only ever propagate upward: the result is
        never more trusted or less sensitive than either input.

        Args:
            other: The provenance to merge with this one.

        Returns:
            A new ``Provenance`` with the maximum trust, the maximum
            classification, and the union of both sources.
        """
        return Provenance(
            trust=max(self.trust, other.trust),
            classification=max(self.classification, other.classification),
            sources=self.sources | other.sources,
        )

    @classmethod
    def merge_all(cls, items: Iterable[Provenance]) -> Provenance:
        """Fold :meth:`merge` over every item in ``items``.

        Args:
            items: The provenances to merge, in any order.

        Returns:
            The merge of every item in ``items``.

        Raises:
            ValueError: If ``items`` is empty. The provenance of nothing
                is not a meaningful default and must never be invented
                silently.
        """
        iterator = iter(items)
        try:
            first = next(iterator)
        except StopIteration:
            msg = "Provenance.merge_all() requires at least one Provenance."
            raise ValueError(msg) from None
        result = first
        for item in iterator:
            result = result.merge(item)
        return result

    @classmethod
    def user(cls) -> Provenance:
        """Build the provenance of a value the user typed in directly."""
        return cls(
            trust=Trust.USER_DIRECT,
            classification=Classification.PUBLIC,
            sources=frozenset(),
        )

    @classmethod
    def system(cls) -> Provenance:
        """Build the provenance of a value JARVIS itself generated."""
        return cls(
            trust=Trust.SYSTEM,
            classification=Classification.PUBLIC,
            sources=frozenset(),
        )

    @classmethod
    def external(cls, source: str, classification: Classification) -> Provenance:
        """Build the provenance of a value read from an untrusted external source.

        Args:
            source: An identifier for the external source (a URL, a
                filename, a plugin name).
            classification: How sensitive the value's content is.

        Returns:
            A ``Provenance`` tagged ``UNTRUSTED_EXTERNAL`` with ``source``
            as its sole contributing source.
        """
        return cls(
            trust=Trust.UNTRUSTED_EXTERNAL,
            classification=classification,
            sources=frozenset({source}),
        )

    @property
    def is_tainted(self) -> bool:
        """Return whether this provenance's trust is untrusted-external."""
        return self.trust == Trust.UNTRUSTED_EXTERNAL


@dataclass(frozen=True)
class Tainted[T]:
    """A value paired with the :class:`Provenance` that produced it."""

    value: T
    provenance: Provenance

    def map[U](self, fn: Callable[[T], U]) -> Tainted[U]:
        """Apply ``fn`` to the wrapped value, leaving provenance untouched.

        Args:
            fn: A pure function from the wrapped value to a new value.

        Returns:
            A new ``Tainted`` with ``fn`` applied and identical provenance.
        """
        return Tainted(fn(self.value), self.provenance)

    def combine[U, V](self, other: Tainted[U], fn: Callable[[T, U], V]) -> Tainted[V]:
        """Combine this value with another, merging both provenances.

        Args:
            other: The other tainted value to combine with.
            fn: A pure function combining both wrapped values.

        Returns:
            A new ``Tainted`` wrapping ``fn``'s result, whose provenance
            is ``self.provenance.merge(other.provenance)``.
        """
        return Tainted(fn(self.value, other.value), self.provenance.merge(other.provenance))

    def require_trusted(self) -> T:
        """Return the wrapped value, if it is not tainted.

        Returns:
            The wrapped value.

        Raises:
            TaintViolation: If this value's provenance ``is_tainted``.
        """
        if self.provenance.is_tainted:
            msg = f"Value sourced from {sorted(self.provenance.sources)} is tainted."
            raise TaintViolation(msg)
        return self.value

    @classmethod
    def user(cls, value: T) -> Tainted[T]:
        """Wrap ``value`` with the provenance of direct user input."""
        return cls(value, Provenance.user())

    @classmethod
    def system(cls, value: T) -> Tainted[T]:
        """Wrap ``value`` with the provenance of system-generated input."""
        return cls(value, Provenance.system())

    @classmethod
    def external(cls, value: T, source: str, classification: Classification) -> Tainted[T]:
        """Wrap ``value`` with the provenance of an untrusted external source.

        Args:
            value: The value to wrap.
            source: An identifier for the external source.
            classification: How sensitive ``value``'s content is.
        """
        return cls(value, Provenance.external(source, classification))
