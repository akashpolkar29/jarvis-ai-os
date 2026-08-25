# M4 vector-store benchmark results (WP-61/62)

## Status

Real, recorded results from a real run -- not a projection, not a repeated CI artifact.

## Date

2026-08-26

## What this is

M4's own exit gate requires the brute-force-vs-ANN decision be "made
by benchmark, not preference" (`docs/architecture/m4-memory-retrieval.md`).
This document records the real numbers `poc/wp61_vector_store_benchmark.py`
produced when run on this real development machine, and the real
decision made from them. Re-run the script directly for current
numbers -- this document is a snapshot, not a live-updating source of
truth.

## Machine

RTX 5070 Laptop GPU (8GB VRAM), 300GB free disk -- the same real
constraints `m4-scoping-notes.md` recorded during scoping. Embedding
inference ran CPU-only via ONNX (`fastembed`, `BAAI/bge-small-en-v1.5`,
384 dimensions) -- the GPU was not used for this benchmark; see
"Embedding pipeline" below for why.

## Correctness (real embeddings, small hand-built eval set)

5 real (corpus, query, expect-top-1-match) pairs, each corpus sentence
a plausible memorized personal-assistant fact, each query a plausible
real recall question. One pair (index 1: corpus "The user's favorite
programming language is Rust." / query "What language does the user
prefer?") is a deliberately-included lexically-confusable near-miss --
the word "prefer(s)" overlaps more strongly with the tabs/indentation
sentence than "Rust" does with "language," which is exactly the kind
of real ambiguity a small local embedding model can genuinely get
wrong.

**Result: 4/5 top-1 correct.** The one miss is the deliberately-hard
pair named above (cosine similarity 0.703 to the wrong sentence vs.
0.690 to the right one -- a genuine near-tie, not a large error).
Reported as-is, not tuned after the fact by removing or rewording the
hard pair to reach 5/5 -- an embedding model this small (bge-small,
~130MB) making an occasional near-tie error on a genuinely ambiguous
query is a real, honest characteristic of this choice, not hidden.

## Latency (synthetic vectors, same dimensionality, real cosine/SQL math)

Mean over 20 queries per row; top-1 nearest-neighbor query only.

| Corpus size | Brute-force (numpy) mean | sqlite-vec mean |
|---|---|---|
| 100 | 0.035ms | 0.105ms |
| 1,000 | 0.174ms | 0.309ms |
| 10,000 | 3.569ms | 2.522ms |
| 50,000 | 27.165ms | 13.180ms |

Real crossover point: somewhere between 1,000 and 10,000 records.
Below it, brute-force is faster in absolute terms (sqlite-vec's
per-query SQL/extension overhead dominates at small n); above it,
sqlite-vec's real ANN-ish indexing wins, roughly 2x at 50,000.

## Decision

**Brute-force numpy cosine similarity**, not `sqlite-vec`, is the real
mechanism `jarvis.adapters.memory.SqliteMemoryAdapter` uses.

Reasoning from the real numbers above, not from `m4-scoping-notes.md`'s
own (explicitly-labeled "not a recommendation") research alone:
`m4-scoping-notes.md` estimated this store's realistic real scale at
"thousands to low tens of thousands" of records for a single-user,
personal-assistant-scale memory store. At the low end of that range
(hundreds to a couple thousand), brute-force is both simpler (no
extension-loading, no float-blob serialization format, one fewer
runtime dependency) and measurably faster. At the high end (10k-50k),
sqlite-vec's real advantage is genuine but small in absolute terms --
even the slower brute-force path's worst measured latency (27ms at
50,000 records) is well under any threshold that would be perceptible
in a voice-assistant interaction, and 50,000 memorized facts is
already an extreme upper bound for a single user's personal-assistant
memory store, not the expected case.

**`sqlite-vec` is not a project dependency** (removed from
`pyproject.toml` after this benchmark ran) -- it was evaluated fairly,
with real numbers, and not chosen; keeping an unused dependency around
"just in case" is not this project's convention. If real memory volume
ever grows well past the benchmarked range and brute-force's latency
becomes a real, measured problem (not a hypothetical one), this
document and `poc/wp61_vector_store_benchmark.py` are the starting
point for reopening this decision with new real numbers, not
re-litigating it from preference.

## Embedding pipeline

`fastembed` (ONNX Runtime backend, `BAAI/bge-small-en-v1.5`, 384-dim)
was chosen over a `torch`-based sentence-transformer model for one
real, explicit reason: this project already depends on `onnxruntime`
(for `faster-whisper`/wake-word inference), so `fastembed` adds no new
ML-runtime dependency family, no new CUDA/driver-version compatibility
surface, and runs correctly on CPU with no GPU involvement at all --
avoiding a real, unattended-overnight risk (a multi-GB `torch`+CUDA
install and model download with no one available to debug a driver
mismatch). This is a deliberate, real scope choice for this milestone,
not a claim that ONNX embeddings are categorically superior to
transformer-based ones -- named explicitly as a real, tracked
follow-up if embedding quality at real, larger scale ever needs
re-examination (`docs/threat-model/v0.md`'s "Milestone 4 additions").

The model itself downloads from Hugging Face on first use (~130MB,
one-time, cached under this machine's XDG cache directory thereafter)
-- a real, new network dependency this milestone introduces, distinct
from and not a violation of this project's data-egress privacy
principles (no user content is ever sent anywhere; only the fixed,
public model artifact is fetched in). Because of this, no automated
test in this repository triggers a real model download -- matching
this project's existing precedent for cloud-provider reasoning
adapters (tested via `tests/cassettes/` replay, never a live network
call in CI) and for hardware-dependent adapters
(`tests/unit/adapters/test_sandbox.py`'s real-GUI test, skipped
outside a real Wayland session). The real embedding pipeline was
verified live, once, in this development session -- recorded in
`docs/threat-model/v0.md`'s "Milestone 4 additions" section, not
re-run automatically.
