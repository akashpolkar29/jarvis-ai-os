"""Wires wake word -> VAD -> STT -> speaker-id (audit only) -> intent -> authorize -> TTS.

:func:`run_voice_loop` is the composition
docs/architecture/m1-voice-architecture.md section 2 describes: it is
genuinely new wiring, but everything below
"AuthorizationOrchestrator.authorize_by_id() [unchanged
from M0]" in that pipeline is exactly M0's existing code, called
unmodified -- ``authorize_ping``, ``authorize_and_run_music_command``,
and ``authorize_and_read_file`` are called directly, exactly as
``jarvis.cli.main`` already calls them, not re-implemented against
``AuthorizationOrchestrator`` a second time. This keeps
``AuthorizationOrchestrator``, the policy engine, the audit chain, and
the two existing M0 capabilities genuinely untouched, per this work
package's own instruction. ``authorize_and_remember`` (M4, WP-63) joins
this dispatch too -- ADR-0053 names this module's own "remember"
branch as real, necessary work for that milestone, distinct from the
"unchanged M0 code" framing above; unlike the M0 functions, it is
new, not a pre-existing function this module merely wires in.
``authorize_and_recall`` (overnight Track 3 pass) joins the same
dispatch: unlike ``authorize_and_remember``, it is a *static*,
fixed-effect capability (``memory.retrieve``, already registered in
``build_default_registry()`` since WP-63) -- closing the real,
previously-named gap that no voice-triggered recall existed, only
"remember `<text>`" (see ``kernel/intent.py``'s own module docstring
for the full "recall" grammar addition).

``authorize_and_run_coding_task`` (overnight Track 4 pass) joins the
same dispatch, but does not fit the pattern above cleanly: it is
``async`` (every other composition function this module calls is
sync), and it requires two pieces of real configuration --
``target_repo`` and ``dispatcher_factory`` -- that have no safe
default anywhere in this codebase (WP-72's own deliberate decision:
which cloud provider(s) service a coding task was never decided by
any ADR, so no default ``DispatcherFactory`` exists to fall back on).
A single free-text voice phrase cannot safely supply either, so
``run_voice_loop`` gains two new *optional* parameters,
``coding_target_repo``/``coding_dispatcher_factory``, that must be
pre-configured out-of-band by whoever constructs the loop (mirroring
how ``database_path``/``embedding_port`` are already pre-configured,
not spoken). If a "code" command resolves while either is ``None``,
this module speaks a real, honest "not configured" message and never
attempts the call -- never a crash, never a silent no-op. Because
``authorize_and_run_coding_task`` is itself ``async``,
``_authorize_and_execute`` is ``async`` too now, awaited at its one
call site in ``_handle_utterance``.

Per utterance: a confirmed :class:`~jarvis.domain.wake_word.WakeEvent`
(carrying its own audio, per ADR-0033) is handed to
:class:`~jarvis.ports.vad.VadPort`, which may find zero, one, or
multiple speech segments in it. Each segment is transcribed, scored by
:class:`~jarvis.ports.speaker_id.SpeakerIdPort` (audit/UX only -- the
score is logged and never used to construct anything resembling a
``PolicyContext``; see ADR-0012 and ``tests/meta/test_speaker_id_isolation.py``,
which structurally verifies this file, like every other, keeps that
guarantee), and resolved via ``jarvis.kernel.intent.resolve_intent``.
An unrecognized intent is spoken back as a plain "I didn't understand
that" and never reaches authorization at all. A resolved intent is
confirmed via :class:`~jarvis.ports.physical_confirmation.PhysicalConfirmationPort`
*every time*, regardless of the capability's actual tier -- this
module deliberately does not pre-inspect a capability's tier to decide
whether to skip the prompt, trading one harmless extra click for a
capability (e.g. "ping", the true no-op) against the complexity and
risk of a second place deciding what does or doesn't need physical
presence. The confirmation's answer becomes
``physical_confirmation_available`` passed straight into whichever
composition function is being called; ``remote_confirmation_available``
is always ``False`` -- no remote-confirmation channel exists anywhere
in this project yet.

Known, real limitation, stated plainly rather than silently worked
around: a ``WakeEvent``'s audio includes the wake phrase itself, not
just the command spoken after it (see ADR-0033). ``resolve_intent()``
matches on the transcript's *first* word, so if VAD/STT hand it a
transcript like "hey jarvis play music" (wake phrase and command
transcribed as one continuous utterance, no silence gap between them),
the leading "hey jarvis" text prevents "play" from ever being seen as
the command word, and the whole utterance resolves as unrecognized.
Whether this actually happens depends on real VAD segmentation
behavior and real STT transcription of the wake phrase -- exactly the
kind of thing that can only be judged from real manual testing (see
docs/architecture/m1-voice-architecture.md section 10), not guessed at
and "fixed" with an unverified heuristic here. Flagged for whoever
does that manual verification, not silently patched around.

Audio playback (speaking TTS's synthesized result out loud) is this
module's own responsibility, not a port: the M1 doc's six ports (see
that doc's section 4) stop at "synthesize text into audio", and unlike
a wake-word engine or an STT model, there is no varying "playback
backend" to abstract over -- playing already-synthesized PCM through
the default output device is a thin, direct ``sounddevice`` call, not
a port-worthy abstraction boundary. See :func:`_play_audio_stream_sync`.

Testability seam, matching every adapter in this project: every port
this module depends on, plus the playback function, is a constructor-
injectable parameter defaulting to the real implementation. Unit tests
inject fakes for all of them and a real, tmp_path-backed chain (the
same convention ``tests/unit/test_ping.py``/``test_music.py``/
``test_files.py`` already use for the composition functions this
module calls), so the wiring itself -- not any adapter's real hardware
-- is what gets exercised automatically. The real ports' own hardware
paths remain individually unit-tested (or, for
``Gtk4PhysicalConfirmationAdapter``'s real dialog, manually verified)
in their own adapter modules; this module does not re-test them.

One deliberate exception to "defaults to the real implementation":
``physical_confirmation`` has no default here and is a required
parameter, unlike every other port. Importing
``Gtk4PhysicalConfirmationAdapter`` directly into this module (the way
every other port's real adapter is imported) transitively reaches
``jarvis.ui.confirm.dialog``'s lazy ``import gi`` -- a real edge
``lint-imports`` sees regardless of that import being function-local,
not module-level, since import-linter's static analysis does not
distinguish lazy from eager imports. ``jarvis.kernel`` is one of C6's
protected source modules ("no GLib in the core"), so this module
cannot import that adapter at all without breaking C6. The real
default is constructed instead by ``jarvis.cli.main``'s "jarvis
listen" subcommand (WP-26) -- ``cli`` sits above both ``kernel`` and
``adapters`` in the C1 layering and is unrestricted by C6, so
constructing the one real, GLib-reaching default there is the correct
place for it, not a workaround.

Diagnostic logging: this module's ``_logger`` emits DEBUG-level lines
(a produced VAD segment's byte length, the STT transcript, the
``resolve_intent`` result) purely as observability -- no behavior
depends on whether anything is actually listening for them. They are
invisible by default; ``jarvis.cli.main``'s ``--verbose`` flag (WP-26
follow-up) is what raises ``jarvis``'s own logger hierarchy to DEBUG.
Replaces the ad hoc ``print()`` debug scaffolding used during live M1
verification, which was reverted rather than left in production code.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from jarvis.adapters.speaker_id import UnverifiedSpeakerIdAdapter
from jarvis.adapters.stt import FasterWhisperAdapter
from jarvis.adapters.tts import PiperTtsAdapter
from jarvis.adapters.vad import SileroVadAdapter
from jarvis.adapters.wake_word import OpenWakeWordAdapter
from jarvis.application.memory.writer import MEMORY_WRITE_CAPABILITY_ID
from jarvis.kernel.capabilities import (
    CODING_RUN_TASK_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
)
from jarvis.kernel.coding import authorize_and_run_coding_task
from jarvis.kernel.files import authorize_and_read_file
from jarvis.kernel.intent import ResolvedIntent, UnrecognizedIntent, resolve_intent
from jarvis.kernel.memory import authorize_and_recall, authorize_and_remember
from jarvis.kernel.music import MUSIC_CAPABILITY_IDS, authorize_and_run_music_command
from jarvis.kernel.ping import authorize_ping

if TYPE_CHECKING:
    from collections.abc import Callable

    from jarvis.application.coding.loop import DispatcherFactory
    from jarvis.domain.audio import AudioStream, Segment
    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.policy import Decision
    from jarvis.kernel.music import MusicCommand
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.file_system import FileSystemPort
    from jarvis.ports.media_player import MediaPlayerPort
    from jarvis.ports.physical_confirmation import PhysicalConfirmationPort
    from jarvis.ports.speaker_id import SpeakerIdPort
    from jarvis.ports.stt import SttPort
    from jarvis.ports.tts import TtsPort
    from jarvis.ports.vad import VadPort
    from jarvis.ports.wake_word import WakeWordPort

    PlayFn = Callable[[AudioStream], None]

_logger = logging.getLogger(__name__)

DEFAULT_CONFIRMATION_TIMEOUT_S = 30.0

_RECALL_SPOKEN_LIMIT = 3
"""How many recalled records a granted "recall" command speaks back.
A real, deliberate bound, not arbitrary: RetrievalPort.retrieve()'s
own ranking already returns records best-match-first, so the top three
are the real, most relevant answer to speak -- more than a handful
read aloud in one breath stops being a usable spoken answer at all."""

_MUSIC_COMMAND_BY_CAPABILITY_ID: dict[CapabilityId, MusicCommand] = {
    capability_id: command for command, capability_id in MUSIC_CAPABILITY_IDS.items()
}
"""Inverts kernel.music.MUSIC_CAPABILITY_IDS rather than re-declaring the
association: resolve_intent() goes MusicCommand -> CapabilityId to build
a ResolvedIntent; this module goes the other way, from an authorized
CapabilityId back to which MusicCommand to actually run. Deriving one
direction from the other keeps the underlying association single-
sourced from kernel.music.MUSIC_CAPABILITY_IDS's own values.
"""


def _play_audio_stream_sync(audio: AudioStream) -> None:
    """The one real, untested-by-design piece of audio output: play synthesized speech.

    See the module docstring for why this is a direct call, not a
    port. Requires a real audio output device; not exercised by the
    automated suite, matching every other real-hardware path in this
    project (see docs/architecture/m1-voice-architecture.md section 10).
    """
    import sounddevice as sd  # noqa: PLC0415 -- deliberately lazy, see module docstring

    samples = np.frombuffer(audio.samples, dtype=np.int16)
    sd.play(samples, samplerate=audio.sample_rate)
    sd.wait()


async def _speak(tts: TtsPort, play_fn: PlayFn, text: str) -> None:
    """Synthesize ``text`` and play it. The one place this module's ports meet playback."""
    audio = await tts.speak(text)
    play_fn(audio)


def _confirmation_prompt(resolved: ResolvedIntent) -> str:
    """Build a human-readable prompt describing the resolved action to approve or deny."""
    if resolved.capability_id == READ_FILE_CAPABILITY_ID:
        path_text = resolved.arguments.value.get("path")
        return f"JARVIS wants to: read {path_text}. Approve?"
    if resolved.capability_id == MEMORY_WRITE_CAPABILITY_ID:
        text = resolved.arguments.value.get("text")
        return f"JARVIS wants to: remember '{text}'. Approve?"
    if resolved.capability_id == MEMORY_RETRIEVE_CAPABILITY_ID:
        query_text = resolved.arguments.value.get("query")
        return f"JARVIS wants to: recall memories about '{query_text}'. Approve?"
    if resolved.capability_id == CODING_RUN_TASK_CAPABILITY_ID:
        task_text = resolved.arguments.value.get("task")
        return f"JARVIS wants to: run a coding task -- '{task_text}'. Approve?"
    return f"JARVIS wants to: {resolved.capability_id}. Approve?"


def _describe(decision: Decision) -> str:
    """A short spoken description of a Decision's outcome."""
    return "Done." if decision.granted else "Sorry, that wasn't approved."


async def _authorize_and_execute(  # noqa: PLR0913, PLR0911 -- one param per composition function, one return per dispatch branch
    resolved: ResolvedIntent,
    *,
    approved: bool,
    chain_path: Path,
    allowed_root: Path | None,
    file_system: FileSystemPort | None,
    media_player: MediaPlayerPort | None,
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    coding_target_repo: Path | None,
    coding_dispatcher_factory: DispatcherFactory | None,
) -> str:
    """Dispatch the resolved capability to its (unchanged, M0) composition function.

    ``allowed_root``/``file_system``/``media_player``/``database_path``/
    ``embedding_port`` are pass-throughs to
    ``authorize_and_read_file``'s, ``authorize_and_run_music_command``'s,
    and ``authorize_and_remember``'s own existing, optional
    parameters -- each unused by the other commands -- included here
    only so tests can override the real file reader/media player/
    memory store exactly as ``test_files.py``/``test_music.py`` already
    do, without this module inventing a second way to do so. Omitting
    ``media_player`` here specifically would mean any test resolving a
    *granted* music command reaches a real, currently-running MPRIS
    player over the session D-Bus -- a real mistake caught during this
    work package's own test-writing, not a hypothetical one. The same
    reasoning applies to ``embedding_port``: a granted memory write
    with no override reaches a real ``FastEmbedAdapter``, triggering a
    real model download on first use (WP-61/62).

    ``coding_target_repo``/``coding_dispatcher_factory`` are
    pass-throughs to ``authorize_and_run_coding_task``'s own existing,
    required parameters, for a resolved "code" command -- see the
    module docstring for why they have no safe default and why a
    missing one speaks an honest "not configured" message instead of
    calling through.

    Returns the text to speak back: a file's content on a granted
    read, otherwise a short granted/denied description.
    """
    if resolved.capability_id == PING_CAPABILITY_ID:
        decision = authorize_ping(
            physical_confirmation_available=approved,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )
        return _describe(decision)

    if resolved.capability_id == READ_FILE_CAPABILITY_ID:
        path_text = str(resolved.arguments.value["path"])
        outcome = authorize_and_read_file(
            Path(path_text),
            physical_confirmation_available=approved,
            remote_confirmation_available=False,
            chain_path=chain_path,
            allowed_root=allowed_root,
            file_system=file_system,
        )
        if outcome.content is not None:
            return outcome.content.value
        return _describe(outcome.decision)

    if resolved.capability_id == MEMORY_WRITE_CAPABILITY_ID:
        text = str(resolved.arguments.value["text"])
        write_outcome = authorize_and_remember(
            text,
            physical_confirmation_available=approved,
            remote_confirmation_available=False,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
        )
        return _describe(write_outcome.decision)

    if resolved.capability_id == MEMORY_RETRIEVE_CAPABILITY_ID:
        query_text = str(resolved.arguments.value["query"])
        recall_outcome = authorize_and_recall(
            query_text,
            limit=_RECALL_SPOKEN_LIMIT,
            physical_confirmation_available=approved,
            remote_confirmation_available=False,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
        )
        if not recall_outcome.decision.granted:
            return _describe(recall_outcome.decision)
        if not recall_outcome.records:
            return "I don't remember anything about that."
        contents = "; ".join(str(record.value.value) for record in recall_outcome.records)
        return f"I recall: {contents}"

    if resolved.capability_id == CODING_RUN_TASK_CAPABILITY_ID:
        if coding_target_repo is None or coding_dispatcher_factory is None:
            return "Coding isn't configured on this device."
        task_text = str(resolved.arguments.value["task"])
        coding_decision, _result = await authorize_and_run_coding_task(
            task_text,
            coding_target_repo,
            coding_dispatcher_factory,
            physical_confirmation_available=approved,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )
        return _describe(coding_decision)

    music_command = _MUSIC_COMMAND_BY_CAPABILITY_ID[resolved.capability_id]
    decision = authorize_and_run_music_command(
        music_command,
        physical_confirmation_available=approved,
        remote_confirmation_available=False,
        chain_path=chain_path,
        media_player=media_player,
    )
    return _describe(decision)


async def _handle_utterance(  # noqa: PLR0913 -- one per injectable port plus chain/timeout config
    segment: Segment,
    *,
    stt: SttPort,
    speaker_id: SpeakerIdPort,
    tts: TtsPort,
    play_fn: PlayFn,
    physical_confirmation: PhysicalConfirmationPort,
    chain_path: Path,
    confirmation_timeout_s: float,
    allowed_root: Path | None,
    file_system: FileSystemPort | None,
    media_player: MediaPlayerPort | None,
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    coding_target_repo: Path | None,
    coding_dispatcher_factory: DispatcherFactory | None,
) -> None:
    """Transcribe, resolve, confirm, and authorize+execute one VAD-confirmed speech segment."""
    transcript = await stt.transcribe(segment)
    _logger.debug("transcript: %r", transcript.value.text)

    score = speaker_id.score(segment)  # audit/UX only -- never an authorization input (ADR-0012)
    _logger.info(
        "speaker_id: verified=%s confidence=%.2f (audit/UX only, not an authorization input)",
        score.verified,
        score.confidence,
    )

    resolved = resolve_intent(transcript.value)
    _logger.debug("resolve_intent result: %r", resolved)
    if isinstance(resolved, UnrecognizedIntent):
        await _speak(tts, play_fn, "I didn't understand that.")
        return

    prompt = _confirmation_prompt(resolved)
    approved = await physical_confirmation.await_physical_confirmation(
        prompt, confirmation_timeout_s
    )

    response_text = await _authorize_and_execute(
        resolved,
        approved=approved,
        chain_path=chain_path,
        allowed_root=allowed_root,
        file_system=file_system,
        media_player=media_player,
        database_path=database_path,
        embedding_port=embedding_port,
        coding_target_repo=coding_target_repo,
        coding_dispatcher_factory=coding_dispatcher_factory,
    )
    await _speak(tts, play_fn, response_text)


async def run_voice_loop(  # noqa: PLR0913 -- one per injectable port plus chain/timeout config
    *,
    chain_path: Path,
    physical_confirmation: PhysicalConfirmationPort,
    wake_word: WakeWordPort | None = None,
    vad: VadPort | None = None,
    stt: SttPort | None = None,
    speaker_id: SpeakerIdPort | None = None,
    tts: TtsPort | None = None,
    play_fn: PlayFn | None = None,
    confirmation_timeout_s: float = DEFAULT_CONFIRMATION_TIMEOUT_S,
    allowed_root: Path | None = None,
    file_system: FileSystemPort | None = None,
    media_player: MediaPlayerPort | None = None,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    coding_target_repo: Path | None = None,
    coding_dispatcher_factory: DispatcherFactory | None = None,
) -> None:
    """Run the voice pipeline until ``wake_word``'s stream ends (never, for the real adapter).

    Args:
        chain_path: Where the audit chain is persisted -- passed
            straight through to whichever composition function ends
            up authorizing each resolved command.
        physical_confirmation: No default -- see the module docstring
            for why (C6's "no GLib in the core" contract). The real
            caller (``jarvis.cli.main``'s "jarvis listen" subcommand,
            WP-26) constructs a real ``Gtk4PhysicalConfirmationAdapter``
            and passes it in; tests pass a fake.
        wake_word: Defaults to a real ``OpenWakeWordAdapter``.
        vad: Defaults to a real ``SileroVadAdapter``.
        stt: Defaults to a real ``FasterWhisperAdapter``.
        speaker_id: Defaults to a real ``UnverifiedSpeakerIdAdapter``.
        tts: Defaults to a real ``PiperTtsAdapter``.
        play_fn: Defaults to a real ``sounddevice``-backed playback
            call. Overridable for tests, exactly as every other
            real-hardware seam in this project is.
        confirmation_timeout_s: How long to wait for a physical
            response before treating a resolved command as denied.
        allowed_root: Pass-through to ``authorize_and_read_file``'s own
            existing parameter of the same name, for a resolved "read"
            command. Defaults to that function's own default
            (``Path.home()``). Overridable for tests.
        file_system: Pass-through to ``authorize_and_read_file``'s own
            existing parameter of the same name. Defaults to that
            function's own default (a real ``LocalFileSystemAdapter``).
            Overridable for tests.
        media_player: Pass-through to
            ``authorize_and_run_music_command``'s own existing
            parameter of the same name, for a resolved music command.
            Defaults to that function's own default (a real
            ``MprisMediaPlayerAdapter`` talking to the session D-Bus).
            Overridable for tests -- important to override, in fact:
            a granted music command with no override reaches a real,
            currently-running media player.
        database_path: Pass-through to ``authorize_and_remember``'s own
            existing parameter of the same name, for a resolved
            "remember" command. Defaults to that function's own
            default. Overridable for tests.
        embedding_port: Pass-through to ``authorize_and_remember``'s
            own existing parameter of the same name. Defaults to that
            function's own default (a real ``FastEmbedAdapter``).
            Overridable for tests -- important to override, in fact: a
            granted memory write with no override triggers a real
            model download on first use.
        coding_target_repo: Pass-through to
            ``authorize_and_run_coding_task``'s own existing required
            ``target_repo`` parameter, for a resolved "code" command.
            No default -- see the module docstring for why. If ``None``
            when a "code" command resolves, this module speaks an
            honest "not configured" message instead of calling through.
        coding_dispatcher_factory: Pass-through to
            ``authorize_and_run_coding_task``'s own existing required
            ``dispatcher_factory`` parameter. No default, for the same
            reason as ``coding_target_repo``.
    """
    wake_word = wake_word or OpenWakeWordAdapter()
    vad = vad or SileroVadAdapter()
    stt = stt or FasterWhisperAdapter()
    speaker_id = speaker_id or UnverifiedSpeakerIdAdapter()
    tts = tts or PiperTtsAdapter()
    play_fn = play_fn or _play_audio_stream_sync

    async for wake_event in wake_word.stream():
        async for segment in vad.segment(wake_event.audio):
            _logger.debug("VAD segment produced: %d bytes", len(segment.samples))
            await _handle_utterance(
                segment,
                stt=stt,
                speaker_id=speaker_id,
                tts=tts,
                play_fn=play_fn,
                physical_confirmation=physical_confirmation,
                chain_path=chain_path,
                confirmation_timeout_s=confirmation_timeout_s,
                allowed_root=allowed_root,
                file_system=file_system,
                media_player=media_player,
                database_path=database_path,
                embedding_port=embedding_port,
                coding_target_repo=coding_target_repo,
                coding_dispatcher_factory=coding_dispatcher_factory,
            )
