# ADR-0037: piper-tts (OHF-Voice/piper1-gpl) chosen over the archived original Piper repo

## Status

Accepted

## Date

2026-08-15

## Source

Work package WP-22 implementation (TtsPort + PiperTtsAdapter)

## Context

The original Piper TTS project (rhasspy/piper) was archived in October 2025. Building against an archived repository would mean depending on a project that receives no further fixes, security patches, or compatibility updates -- a real risk for a dependency this project expects to keep running on. The M1 architecture doc's own text flagged this as needing empirical confirmation at implementation time, not assumption from the doc's own wording alone.

## Decision

Confirmed empirically (PyPI API query, GitHub README/VOICES.md fetch, live Python API introspection against this real project, not just read from documentation): the actively maintained continuation is OHF-Voice/piper1-gpl, under the Open Home Foundation, installed via the PyPI package `piper-tts` (v1.6.1 at verification time). Same architecture as the original (VITS, exported to ONNX, embedded espeak-ng for phonemization), same real-time CPU-only performance profile. Core runtime dependencies are `onnxruntime` and `pathvalidate` -- CPU/ONNX only; `torch` sits behind an unused `train` extra and is never pulled in by `PiperTtsAdapter`'s actual usage.

`PiperTtsAdapter` (`jarvis.adapters.tts`) uses the voice model `en_US-lessac-medium` (`.onnx` + `.onnx.json`), fetched from Hugging Face `rhasspy/piper-voices` pinned to tag `v1.0.0` (a specific tag, not a mutable branch, to eliminate force-push risk -- the same URL-pinning discipline this project already applied to Silero VAD's model download in WP-21). `piper.voice.AudioChunk` (the library's own internal type) is deliberately never imported by that name in this codebase -- it collides with `jarvis.domain.audio.AudioChunk`, an unrelated domain value object -- and is only ever accessed via its attributes (`audio_int16_bytes`, `sample_rate`), never imported directly.

## Consequences

TTS output stays CPU-only and light, matching the M1 doc's dependency posture (`docs/architecture/m1-voice-architecture.md` section 8). Depending on an actively maintained fork rather than an archived repository means future security/compatibility fixes remain available; if OHF-Voice/piper1-gpl is ever archived or abandoned in turn, this decision -- and the empirical-verification method used to reach it -- should be revisited the same way, not assumed to still hold.
