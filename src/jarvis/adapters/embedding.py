"""The real embedding adapter: BAAI/bge-small-en-v1.5 via fastembed's ONNX runtime.

Chosen over a ``torch``-based sentence-transformer model for one real,
explicit reason (recorded in full in
``docs/architecture/m4-benchmark-results.md``): this project already
depends on ``onnxruntime`` (``faster-whisper``, wake-word inference),
so this adds no new ML-runtime dependency family and no new
CUDA/driver-version compatibility surface -- it runs correctly on CPU
alone, avoiding a real, unattended-overnight risk this milestone was
built under (a multi-GB ``torch`` + CUDA install and model download with
no one available to debug a driver mismatch).

The real model (~130MB) downloads from Hugging Face on first use,
cached under this machine's XDG cache directory thereafter -- a real,
new network dependency, not a violation of this project's data-egress
privacy principles (no user content is ever sent anywhere; only the
fixed, public model artifact is fetched in). Because of this, no
automated test in this repository constructs the real
``fastembed.TextEmbedding`` model or calls :meth:`FastEmbedAdapter.embed`
-- matching this project's existing precedent for cloud-provider
reasoning adapters (cassette replay only, never a live call in CI) and
hardware-dependent adapters (skipped outside a real environment). The
real pipeline was verified live, once, in the development session that
built it -- see ``docs/threat-model/v0.md``'s "Milestone 4 additions".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

_MODEL_NAME = "BAAI/bge-small-en-v1.5"


class FastEmbedAdapter:
    """A real ``EmbeddingPort`` backed by fastembed's ONNX runtime.

    ``__init__`` does zero I/O -- matching every other adapter in this
    repo's own "safe to construct with no arguments" convention
    (``SecretServiceAdapter``, ``SystemClockAdapter``). The real model
    is loaded lazily, on the first :meth:`embed` call, and cached on
    this instance thereafter.
    """

    def __init__(self) -> None:
        """Store nothing but a placeholder for the lazily-loaded model."""
        self._model: TextEmbedding | None = None

    def _loaded_model(self) -> TextEmbedding:
        if self._model is None:
            # Deferred import: keeps __init__ I/O-free (see class docstring).
            from fastembed import TextEmbedding  # noqa: PLC0415

            self._model = TextEmbedding(model_name=_MODEL_NAME)
        return self._model

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one real 384-dimension embedding vector per element of ``texts``.

        Loads the real model on first call (see class docstring) --
        this is real, network-and-disk I/O, not something any
        automated test in this repository exercises.
        """
        model = self._loaded_model()
        return tuple(
            tuple(float(component) for component in vector) for vector in model.embed(list(texts))
        )
