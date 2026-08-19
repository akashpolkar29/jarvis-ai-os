"""Record/replay cassette adapters implementing jarvis.ports.reasoning.ReasoningPort.

``docs/architecture/m2-reasoning-layer.md`` section 5's deliverable
#10 ("record/replay cassette harness -- also functions as a regression
corpus: replay every historical task when ladder logic changes") and
section 7 names ``CassetteRecorder``/``CassettePlayer`` directly.
Acceptance criterion #7: "Full ladder replays deterministically from
cassettes with the network disabled."

:class:`CassetteRecorder` wraps a real ``ReasoningPort`` adapter
(``family_a``, ``family_b``, ``local`` -- any of them, injected, never
imported directly here, so this module adds no C4 coupling), recording
every real ``(task, Candidate)`` interaction in order, then
:meth:`CassetteRecorder.save` writes them to a JSON file under
``tests/cassettes/``.

:class:`CassettePlayer` is how "the network disabled" becomes
structurally true, not merely configured: it loads a cassette file at
construction and never holds a reference to any real adapter, D-Bus
connection, or subprocess-spawning code at all -- there is no code
path here that could reach a real network or process, unlike a
"replay mode" flag on a real adapter would be. Replay is strictly
ordered (call *N* always returns recording *N*), matching how a
deterministic ladder replay actually works: the same task, run through
the same ladder logic, produces the same call sequence every time.
:class:`CassetteMismatchError` catches a ladder/cassette drift early
(the task string at call *N* no longer matches what was recorded) with
a clear, specific error instead of silently returning the wrong
Candidate for a different call. :class:`CassetteExhaustedError` catches
a replay asking for more calls than were ever recorded -- never
silently loops the recording or reaches for a real call to make up the
difference.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from jarvis.domain.evidence import Attempt
    from jarvis.ports.reasoning import ReasoningPort


class CassetteMismatchError(Exception):
    """Raised when a replayed call's task does not match what was recorded at that position."""


class CassetteExhaustedError(Exception):
    """Raised when a replay is asked for more calls than the cassette ever recorded."""


class CassetteRecorder:
    """Wraps a real ReasoningPort adapter, recording every call in order."""

    def __init__(self, real_provider: ReasoningPort) -> None:
        """Store the real adapter every call is delegated to and recorded from.

        Args:
            real_provider: The real ``ReasoningPort`` this recorder
                wraps. Owned by the caller -- never constructed here,
                matching every other adapter's constructor-injection
                pattern in this repo.
        """
        self._real_provider = real_provider
        self._recordings: list[dict[str, object]] = []

    async def generate(self, task: str, prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Delegate to the real provider, record the real interaction, and return its result."""
        tainted = await self._real_provider.generate(task, prior_attempts)
        self._recordings.append(
            {
                "task": task,
                "candidate_author": tainted.value.author,
                "candidate_content": tainted.value.content,
                "trust": tainted.provenance.trust.name,
                "classification": tainted.provenance.classification.name,
                "sources": sorted(tainted.provenance.sources),
            }
        )
        return tainted

    def save(self, path: Path) -> None:
        """Write every recorded interaction, in order, to ``path`` as JSON."""
        path.write_text(json.dumps(self._recordings, indent=2), encoding="utf-8")


class CassettePlayer:
    """Replays a recorded cassette's interactions, strictly in order, with no real I/O at all."""

    def __init__(self, recordings: Sequence[dict[str, object]]) -> None:
        """Store the already-loaded recordings this player replays from.

        Args:
            recordings: Every recorded interaction, in the order they
                must be replayed. Use :meth:`load` to build this from
                a real cassette file on disk.
        """
        self._recordings = recordings
        self._next_index = 0

    @classmethod
    def load(cls, path: Path) -> CassettePlayer:
        """Build a CassettePlayer from a real cassette file on disk."""
        recordings = json.loads(path.read_text(encoding="utf-8"))
        return cls(recordings)

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Return the next recorded interaction, in order -- never a real call.

        Raises:
            CassetteExhaustedError: If every recorded interaction has
                already been replayed.
            CassetteMismatchError: If ``task`` does not match what was
                recorded at this position -- a real signal that the
                ladder driving this replay has drifted from the
                recording, not something to silently paper over.
        """
        if self._next_index >= len(self._recordings):
            msg = (
                f"Cassette exhausted: {len(self._recordings)} interaction(s) recorded, "
                "one more was requested."
            )
            raise CassetteExhaustedError(msg)
        recording = self._recordings[self._next_index]
        if recording["task"] != task:
            msg = (
                f"Cassette mismatch at recording {self._next_index}: "
                f"recorded task {recording['task']!r}, replay asked for {task!r}."
            )
            raise CassetteMismatchError(msg)
        self._next_index += 1
        candidate = Candidate(
            author=str(recording["candidate_author"]), content=str(recording["candidate_content"])
        )
        provenance = Provenance(
            trust=Trust[str(recording["trust"])],
            classification=Classification[str(recording["classification"])],
            sources=frozenset(recording["sources"]),  # type: ignore[call-overload]
        )
        return Tainted(candidate, provenance)
