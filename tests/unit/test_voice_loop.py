"""Unit tests for jarvis.kernel.voice_loop.run_voice_loop.

Every port run_voice_loop depends on is faked -- no real microphone,
GPU, TTS model, or display is touched. Authorization itself runs for
real, against a real tmp_path-backed audit chain, exactly like
tests/unit/test_ping.py, test_music.py, and test_files.py: the point
of these tests is the wiring (wake word -> VAD -> STT -> intent ->
confirm -> authorize -> speak), not re-proving those already-tested
composition functions work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.audio import AudioChunk, AudioStream, Segment
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.speaker_id import SpeakerScore
from jarvis.domain.transcript import Transcript
from jarvis.domain.wake_word import WakeEvent
from jarvis.kernel.voice_loop import run_voice_loop

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

_SAMPLE_RATE = 16000
_SOME_AUDIO = AudioChunk(samples=b"\x00\x00\x01\x00", sample_rate=_SAMPLE_RATE)
_SOME_SEGMENT = Segment(samples=b"\x00\x00\x01\x00", sample_rate=_SAMPLE_RATE)
_A_WAKE_EVENT = WakeEvent(score=0.9, audio=_SOME_AUDIO)


class _FakeWakeWordPort:
    """Yields a fixed list of WakeEvents, then ends -- unlike the real, unbounded adapter."""

    def __init__(self, events: list[WakeEvent]) -> None:
        self._events = events

    async def stream(self) -> AsyncIterator[WakeEvent]:
        for event in self._events:
            yield event


class _FakeVadPort:
    """Yields a fixed list of Segments regardless of the audio passed in."""

    def __init__(self, segments: list[Segment]) -> None:
        self._segments = segments

    async def segment(self, audio: AudioChunk) -> AsyncIterator[Segment]:
        del audio
        for seg in self._segments:
            yield seg


class _FakeSttPort:
    """Always transcribes to a fixed text, tagged Provenance.user() like the real port."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, audio: Segment) -> Tainted[Transcript]:
        del audio
        return Tainted(Transcript(text=self._text), Provenance.user())


class _FakeSpeakerIdPort:
    """Always reports the same fixed score -- content is irrelevant, it's audit/UX only."""

    def score(self, audio: Segment) -> SpeakerScore:
        del audio
        return SpeakerScore(verified=False, confidence=0.0)


class _FakeTtsPort:
    """Records every text it was asked to speak, in order."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(self, text: str) -> AudioStream:
        self.spoken.append(text)
        return AudioStream(samples=b"\x00\x00", sample_rate=22050)


class _FakePhysicalConfirmationPort:
    """Always answers with a fixed bool, recording every prompt it was asked."""

    def __init__(self, *, approve: bool) -> None:
        self._approve = approve
        self.prompts: list[tuple[str, float]] = []

    async def await_physical_confirmation(self, prompt: str, timeout_s: float) -> bool:
        self.prompts.append((prompt, timeout_s))
        return self._approve


def _no_playback(audio: AudioStream) -> None:
    """A play_fn that touches no real audio hardware."""
    del audio


class _FakeMediaPlayerPort:
    """Records which commands it was sent, touching no real media player over D-Bus."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def play(self) -> None:
        self.calls.append("play")

    def pause(self) -> None:
        self.calls.append("pause")

    def next_track(self) -> None:
        self.calls.append("next_track")

    def previous_track(self) -> None:
        self.calls.append("previous_track")


async def test_a_recognized_ping_command_is_confirmed_authorized_and_spoken(
    tmp_path: Path,
) -> None:
    """ping -> confirmed -> granted -> "Done." spoken, recorded in a real audit chain."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    chain_path = tmp_path / "audit_chain.json"

    await run_voice_loop(
        chain_path=chain_path,
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("ping"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["Done."]
    assert len(confirmation.prompts) == 1
    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1
    assert chain.verify().valid is True


async def test_a_recognized_command_denied_confirmation_speaks_not_approved(
    tmp_path: Path,
) -> None:
    """A resolved command whose physical confirmation is denied is never executed."""
    tts = _FakeTtsPort()
    media_player = _FakeMediaPlayerPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("play"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        media_player=media_player,
    )

    assert tts.spoken == ["Sorry, that wasn't approved."]
    assert media_player.calls == []  # denied: the real command is never sent


async def test_an_unrecognized_transcript_is_spoken_back_and_never_confirmed(
    tmp_path: Path,
) -> None:
    """UnrecognizedIntent is spoken back directly -- authorization/confirmation never runs."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    chain_path = tmp_path / "audit_chain.json"

    await run_voice_loop(
        chain_path=chain_path,
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("what time is it"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["I didn't understand that."]
    assert confirmation.prompts == []  # never even asked
    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 0  # nothing was authorized, so nothing was audited


async def test_a_recognized_read_command_speaks_the_file_content_when_granted(
    tmp_path: Path,
) -> None:
    """A granted "read" resolves to the file's actual content being spoken, not a status."""
    target = tmp_path / "notes.txt"
    target.write_text("hello from a test file")
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort(f"read {target}"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        allowed_root=tmp_path,
    )

    assert tts.spoken == ["hello from a test file"]


class _FakeEmbeddingPort:
    """Maps every text to the same vector, touching no real model download."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


async def test_a_recognized_remember_command_is_granted_and_spoken(tmp_path: Path) -> None:
    """ "remember <text>" -> confirmed -> granted -> "Done." spoken, recorded in the audit chain."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    chain_path = tmp_path / "audit_chain.json"

    await run_voice_loop(
        chain_path=chain_path,
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("remember I prefer tabs"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
    )

    assert tts.spoken == ["Done."]
    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1
    assert chain.verify().valid is True


async def test_a_recognized_remember_command_denied_confirmation_speaks_not_approved(
    tmp_path: Path,
) -> None:
    """A resolved "remember" whose physical confirmation is denied never reaches the store."""
    tts = _FakeTtsPort()
    database_path = tmp_path / "memory.sqlite3"

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("remember I prefer tabs"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )

    assert tts.spoken == ["Sorry, that wasn't approved."]
    assert database_path.exists() is False


async def test_the_confirmation_prompt_names_the_text_to_remember(tmp_path: Path) -> None:
    """The prompt for a resolved "remember" command names the actual text, not a generic label."""
    confirmation = _FakePhysicalConfirmationPort(approve=True)

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("remember I prefer tabs"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=_FakeTtsPort(),
        play_fn=_no_playback,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
    )

    assert len(confirmation.prompts) == 1
    prompt_text, _timeout = confirmation.prompts[0]
    assert "I prefer tabs" in prompt_text


async def test_zero_vad_segments_produces_no_speech_and_no_confirmation(tmp_path: Path) -> None:
    """If VAD finds no speech in a WakeEvent's audio, nothing is spoken or confirmed."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([]),
        stt=_FakeSttPort("ping"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == []
    assert confirmation.prompts == []


async def test_multiple_wake_events_are_each_handled_independently(tmp_path: Path) -> None:
    """Two separate WakeEvents each produce their own resolved-and-spoken outcome."""
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT, _A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("ping"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["Done.", "Done."]


async def test_the_confirmation_prompt_names_the_resolved_capability(tmp_path: Path) -> None:
    """The prompt shown for physical confirmation is specific to what was actually resolved."""
    confirmation = _FakePhysicalConfirmationPort(approve=True)

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("pause"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=_FakeTtsPort(),
        play_fn=_no_playback,
        media_player=_FakeMediaPlayerPort(),
    )

    assert len(confirmation.prompts) == 1
    prompt_text, _timeout = confirmation.prompts[0]
    assert "music.pause" in prompt_text
