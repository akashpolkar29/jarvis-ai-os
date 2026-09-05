"""WP-67: real kernel-path performance benchmark (10-phase pass, Phase 4).

A real, one-shot benchmark of three real kernel hot paths, run manually
on this development machine and recorded in
``docs/architecture/kernel-performance-benchmarks.md`` -- not a
repeated CI artifact, matching ``poc/wp61_vector_store_benchmark.py``'s
own established precedent exactly (PEP 723 inline script, ``uv run``
directly, results recorded separately so the doc cannot silently drift
from a script it no longer matches).

**Hard scope boundary, matching this pass's own instruction**: this
script only measures ``JsonFileAuditStorageAdapter``'s real, existing
whole-file-rewrite behavior at scale -- it does not, and this pass may
not, change that adapter's save/load format or attempt to fix its
already-known, already-documented gaps (the cross-process race, the
whole-file-replacement cost itself). Those remain open, awaiting the
user's own architecture decision, exactly as ``docs/threat-model/v0.md``
already states.

Three real things measured, each isolating a different real cost:

1. ``JsonFileAuditStorageAdapter.save()``/``.load()`` in isolation --
   real ``AuditChain``/``AuditRecord`` objects (one real ``Decision``,
   obtained via one real ``authorize_ping()`` call, reused to fill the
   chain), no embedding/orchestrator overhead -- isolates the file-I/O
   cost alone.
2. ``authorize_ping()`` end-to-end, called repeatedly against the same
   growing ``chain_path`` -- the real, full per-CLI-invocation cost
   (fresh registry + load + authorize + save) every real capability
   call in this codebase pays today.
3. ``authorize_and_remember()``/``authorize_and_recall()`` end-to-end,
   real ``FastEmbedAdapter`` embeddings, real ``SqliteMemoryAdapter`` --
   a genuinely new number: WP-61/62's own benchmark measured only the
   cosine-similarity math over synthetic vectors, never the real
   embedding-inference latency real callers actually pay.

Run directly: ``uv run poc/wp67_kernel_benchmark.py``
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and
# small helper functions are the point here, not library hygiene.
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.audit import AuditChain
from jarvis.kernel.memory import authorize_and_recall, authorize_and_remember
from jarvis.kernel.ping import authorize_ping


def _timed(fn: object, *args: object, **kwargs: object) -> tuple[float, object]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)  # type: ignore[operator]
    return (time.perf_counter() - start) * 1000, result


def benchmark_audit_storage_io() -> None:
    print("\n=== 1. JsonFileAuditStorageAdapter: save()/load() in isolation ===")
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-bench-audit-"))
    try:
        chain_path = tmp / "chain.json"
        decision = authorize_ping(
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )
        chain_path.unlink()

        print(f"{'size':>6} | {'save (ms)':>10} | {'load (ms)':>10}")
        chain = AuditChain()
        sizes = [10, 100, 500, 2000]
        next_size = 0
        for size in sizes:
            while next_size < size:
                chain.append(decision)
                next_size += 1
            storage = JsonFileAuditStorageAdapter(chain_path)
            save_ms, _ = _timed(storage.save, chain)
            load_ms, _ = _timed(storage.load)
            print(f"{size:>6} | {save_ms:>10.3f} | {load_ms:>10.3f}")
    finally:
        shutil.rmtree(tmp)


def benchmark_authorize_ping_end_to_end() -> None:
    print("\n=== 2. authorize_ping(): real end-to-end call, growing chain ===")
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-bench-ping-"))
    try:
        chain_path = tmp / "chain.json"
        checkpoints = {1, 10, 50, 100, 300, 600, 1000}
        target = max(checkpoints)
        print(f"{'call #':>7} | {'latency (ms)':>13}")
        for call_number in range(1, target + 1):
            latency_ms, _ = _timed(
                authorize_ping,
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=chain_path,
            )
            if call_number in checkpoints:
                print(f"{call_number:>7} | {latency_ms:>13.3f}")
    finally:
        shutil.rmtree(tmp)


def benchmark_memory_pipeline_end_to_end() -> None:
    print("\n=== 3. authorize_and_remember()/authorize_and_recall(): real embeddings ===")
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-bench-memory-"))
    try:
        chain_path = tmp / "chain.json"
        database_path = tmp / "memory.sqlite3"
        checkpoints = {1, 10, 50, 100, 200}
        target = max(checkpoints)

        # A real, one-time cost (first-use model download + ONNX session
        # load, ~30s on this machine's connection) that has nothing to do
        # with per-write latency -- warmed up here and excluded from the
        # timed rows below, and called out explicitly in the results doc
        # rather than left to silently distort "record #1"'s own number.
        authorize_and_remember(
            "warmup",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp / "warmup-chain.json",
            database_path=tmp / "warmup-memory.sqlite3",
        )

        print(f"{'record #':>9} | {'write (ms)':>10} | {'recall (ms)':>11}")
        for record_number in range(1, target + 1):
            write_ms, _ = _timed(
                authorize_and_remember,
                f"Real benchmark fact number {record_number} about the user's preferences.",
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=chain_path,
                database_path=database_path,
            )
            if record_number in checkpoints:
                recall_ms, _ = _timed(
                    authorize_and_recall,
                    "What are the user's preferences?",
                    limit=5,
                    physical_confirmation_available=True,
                    remote_confirmation_available=False,
                    chain_path=chain_path,
                    database_path=database_path,
                )
                print(f"{record_number:>9} | {write_ms:>10.3f} | {recall_ms:>11.3f}")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    benchmark_audit_storage_io()
    benchmark_authorize_ping_end_to_end()
    benchmark_memory_pipeline_end_to_end()
