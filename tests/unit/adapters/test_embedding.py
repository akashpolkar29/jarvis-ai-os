"""Unit tests for jarvis.adapters.embedding.FastEmbedAdapter.

Only construction is tested here -- calling embed() would trigger a
real Hugging Face model download, which no automated test in this
repository does (see the adapter's own module docstring and
docs/threat-model/v0.md's "Milestone 4 additions" for the real, manual
verification pass that exercised it live instead).
"""

from __future__ import annotations

from jarvis.adapters.embedding import FastEmbedAdapter


def test_construction_does_zero_io() -> None:
    """__init__ never touches the network or loads the real model -- purely instant."""
    adapter = FastEmbedAdapter()

    assert adapter._model is None
