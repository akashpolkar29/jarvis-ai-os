"""The embedding port: turning text into a real, comparable vector (WP-61).

:class:`EmbeddingPort` is the seam between a real, injectable
embedding model and ``jarvis.adapters.memory.SqliteMemoryAdapter``'s
own similarity search. Kept as a narrow, framework-agnostic Protocol
(plain ``tuple[float, ...]``, not a ``numpy`` array) so this port
itself does not force a particular embedding-library's own array type
on every caller -- the real adapter converts at its own boundary.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.embedding`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    """A real source of fixed-dimensionality embedding vectors for text."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one embedding vector per element of ``texts``, in the same order.

        Args:
            texts: The real text to embed, one or more strings.

        Returns:
            One vector per input string, same length and order as
            ``texts``. Every vector returned by a given adapter
            instance has the same dimensionality.
        """
        ...
