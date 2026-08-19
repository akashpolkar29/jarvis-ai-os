"""Unit tests for jarvis.adapters.reasoning.cassette.CassetteRecorder/CassettePlayer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.reasoning.cassette import (
    CassetteExhaustedError,
    CassetteMismatchError,
    CassettePlayer,
    CassetteRecorder,
)
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt


class _FakeRealProvider:
    """A minimal, test-local stand-in for a real ReasoningPort, used to seed a recording."""

    def __init__(self, responses: list[Tainted[Candidate]]) -> None:
        self._responses = responses
        self._calls = 0

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        response = self._responses[self._calls]
        self._calls += 1
        return response


def _tainted(author: str, content: str) -> Tainted[Candidate]:
    provenance = Provenance(
        trust=Trust.UNTRUSTED_EXTERNAL,
        classification=Classification.PUBLIC,
        sources=frozenset({author}),
    )
    return Tainted(Candidate(author=author, content=content), provenance)


async def test_recorder_delegates_to_the_real_provider_and_returns_its_result() -> None:
    real = _FakeRealProvider([_tainted("family_a", "the real answer")])
    recorder = CassetteRecorder(real)

    result = await recorder.generate("do the task", ())

    assert result.value.content == "the real answer"


async def test_recorder_then_player_round_trips_through_a_real_file(tmp_path: Path) -> None:
    real = _FakeRealProvider([_tainted("family_a", "first"), _tainted("family_a", "second")])
    recorder = CassetteRecorder(real)
    await recorder.generate("task one", ())
    await recorder.generate("task two", ())
    cassette_path = tmp_path / "example.json"
    recorder.save(cassette_path)

    player = CassettePlayer.load(cassette_path)
    first = await player.generate("task one", ())
    second = await player.generate("task two", ())

    assert first.value.content == "first"
    assert second.value.content == "second"


async def test_player_preserves_the_recorded_provenance(tmp_path: Path) -> None:
    real = _FakeRealProvider([_tainted("family_a", "answer")])
    recorder = CassetteRecorder(real)
    await recorder.generate("task", ())
    cassette_path = tmp_path / "example.json"
    recorder.save(cassette_path)

    player = CassettePlayer.load(cassette_path)
    result = await player.generate("task", ())

    assert result.provenance.trust is Trust.UNTRUSTED_EXTERNAL
    assert result.provenance.classification is Classification.PUBLIC
    assert result.provenance.sources == frozenset({"family_a"})


async def test_player_raises_cassette_exhausted_when_asked_for_more_than_was_recorded() -> None:
    player = CassettePlayer([])

    with pytest.raises(CassetteExhaustedError):
        await player.generate("any task", ())


async def test_player_raises_cassette_mismatch_when_the_task_does_not_match() -> None:
    player = CassettePlayer(
        [
            {
                "task": "the recorded task",
                "candidate_author": "family_a",
                "candidate_content": "answer",
                "trust": "SYSTEM",
                "classification": "PUBLIC",
                "sources": [],
            }
        ]
    )

    with pytest.raises(CassetteMismatchError):
        await player.generate("a completely different task", ())
