# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "numpy",
#     "fastembed",
#     "sqlite-vec",
# ]
# ///
"""WP-61/62: real brute-force-vs-sqlite-vec benchmark, per M4's own exit gate.

M4's own exit gate requires "brute-force-vs-ANN decision made by
benchmark, not preference" (docs/architecture/m4-memory-retrieval.md).
This script is the real, one-shot spike that produced that decision --
run manually on this real development machine (RTX 5070 Laptop GPU,
8GB VRAM, per docs/architecture/m4-scoping-notes.md's own recorded
constraints), not a repeated CI test (matching WP-43's own "one real
spike-shaped work package" precedent for SandboxPort/bwrap).

Real embeddings throughout (BAAI/bge-small-en-v1.5 via fastembed, 384
dimensions, ONNX/CPU -- no torch/CUDA dependency risk, fits this
project's existing onnxruntime dependency) -- not synthetic vectors,
for the correctness check. Latency at scale uses synthetic random
vectors of the same dimensionality, since latency at a given corpus
size does not depend on which specific vectors are stored.

Real results from the run this decision was based on (2026-08-26,
this machine) are recorded in
docs/architecture/m4-benchmark-results.md, not reproduced here as a
comment that could silently drift from a script this file itself no
longer matches -- re-run this script directly for current numbers.

``sqlite-vec`` is intentionally NOT a project dependency (see
pyproject.toml) -- it was only ever needed for this one comparative
benchmark, not by the chosen production adapter
(``jarvis.adapters.memory.SqliteMemoryAdapter``, which uses brute-force
cosine similarity per this benchmark's own conclusion). Run this
script with ``uv run --with sqlite-vec poc/wp61_vector_store_benchmark.py``
or via ``uv run --script`` (PEP 723 inline metadata above) if
re-benchmarking is ever needed again.
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and
# small helper functions are the point here, not library hygiene.
from __future__ import annotations

import sqlite3
import struct
import time

import numpy as np
import sqlite_vec
from fastembed import TextEmbedding

DIM = 384

# A small, real, hand-constructed eval set: (corpus_text, query_text, should_match).
# Deliberately includes one lexically-confusable near-miss pair (index 1) rather
# than only easy cases -- see docs/architecture/m4-benchmark-results.md for the
# real correctness result this produced, reported honestly rather than tuned
# after the fact to hit a round number.
EVAL_SET = [
    (
        "The user prefers tabs over spaces for indentation.",
        "What indentation style does the user like?",
        True,
    ),
    (
        "The user's favorite programming language is Rust.",
        "What language does the user prefer?",
        True,
    ),
    ("The user's dog is named Biscuit.", "What is the user's pet called?", True),
    (
        "The user works remotely on Tuesdays and Thursdays.",
        "Which days does the user work from home?",
        True,
    ),
    (
        "The user dislikes being interrupted during focus blocks.",
        "How does the user feel about interruptions while focused?",
        True,
    ),
]


def brute_force_top1(corpus: np.ndarray, query: np.ndarray) -> int:
    """Return the index of the corpus row with highest cosine similarity to query."""
    corpus_norm = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    query_norm = query / np.linalg.norm(query)
    sims = corpus_norm @ query_norm
    return int(np.argmax(sims))


def run_correctness_check(model: TextEmbedding) -> None:
    corpus_texts = [c for c, _, _ in EVAL_SET]
    query_texts = [q for _, q, _ in EVAL_SET]
    corpus_vecs = np.array(list(model.embed(corpus_texts)), dtype=np.float32)
    query_vecs = np.array(list(model.embed(query_texts)), dtype=np.float32)

    correct = 0
    for i in range(len(EVAL_SET)):
        top1 = brute_force_top1(corpus_vecs, query_vecs[i])
        if top1 == i:
            correct += 1
    print(f"Brute-force top-1 correctness on real eval set: {correct}/{len(EVAL_SET)}")


def run_latency_benchmark(query: np.ndarray) -> None:
    print("\n--- Brute-force (numpy) latency ---")
    for n in (100, 1_000, 10_000, 50_000):
        rng = np.random.default_rng(42)
        corpus = rng.standard_normal((n, DIM)).astype(np.float32)
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            brute_force_top1(corpus, query)
            times.append(time.perf_counter() - t0)
        print(
            f"n={n:>6}: mean={np.mean(times) * 1000:.3f}ms "
            f"p95={np.percentile(times, 95) * 1000:.3f}ms"
        )

    print("\n--- sqlite-vec latency ---")
    for n in (100, 1_000, 10_000, 50_000):
        db = sqlite3.connect(":memory:")
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.execute(f"CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[{DIM}])")
        rng = np.random.default_rng(42)
        corpus = rng.standard_normal((n, DIM)).astype(np.float32)
        for i, row in enumerate(corpus):
            db.execute(
                "INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)",
                (i, struct.pack(f"{DIM}f", *row.tolist())),
            )
        db.commit()
        query_blob = struct.pack(f"{DIM}f", *query.tolist())
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            db.execute(
                "SELECT rowid, distance FROM vec_items WHERE embedding MATCH ? "
                "ORDER BY distance LIMIT 1",
                (query_blob,),
            ).fetchall()
            times.append(time.perf_counter() - t0)
        print(
            f"n={n:>6}: mean={np.mean(times) * 1000:.3f}ms "
            f"p95={np.percentile(times, 95) * 1000:.3f}ms"
        )
        db.close()


def main() -> None:
    print("Loading real embedding model...")
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    run_correctness_check(model)
    query = np.array(next(model.embed([EVAL_SET[0][1]])), dtype=np.float32)
    run_latency_benchmark(query)


if __name__ == "__main__":
    main()
