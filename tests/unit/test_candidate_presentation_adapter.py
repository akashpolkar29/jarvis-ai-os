"""Unit tests for jarvis.adapters.candidate_presentation.TtsTextCandidatePresentationAdapter.

What's mocked and why: TtsPort and the two I/O functions
(play_fn/read_selection_fn) are faked -- no real TTS model or audio
device is required. Text output is captured via pytest's own
``capsys``, matching this project's convention of testing real,
observable behavior rather than mocking ``print`` itself.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.candidate_presentation import TtsTextCandidatePresentationAdapter
from jarvis.domain.audio import AudioStream
from jarvis.domain.evidence import Candidate
from jarvis.ports.candidate_presentation import InvalidSelectionError

_SILENCE = AudioStream(samples=b"\x00\x00", sample_rate=16000)


class _FakeTts:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(self, text: str) -> AudioStream:
        self.spoken.append(text)
        return _SILENCE


def _adapter(
    tts: _FakeTts, selection: str
) -> tuple[TtsTextCandidatePresentationAdapter, list[AudioStream]]:
    played: list[AudioStream] = []
    adapter = TtsTextCandidatePresentationAdapter(
        tts, play_fn=played.append, read_selection_fn=lambda _prompt: selection
    )
    return adapter, played


_CANDIDATES = (
    Candidate(author="family_a", content="answer one"),
    Candidate(author="family_b", content="answer two"),
)


async def test_present_and_select_returns_the_chosen_candidate() -> None:
    tts = _FakeTts()
    adapter, _played = _adapter(tts, "2")

    result = await adapter.present_and_select(_CANDIDATES)

    assert result is _CANDIDATES[1]


async def test_present_and_select_announces_every_candidate_via_tts() -> None:
    tts = _FakeTts()
    adapter, played = _adapter(tts, "1")

    await adapter.present_and_select(_CANDIDATES)

    assert len(tts.spoken) == len(_CANDIDATES)
    assert len(played) == len(_CANDIDATES)


async def test_present_and_select_prints_full_candidate_content_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tts = _FakeTts()
    adapter, _played = _adapter(tts, "1")

    await adapter.present_and_select(_CANDIDATES)

    captured = capsys.readouterr()
    assert "answer one" in captured.out
    assert "answer two" in captured.out


async def test_present_and_select_raises_on_a_non_numeric_selection() -> None:
    tts = _FakeTts()
    adapter, _played = _adapter(tts, "not a number")

    with pytest.raises(InvalidSelectionError, match="not a number"):
        await adapter.present_and_select(_CANDIDATES)


async def test_present_and_select_raises_on_an_out_of_range_selection() -> None:
    tts = _FakeTts()
    adapter, _played = _adapter(tts, "99")

    with pytest.raises(InvalidSelectionError, match="out of range"):
        await adapter.present_and_select(_CANDIDATES)
