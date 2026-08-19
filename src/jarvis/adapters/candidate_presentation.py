"""Adapters implementing jarvis.ports.candidate_presentation.CandidatePresentationPort.

:class:`TtsTextCandidatePresentationAdapter` is ADR-0040's real,
today-available surface: each candidate is spoken via
:class:`~jarvis.ports.tts.TtsPort` (a short, terse announcement --
full candidate content would be an unreasonable amount to listen to)
and printed in full to stdout for the human to actually read, then a
choice is read back from stdin as a 1-based index.

Audio playback (speaking a candidate announcement out loud) is this
adapter's own responsibility, not a further port -- playing
already-synthesized PCM through the default output device is a thin,
direct ``sounddevice`` call, not a port-worthy abstraction boundary,
matching ``kernel/voice_loop.py``'s own ``_play_audio_stream_sync`` and
its module docstring's reasoning for the same choice. Duplicated here
rather than imported: ``adapters`` may not depend on ``kernel``
(C1 layered architecture).

Testability seam, matching every adapter in this project: ``play_fn``
and ``read_selection_fn`` are constructor-injectable, defaulting to the
real ``sounddevice`` call and the real ``input()`` builtin -- unit
tests inject fakes for both, so no real audio device or real terminal
input is required to exercise this adapter's own presentation/parsing
logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.ports.candidate_presentation import InvalidSelectionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from jarvis.domain.audio import AudioStream
    from jarvis.domain.evidence import Candidate
    from jarvis.ports.tts import TtsPort

    PlayFn = Callable[[AudioStream], None]
    ReadSelectionFn = Callable[[str], str]


def _play_audio_stream_sync(audio: AudioStream) -> None:
    """The one real, untested-by-design piece of audio output: play synthesized speech.

    See the module docstring for why this is a direct call, not a
    port. Requires a real audio output device; not exercised by the
    automated suite, matching every other real-hardware path in this
    project (see docs/architecture/m1-voice-architecture.md section 10).
    """
    import numpy as np  # noqa: PLC0415 -- deliberately lazy, matching kernel/voice_loop.py
    import sounddevice as sd  # noqa: PLC0415 -- deliberately lazy, matching kernel/voice_loop.py

    samples = np.frombuffer(audio.samples, dtype=np.int16)
    sd.play(samples, samplerate=audio.sample_rate)
    sd.wait()


class TtsTextCandidatePresentationAdapter:
    """Presents candidates via TTS-plus-stdout, and reads a selection back from stdin."""

    def __init__(
        self,
        tts: TtsPort,
        play_fn: PlayFn | None = None,
        read_selection_fn: ReadSelectionFn | None = None,
    ) -> None:
        """Store the real TTS port and the (defaultable) I/O functions this adapter uses.

        Args:
            tts: Synthesizes each announcement. Owned by the caller.
            play_fn: Plays one synthesized announcement. Defaults to a
                real ``sounddevice``-backed implementation.
            read_selection_fn: Given a prompt string, returns the raw
                text the human typed. Defaults to the real ``input()``
                builtin.
        """
        self._tts = tts
        self._play_fn: PlayFn = play_fn or _play_audio_stream_sync
        self._read_selection_fn: ReadSelectionFn = read_selection_fn or input

    async def present_and_select(self, candidates: tuple[Candidate, ...]) -> Candidate:
        """Announce and print every candidate, then read and resolve a 1-based selection.

        Raises:
            InvalidSelectionError: If the human's input is not a
                number, or is out of the ``1..len(candidates)`` range.
        """
        for index, candidate in enumerate(candidates, start=1):
            announcement = (
                f"Candidate {index} of {len(candidates)}, from {candidate.author}, is ready."
            )
            audio = await self._tts.speak(announcement)
            self._play_fn(audio)
            print(f"--- Candidate {index} ({candidate.author}) ---")  # noqa: T201 -- the real text surface
            print(candidate.content)  # noqa: T201 -- the real text surface

        prompt = f"Choose a candidate (1-{len(candidates)}): "
        raw_choice = self._read_selection_fn(prompt)
        try:
            choice = int(raw_choice)
        except ValueError:
            msg = f"{raw_choice!r} is not a number."
            raise InvalidSelectionError(msg) from None
        if not 1 <= choice <= len(candidates):
            msg = f"{choice} is out of range 1-{len(candidates)}."
            raise InvalidSelectionError(msg)
        return candidates[choice - 1]
