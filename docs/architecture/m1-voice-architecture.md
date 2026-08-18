# JARVIS — M1: Voice Architecture

**Status:** Implemented (WP-19 through WP-27, tagged v0.2.0) · **Version:** 0.1 · **Grounded in:** confirmed hardware (RTX 5070 Laptop, 8GB VRAM, CUDA 13.2 working, GNOME/Wayland, 30GB RAM)
**Depends on:** M0 (tagged v0.1.1, complete)
**Scope:** Architecture as originally approved, annotated in place where implementation diverged from or extended the plan (see sections 4, 6, 7, 9, and 11) rather than left silently stale.

---

## 0. One correction to an earlier assumption

Piper TTS itself was archived in October 2025. The current, actively maintained project is OHF-Voice/piper1-gpl under the Open Home Foundation, at v1.6.0 as of July 2026, installed via `pip install piper-tts`. Same architecture (VITS, exported to ONNX, embedded espeak-ng for phonemization), same real-time CPU-only performance, just a different maintainer and package name. Using `piper-tts` (the OHF fork) is correct, not the original archived repo.

`faster-whisper` and `openWakeWord` are both still current and actively recommended for exactly this hardware profile in 2026 — faster-whisper specifically noted as the best choice for NVIDIA GPU Python pipelines, which is exactly what this machine has.

---

## 1. The one finding that matters more than the pipeline

M0's threat model ended with an honest admission (Finding 2, docs/threat-model/v0.md): CONFIRM and MANUAL_ONLY currently provide identical real-world protection, because the only ConfirmationPort adapter that exists (ManualConfirmationAdapter) just echoes back a CLI boolean. Anyone who can run the jarvis binary can claim physical presence and have it accepted at face value.

M1 is the first point in this project where that gap can actually be closed for real, and closing it should be M1's central design goal, not a side effect of adding voice.

Here's why voice makes this urgent rather than optional: the moment a spoken command can trigger a capability invocation, physical presence needs to mean something a voice alone cannot produce. If M1 ships voice input without upgrading confirmation, a recording of you, or a video call playing your voice, could satisfy MANUAL_ONLY exactly as well as a CLI flag does today. That is precisely the replay/cloning attack ADR-0012 named as the reason voice can never be an authorization boundary.

The fix: a ConfirmationPort adapter backed by a genuine physical action, a keypress or mouse click on a small, focused GTK4 dialog, replaces the self-reported CLI boolean for anything voice-triggered. A spoken command can request a MANUAL_ONLY action, but granting it requires physically pressing a key or clicking a button on the screen in front of the user. That is not defeated by a recording, a video call, or another voice in the room, because none of those can move an actual hand.

This does not make MANUAL_ONLY bulletproof against an attacker who already has full control of the session. But it closes the specific, previously-honest gap: voice alone can no longer satisfy the tier meant to require physical presence.

---

## 2. Revised pipeline

Microphone (PipeWire)
  -> Ring buffer (in-memory only, never written to disk, per ADR-0018)
  -> Wake word detection (openWakeWord, CPU, always running, near-zero GPU cost)
     triggers on a wake phrase
  -> VAD, voice activity detection (Silero VAD, CPU, trims silence)
  -> Speech-to-text (faster-whisper, GPU/CUDA, runs ONLY after wake word, not continuously)
  -> Speaker filter (optional, non-authoritative, see section 3)
  -> Intent resolution (a rule-based resolver; full LLM understanding is M2, not M1 --
     built fresh in WP-25 as kernel.intent.resolve_intent(), not reused from M0: M0
     never actually built any text -> capability mapping, despite this doc's original
     wording implying one already existed. The closest M0 analog was argparse's own
     CLI subcommand dispatch, which only works because argparse has already done the
     parsing -- it never faces raw free-form text the way an SttPort transcript does.
     See kernel/intent.py's own module docstring for the full account.)
  -> AuthorizationOrchestrator.authorize_by_id(...)   [unchanged from M0]
       CONFIRM/MANUAL_ONLY routed through the new physical-keypress ConfirmationPort adapter
  -> Capability executes (existing music/file capabilities, unchanged)
  -> Text-to-speech (piper-tts, CPU) speaks the result

What's genuinely new here vs. M0: everything above the AuthorizationOrchestrator line. The policy engine, the audit chain, the capability registry, and the two existing capabilities are completely untouched. That is the actual test of whether M0's architecture was sound: if voice can only plug in as new adapters feeding the exact same orchestrator, the ports-and-adapters design did its job.

---

## 3. The speaker-filter boundary

ADR-0012 established this in M0: voice and speaker verification are a convenience filter and an audit signal, never an authorization boundary. M1 is where this stops being a principle on paper and becomes real code that is tempting to get wrong under time pressure.

The concrete risk: it would be easy, and feel reasonable, to write something like "if speaker_match: physical_confirmation_available = True." That would directly violate ADR-0012, and would mean a good enough voice clone or a recording of the real user specifically, not just anyone, could pass MANUAL_ONLY.

The rule for M1, as a structural constraint, not just a comment: SpeakerIdPort's output must never appear anywhere near PolicyContext construction. It is an audit-log field and a UX signal only, never an input to tier-satisfaction logic in evaluate(). The physical-keypress confirmation from section 1 is the only thing allowed to set physical_confirmation_available to True.

---

## 4. Ports

WakeWordPort: stream() -> AsyncIterator[WakeEvent]
  WakeEvent gained a required `audio: AudioChunk` field during WP-25 (ADR-0033),
  not originally planned here: VadPort.segment() needs real captured audio to
  operate on, and this doc's original pipeline diagram implied a connection
  between wake-word detection and VAD that neither port's frozen WP-20/WP-21
  signature actually provided. See ADR-0033 for the gap, the options considered,
  and why WakeEvent -- not a new port -- is where that audio is carried.
VadPort: segment(audio: AudioChunk) -> AsyncIterator[Segment]
SttPort: async transcribe(audio: Segment) -> Tainted[Transcript]
TtsPort: async speak(text: str) -> AudioStream
SpeakerIdPort: score(audio: Segment) -> SpeakerScore   [audit/UX only, see section 3]
PhysicalConfirmationPort: async await_physical_confirmation(prompt: str, timeout_s: float) -> bool

SttPort.transcribe returns Tainted[Transcript]. A spoken command is Provenance.user() (USER_DIRECT), the same trust level as a typed CLI argument. Voice input gets exactly the trust level M0 already gives typed input, no more, no less.

---

## 5. Threat model additions (to append to docs/threat-model/v0.md)

- Always-on listening is a new, permanent privacy surface. Wake-word detection runs continuously on-device. It must never touch the network (openWakeWord is fully local) and the ring buffer feeding it must never be written to disk under any circumstance, matching ADR-0018 exactly, extended from "no audio persisted" to "no audio persisted, including transiently during wake-word evaluation."
- A legal note carried forward from the original M0 review: recording someone else's non-public spoken word without consent is treated seriously under German law (paragraph 201 StGB). A household microphone that can capture flatmates or visitors is exactly the situation that contemplates. The ring-buffer-only, never-persisted design is a direct mitigation.
- The Finding 2 closure becomes a new, explicit claim once section 1 ships: "MANUAL_ONLY now requires a physical keypress/click that voice alone cannot produce," and this needs its own test proving a simulated or injected keypress event is rejected the same way M0's original synthetic-input interlock was designed to prevent.

---

## 6. New ADRs this milestone needed

Written for real during implementation, numbered 0033-0037 (the next available
numbers at the time each was written, checked directly against docs/adr/, not
the guesses originally sketched here):

ADR-0033: WakeEvent carries the triggering audio, via the existing ring buffer -- an
  unplanned finding from WP-25 (see section 4's WakeWordPort note above), not
  anticipated when this doc was first drafted.
ADR-0034: Speaker verification is audit/UX only, mechanically enforced (operationalizes
  ADR-0012, not ADR-0005 as originally mis-cited in this doc)
ADR-0035: A genuine physical-keypress ConfirmationPort closes threat-model Finding 2 --
  named PhysicalConfirmationPort, deliberately a separate port from ConfirmationPort,
  not a new ConfirmationPort adapter (see section 4)
ADR-0036: Continuous CPU wake-word detection, GPU speech-to-text only after a trigger
ADR-0037: piper-tts (OHF-Voice/piper1-gpl) chosen over the archived original Piper repo

---

## 7. Package layout

src/jarvis/
  ports/
    wake_word.py          - WakeWordPort
    vad.py                 - VadPort
    stt.py                  - SttPort
    tts.py                  - TtsPort
    speaker_id.py          - SpeakerIdPort, audit/UX only, see section 3
    physical_confirmation.py - PhysicalConfirmationPort, the Finding 2 closure
  adapters/
    wake_word.py            - OpenWakeWordAdapter
    vad.py                   - SileroVadAdapter
    stt.py                    - FasterWhisperAdapter
    tts.py                    - PiperTtsAdapter
    speaker_id.py            - stub, decided and implemented as always-unverified (see section 11)
    physical_confirmation.py - Gtk4PhysicalConfirmationAdapter
  kernel/
    intent.py                 - resolve_intent(), built fresh in WP-25 -- not in the
                                 original plan, see section 4's Intent resolution note
    voice_loop.py             - wires wake word to VAD to STT to intent to authorize to TTS
  ui/
    confirm/                  - the GTK4 dialog itself, first real UI code in the project
  cli/
    main.py                    - add a "jarvis listen" subcommand, daemon-style, runs voice_loop

Nothing in domain/ or application/ changes. If any adapter ends up needing a domain change, that is a signal M0's design had a gap; stop and raise it explicitly rather than quietly patching around it.

---

## 8. Dependencies

openwakeword - wake word detection, ONNX-based, CPU, light
faster-whisper - speech-to-text, pulls in ctranslate2 (C++ inference engine), moderate weight
piper-tts (OHF-Voice/piper1-gpl) - text-to-speech, ONNX-based, CPU, light
Silero VAD - voice activity detection. Needs verification at implementation time whether to use the original torch-based distribution or a newer ONNX export that avoids the full torch dependency; torch alone is a heavy dependency for something this small and should be avoided if the ONNX path is viable. Do not assume either way without checking when this work package is actually reached.
sounddevice or PyAudio - raw microphone capture via PortAudio/PipeWire, light
PyGObject (gi) - GTK4 bindings for the confirmation dialog, moderate weight. This is exactly the case the M0 architecture doc anticipated: GLib/GTK is fine in ui/, banned only from kernel/application/domain (import-linter contract C6 already enforces this).

This is a real increase in supply-chain surface compared to M0's stdlib-only-until-necessary philosophy. Justified because local voice requires ML inference libraries, but named explicitly rather than growing one dependency at a time unnoticed.

---

## 9. Work package roadmap

Numbering continues from M0's WP-18. The first work package is a rough, honest proof-of-concept outside the formal architecture, to de-risk the hardware/library stack before wiring anything into ports and adapters, mirroring how M0 proved jeepney could talk to a real media player before formalizing MPRIS support.

WP-19: Proof of concept, deliberately outside the architecture. A standalone script that captures microphone audio, runs openWakeWord, and on trigger runs faster-whisper, printing the transcript to the terminal. No ports, no adapters, no CLAUDE.md changes. The only goal: prove the microphone, GPU, and libraries actually work together on this real machine. Depends on nothing; pure de-risking.

WP-20: WakeWordPort plus OpenWakeWordAdapter, ring buffer (never persisted, per ADR-0018), formalized into the real architecture for the first time. Depends on WP-19 proving it works.

WP-21: VadPort and SttPort plus adapters, wired to fire after wake word. Depends on WP-20.

WP-22: TtsPort plus PiperTtsAdapter, spoken responses. Independent, can happen in parallel with WP-21.

WP-23: SpeakerIdPort plus adapter, with a structural test proving its output can never reach PolicyContext construction, making the section 3 rule mechanically enforceable, not just a comment. Depends on WP-20.

WP-24: PhysicalConfirmationPort plus GTK4 dialog adapter, the Finding 2 closure. The most safety-critical work package in M1; expect the same depth of review the original policy engine (WP-04) got in M0. Independent.

WP-25: kernel/voice_loop.py, wiring everything together, calling the existing, unchanged AuthorizationOrchestrator. Depends on WP-20 through WP-24. In practice also had to build kernel/intent.py from scratch (see section 4) and extend WakeEvent to carry audio (ADR-0033, see section 4) -- both real gaps this doc did not anticipate, not scope creep.

WP-26: "jarvis listen" CLI subcommand, runs the voice loop as a foreground process. Depends on WP-25.

WP-27: M1 threat-model closeout, new ADRs 0034 through 0037 written for real (ADR-0033 was written during WP-25, when its finding actually happened), tag v0.2.0. Depends on everything above.

---

## 10. Testing strategy

M0's WP-14 AppArmor incident taught a real lesson: mocks cannot catch everything, and Claude Code's sandbox cannot reach real hardware at all. M1 is entirely hardware-dependent: microphone, GPU, audio output. Expect this pattern for essentially every work package:

Unit and contract tests (CI-safe): fake WakeWordPort/SttPort/etc. implementations, proving the wiring logic (intent resolution, authorization calls, the speaker-id-never-reaches-PolicyContext rule) without touching real audio.

Manual verification (real terminal, real microphone, every single time): does the wake word actually trigger? Is the transcript accurate? Does the spoken response actually play? This is not optional per work package; it is the primary way most of M1 gets verified at all, more so than M0.

---

## 11. Open questions

1. Wake phrase: openWakeWord's default, or a custom phrase? **Resolved (WP-20): openWakeWord's default ("hey jarvis").**
2. Whisper model size: medium (faster, lower latency, recommended default) or large-v3 (slower, marginally more accurate)? **Resolved (WP-21): medium, the recommended default.**
3. Does the physical-confirmation dialog replace ManualConfirmationAdapter entirely, or run alongside it for CLI use? Recommendation: alongside, so existing CLI workflows are not broken; the stronger physical-confirmation path is added specifically for voice-triggered actions. **Resolved (WP-24): alongside, per the recommendation -- PhysicalConfirmationPort is a wholly separate port from ConfirmationPort, so this held true by construction, not by a choice made under pressure. ManualConfirmationAdapter is untouched and still used for every non-voice (CLI) invocation.**
4. SpeakerIdPort: build a real speaker-embedding model with an enrollment step in M1, or stub it as an always-"unverified" pass-through and defer the real implementation? Since it is explicitly non-authoritative (section 3), stubbing it in M1 is recommended; it only ever affects audit logging and UX tone, never a security decision. **Resolved (WP-23): stubbed, per the recommendation -- UnverifiedSpeakerIdAdapter always returns verified=False, confidence=0.0. See ADR-0034 for the mechanical enforcement that keeps this non-authoritative for real, not just by convention.**
