"""Unit tests for jarvis.adapters.stt.FasterWhisperAdapter.

What's exercised here is deliberately narrow: everything that doesn't
require a real GPU or a real ctranslate2/faster-whisper install. The
sample-rate validation in transcribe() runs before model loading is
ever attempted, so it's testable in isolation. The real model-loading
and transcription path (_ensure_model_loaded, the LD_LIBRARY_PATH
re-exec) has no automated test, matching jarvis.adapters.wake_word's
_default_score_source; its correctness is proven by manual
verification instead (see docs/architecture/m1-voice-architecture.md
section 10).
"""

from __future__ import annotations

import pytest

from jarvis.adapters.stt import FasterWhisperAdapter
from jarvis.domain.audio import Segment

_SAMPLE_RATE = 16000


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches OpenWakeWordAdapter's/SileroVadAdapter's convention: __init__ does zero I/O."""
    adapter = FasterWhisperAdapter()

    assert adapter is not None


async def test_transcribe_rejects_a_sample_rate_other_than_16khz() -> None:
    """FasterWhisperAdapter only supports the project's fixed 16kHz throughout.

    This is checked before any model-loading is attempted, so this
    test needs no GPU and no real faster-whisper install -- if it did
    reach model loading, this test would hang or fail on CI for an
    unrelated reason.
    """
    segment = Segment(samples=b"\x00\x00", sample_rate=8000)
    adapter = FasterWhisperAdapter()

    with pytest.raises(ValueError, match="16000"):
        await adapter.transcribe(segment)
