# Physical verification checklist

Real, current commands and prerequisites for the three real, open
verification items this project has repeatedly named as needing a
physically-present human -- not something an unattended pass may ever
trigger (see `CLAUDE.md`'s own standing rule: no real synthetic
keystroke, no real portal dialog, no wake-word test, ever, outside a
supervised session). **This document is itself documentation only.**
Writing it does not run, simulate, or trigger any of the three real
actions it describes.

Written 2026-09-06. Commands reflect the real, current CLI/kernel
surface as of `v0.6.0` plus the `jarvis plan run`/`jarvis email
list`/`jarvis email read` CLI-wiring pass. Re-check against
`docs/protocol/README.md`'s own subcommand table if this drifts.

## Before starting any of the three: run `jarvis doctor`

```sh
uv run jarvis doctor
```

Confirms real environment readiness (Python version, `git`/`docker`/
`bwrap` binaries, GTK4, `libportaudio`, `nvidia-smi`, local Ollama
reachability, audit-chain directory writability) before attempting
anything below. `doctor` is read-only and side-effect-free -- see
`docs/architecture/jarvis-doctor.md`.

## 1. Live voice loop test (`jarvis listen`)

**What's unverified**: tracker #19. Every individual pipeline stage
(mic capture, wake-word scoring, VAD, STT, TTS) has been confirmed
working in isolation against real hardware (see
`docs/threat-model/v0.md`'s "M1's voice pipeline" section, 2026-08-25).
What has never been exercised is (a) real wake-word *detection
accuracy* -- does saying "hey jarvis" out loud actually trigger a
detection at a usable rate -- and (b) the full `run_voice_loop`
integration end to end. Neither is safely testable unattended; both
need a human physically present, speaking.

**Command**:

```sh
uv run jarvis listen --chain-path /tmp/audit_chain.json --verbose
```

`--verbose` enables DEBUG-level logging for JARVIS's own loggers
(wake-word scores, VAD/STT/intent-resolution output) -- useful for
diagnosing exactly where a failed detection breaks down, per
tracker #19's own open question (accuracy vs. integration-layer bug).

**Real prerequisites**: a working microphone (`jarvis doctor`'s
`libportaudio` check covers the library, not the physical device
itself -- no check confirms a mic is actually plugged in and granted
permission); a real CUDA GPU for STT (`nvidia-smi` check); real Piper
TTS output through a working speaker/headphones.

**What to actually verify while running it**: say "hey jarvis" at a
normal speaking volume and distance; confirm a wake-word detection
fires (visible in `--verbose` output as a wake-word score crossing
threshold); speak a real command (e.g. "ping"); confirm STT produces
an accurate transcript; confirm the correct capability is dispatched;
confirm a spoken TTS response plays back. Repeat at varying distances/
volumes if the first attempt fails, to help separate "wake-word model
genuinely doesn't detect this phrase reliably" from "a one-off audio
glitch."

## 2. Terminal synthetic-typing portal dialog (`terminal.run`)

**What's unverified**: ADR-0047's `SyntheticInputPort`/
`PortalSyntheticInputAdapter` -- the real
`org.freedesktop.portal.RemoteDesktop` `CreateSession`/`SelectDevices`/
`Start` D-Bus call sequence -- has never fired against the real portal.
The first real call pops a real, interactive OS permission dialog that
needs a human physically present to approve (or deny) it; every prior
pass has deliberately stopped short of this, per ADR-0047's own
design and this project's own standing "no real portal call
unattended" rule. See `adapters/synthetic_input.py`'s own module
docstring for the full, existing reasoning.

**No CLI/voice entry point exists for this today** --
`authorize_and_run_terminal_command` (`kernel/desktop.py`) is real,
tested, and callable, but was deliberately never wired into `jarvis`'s
CLI (see `docs/ROADMAP.md`'s M3 row: "`terminal.run` ... needs
`SyntheticInputPort`, explicitly out of scope"). Verifying this today
means invoking the kernel composition function directly, not through
a subcommand:

```python
import asyncio
from pathlib import Path

from jarvis.adapters.desktop_window import AtspiDesktopWindowAdapter
from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.adapters.secret import SecretServiceAdapter
from jarvis.adapters.synthetic_input import PortalSyntheticInputAdapter
from jarvis.adapters.terminal_profile import ensure_synthetic_input_profile_exists
from jarvis.adapters.tts import PiperTtsAdapter
from jarvis.kernel.desktop import authorize_and_run_terminal_command
from jarvis.kernel.voice_loop import _play_audio_stream_sync  # noqa: PLC0415 -- verification-script-only

outcome = asyncio.run(
    authorize_and_run_terminal_command(
        "echo hello from a real sandboxed terminal",
        physical_confirmation_available=True,  # only this channel can grant terminal.run
        remote_confirmation_available=False,
        chain_path=Path("/tmp/audit_chain.json"),
        sandbox=BwrapSandboxAdapter(),
        desktop_window=AtspiDesktopWindowAdapter(),
        synthetic_input=PortalSyntheticInputAdapter(),
        secret=SecretServiceAdapter(),
        tts=PiperTtsAdapter(),
        play_fn=_play_audio_stream_sync,
        ensure_profile=ensure_synthetic_input_profile_exists,
    )
)
print(outcome)
```

**Real prerequisites**: a real Wayland (or X11) session with a real
`xdg-desktop-portal` implementation running and supporting
`RemoteDesktop` version 2 (confirmed present on this project's own
development machine via `gdbus introspect` during ADR-0047's design
pass -- re-check on whatever machine actually runs this); a real
`gnome-keyring` (or equivalent Secret Service) for the `restore_token`
round-trip; real Piper TTS/audio output for the real-time spoken
announcement, which ADR-0047 requires to fire *before* any keystroke.

**What to actually verify while running it**: a real OS permission
dialog appears asking to share the screen/input with JARVIS -- approve
it; a real terminal window opens with the ADR-0047 real-time-indicator
profile (amber/red border, per its own GSettings profile); a real
spoken TTS announcement plays before typing starts; the command is
genuinely typed character-by-character into the real terminal (not
pasted); the terminal's real output is captured afterward. Also worth
confirming: denying the portal dialog fails closed cleanly (no
keystrokes, a clean error), and a second run reuses the persisted
`restore_token` rather than re-prompting (ADR-0047's own documented
one-retry-on-failed-replay behavior).

## 3. ChatGPT desktop app test

**Real, structural blocker, not merely "not yet run"**: re-checked
exhaustively during the M3 live-verification pass (PATH, all
`.desktop` locations, `snap list`, `flatpak list`, `dpkg`) -- no
ChatGPT desktop app exists on this project's own development machine,
under any name. More importantly: **OpenAI does not publish an
official Linux ChatGPT desktop client at all.** Every result under a
name like `chatgpt-desktop`/`chatgpt-linux` in the snap store is an
unofficial third-party wrapper by an individual developer, unlike
`claude-desktop` (Anthropic's own official Linux package, which *is*
installed and *does* launch for real -- see item below).

**Decision already made, recorded in `docs/threat-model/v0.md`'s
"Live desktop-control verification" section**: not to install an
unofficial third-party wrapper to satisfy this test. Doing so would
not actually verify "the ChatGPT desktop app" the way ADR-0045 means
it -- only the general AT-SPI2/Electron mechanism already covered by
the Claude desktop app test below -- while running unaudited
third-party code, a real cost with no matching real benefit. This item
remains deliberately deferred, not because no one has gotten around to
it, but because there is currently no real, official target to test
against on Linux at all.

**If this ever needs to be revisited**: check first whether OpenAI has
since published an official Linux client (search their own official
download page/docs, not the snap store) before treating this as
actionable again.

**Related, already-partially-done item, for context**: the Claude
desktop app (`desktop.claude_app_send_text`) *does* launch for real
(confirmed via its real process tree) but never exposes an AT-SPI2
accessible tree in its default configuration (Chromium/Electron's own
behavior of not activating the accessibility bridge without a detected
assistive-technology client) -- so `desktop.claude_app_send_text`
remains unverified against the real app too, for a different, already
fully-diagnosed reason (see `docs/threat-model/v0.md`'s "Claude
desktop app" section). Not a new gap this document introduces; noted
here only because it is easy to conflate with the ChatGPT item above.
No real command to run for this one that would produce a different
result than what's already been found -- re-verification would need
either the GNOME accessibility bridge enabled system-wide or a
per-process `--force-renderer-accessibility` flag scoped into
JARVIS's own launch path, both already identified and already
deliberately not applied (see the same threat-model section for why).
