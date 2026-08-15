"""Raw, speech-segmented, and synthesized audio as domain value objects.

:class:`AudioChunk` is a buffer of raw, uninterpreted audio samples --
what a microphone (or a ring buffer) produces. :class:`Segment` is a
buffer that a voice-activity detector has already confirmed contains
speech, not silence or noise -- what :class:`~jarvis.ports.vad.VadPort`
produces and :class:`~jarvis.ports.stt.SttPort` consumes.
:class:`AudioStream` is synthesized speech ready for playback -- what
:class:`~jarvis.ports.tts.TtsPort` produces. All three share the same
shape deliberately (raw PCM bytes plus a sample rate) but are kept as
distinct types rather than one type with a role flag, so a caller can
never accidentally hand STT something that was never actually vetted
by VAD, or play back something that was never actually synthesized --
the type itself is the evidence.

All three store audio as raw bytes (16-bit signed little-endian PCM,
mono), not a numpy array: domain/ is stdlib-only (ADR-0029) and numpy
is not stdlib. Adapters convert to/from numpy as needed for real
processing.
"""

from __future__ import annotations

from dataclasses import dataclass

_BYTES_PER_SAMPLE = 2  # 16-bit signed PCM


def _validate_pcm16_mono(samples: bytes, sample_rate: int, type_name: str) -> None:
    if sample_rate <= 0:
        msg = f"{type_name}.sample_rate must be positive: {sample_rate!r}"
        raise ValueError(msg)
    if len(samples) % _BYTES_PER_SAMPLE != 0:
        msg = (
            f"{type_name}.samples must be 16-bit PCM (an even number of bytes): "
            f"got {len(samples)} bytes"
        )
        raise ValueError(msg)


@dataclass(frozen=True)
class AudioChunk:
    """A buffer of raw, uninterpreted audio: what a microphone produces.

    Attributes:
        samples: 16-bit signed little-endian PCM, mono.
        sample_rate: Samples per second (e.g. 16000).
    """

    samples: bytes
    sample_rate: int

    def __post_init__(self) -> None:
        """Validate ``sample_rate`` is positive and ``samples`` is well-formed 16-bit PCM."""
        _validate_pcm16_mono(self.samples, self.sample_rate, "AudioChunk")


@dataclass(frozen=True)
class Segment:
    """A buffer of audio a voice-activity detector has confirmed contains speech.

    Attributes:
        samples: 16-bit signed little-endian PCM, mono.
        sample_rate: Samples per second (e.g. 16000).
    """

    samples: bytes
    sample_rate: int

    def __post_init__(self) -> None:
        """Validate ``sample_rate`` is positive and ``samples`` is well-formed 16-bit PCM."""
        _validate_pcm16_mono(self.samples, self.sample_rate, "Segment")


@dataclass(frozen=True)
class AudioStream:
    """A buffer of synthesized speech audio, ready for playback.

    Attributes:
        samples: 16-bit signed little-endian PCM, mono.
        sample_rate: Samples per second (e.g. 22050).
    """

    samples: bytes
    sample_rate: int

    def __post_init__(self) -> None:
        """Validate ``sample_rate`` is positive and ``samples`` is well-formed 16-bit PCM."""
        _validate_pcm16_mono(self.samples, self.sample_rate, "AudioStream")
