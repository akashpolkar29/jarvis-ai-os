"""Contract test: adapters must structurally satisfy jarvis.ports.embedding.EmbeddingPort."""

from __future__ import annotations

from jarvis.adapters.embedding import FastEmbedAdapter
from jarvis.ports.embedding import EmbeddingPort


def test_fast_embed_adapter_satisfies_embedding_port() -> None:
    """FastEmbedAdapter is structurally an EmbeddingPort.

    Safe to construct with no arguments here: __init__ does zero I/O --
    the real model is loaded lazily, on first embed() call, never here.
    """
    adapter = FastEmbedAdapter()

    assert isinstance(adapter, EmbeddingPort)


def test_an_object_missing_embed_does_not_satisfy_embedding_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnEmbeddingSource:
        """Deliberately lacks embed()."""

    assert isinstance(NotAnEmbeddingSource(), EmbeddingPort) is False
