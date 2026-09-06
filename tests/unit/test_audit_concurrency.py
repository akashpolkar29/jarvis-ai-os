"""Real, deterministic concurrency tests for jarvis.domain.audit.AuditChain.

Not a real-timing-luck test (which would be flaky, exactly the kind of
test this project's own discipline avoids): each test below uses a
real threading.Event to force a specific, guaranteed interleaving
rather than hoping the OS scheduler produces one.
"""

from __future__ import annotations

import threading
from unittest.mock import patch

import jarvis.domain.audit as audit_module
from jarvis.domain.audit import GENESIS_PREVIOUS_HASH, AuditChain
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.policy import Decision, PolicyContext, evaluate
from jarvis.domain.provenance import Provenance, Tainted

_ORIGINAL_COMPUTE = audit_module._compute_record_hash
_TWO_CONCURRENT_CALLERS = 2


def _decision() -> Decision:
    """Build a real, granted Decision -- content is irrelevant, only that each call is distinct."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId("test.capability"),
        effects=Effect.READ_LOCAL,
        description="A test capability.",
    )
    invocation = CapabilityInvocation(descriptor, Tainted({}, Provenance.user()))
    context = PolicyContext(
        physical_confirmation_available=True, remote_confirmation_available=True
    )
    return evaluate(invocation, context)


def test_append_serializes_concurrent_callers_so_sequences_never_collide() -> None:
    """A real, deterministic proof that AuditChain.append()'s internal lock actually serializes.

    Found by this pass's own investigation (property-matrix/fuzzing/
    concurrency pass, Track 3, 2026-09-04): before the fix, two
    threads racing on the same AuditChain instance could both read
    sequence=0 from the same pre-append state, producing two audit
    records that both claim the same position in the hash chain -- a
    real, reproducible corruption. This test forces the first caller
    to block mid-append (inside _compute_record_hash, which now runs
    under the lock) via a real threading.Event, starts a second
    caller, and proves the second caller is genuinely blocked -- not
    racing ahead -- until the first one finishes. Both then complete
    with correct, non-colliding sequence numbers.
    """
    chain = AuditChain()
    first_call_entered = threading.Event()
    release_first_call = threading.Event()
    call_count = 0

    def _blocking_compute(
        sequence: int, decision: Decision, previous_hash: str, written_at: str
    ) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_call_entered.set()
            release_first_call.wait(timeout=5)
        return _ORIGINAL_COMPUTE(sequence, decision, previous_hash, written_at)

    results: list[object] = []

    def _worker() -> None:
        results.append(chain.append(_decision(), written_at="2026-09-07T00:00:00+00:00"))

    with patch.object(audit_module, "_compute_record_hash", side_effect=_blocking_compute):
        first_thread = threading.Thread(target=_worker)
        first_thread.start()
        assert first_call_entered.wait(timeout=5), "first caller never entered its critical section"

        # The first caller is now blocked *inside* the lock. A second,
        # real concurrent caller must be unable to make any progress
        # at all -- not even to call _compute_record_hash once -- until
        # the first one finishes and releases the lock.
        second_thread = threading.Thread(target=_worker)
        second_thread.start()
        second_thread.join(timeout=0.2)
        assert second_thread.is_alive(), "second caller was not genuinely blocked by the lock"
        assert call_count == 1, (
            "second caller reached _compute_record_hash before the lock released"
        )

        release_first_call.set()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)

    assert len(chain) == _TWO_CONCURRENT_CALLERS
    sequences = sorted(record.sequence for record in results)  # type: ignore[attr-defined]
    assert sequences == [0, 1]
    result = chain.verify()
    assert result.valid is True

    previous_hashes = {record.previous_hash for record in results}  # type: ignore[attr-defined]
    assert GENESIS_PREVIOUS_HASH in previous_hashes


def test_many_real_concurrent_appends_never_produce_a_duplicate_sequence() -> None:
    """A real, unforced concurrent stress test -- real OS scheduling, no injected interleaving.

    Complements the deterministic test above: this one exercises real,
    natural thread scheduling across enough concurrent callers that,
    were the lock ever removed or subtly broken, a collision would be
    very likely to surface. Not a substitute for the deterministic
    test (a clean run here proves nothing removed, only that this run
    didn't get unlucky) -- kept as an additional, real-world-shaped
    check the deterministic test's own narrow, forced interleaving
    doesn't cover (many callers, not just two).
    """
    chain = AuditChain()
    thread_count = 32

    def _worker() -> None:
        chain.append(_decision(), written_at="2026-09-07T00:00:00+00:00")

    threads = [threading.Thread(target=_worker) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(chain) == thread_count
    sequences = sorted(record.sequence for record in chain)
    assert sequences == list(range(thread_count))
    result = chain.verify()
    assert result.valid is True
