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
from jarvis.adapters.validation.pytest_validator import PytestValidator
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audio import AudioChunk, AudioStream, Segment
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry
from jarvis.domain.speaker_id import SpeakerScore
from jarvis.domain.transcript import Transcript
from jarvis.domain.wake_word import WakeEvent
from jarvis.kernel.voice_loop import run_voice_loop

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from jarvis.application.coding.loop import DispatcherFactory
    from jarvis.domain.calendar import CalendarEvent, CalendarEventDraft
    from jarvis.domain.email import EmailMessage, EmailSummary
    from jarvis.domain.evidence import Attempt
    from jarvis.ports.workspace import WorkspacePort

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


class _SequentialSttPort:
    """Transcribes a fixed list of texts, one per real call, in order -- for a multi-utterance test."""  # noqa: E501

    def __init__(self, texts: list[str]) -> None:
        self._texts = iter(texts)

    async def transcribe(self, audio: Segment) -> Tainted[Transcript]:
        del audio
        return Tainted(Transcript(text=next(self._texts)), Provenance.user())


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


class _FakeEmailPort:
    """Records every real send_message call it receives -- no real IMAP/SMTP is touched.

    read_message/list_messages are never called by anything
    "send email" voice grammar exercises, so they raise if reached --
    the same "unused Protocol method never silently succeeds" caution
    tests/unit/test_communications_kernel.py's own fakes take.
    """

    def __init__(self) -> None:
        self.send_calls: list[tuple[tuple[str, ...], str, str]] = []

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        raise NotImplementedError

    async def read_message(self, message_id: str) -> EmailMessage:
        raise NotImplementedError

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        self.send_calls.append((to, subject, body))


class _FakeCalendarPort:
    """Records every real create_event call it receives -- no real CalDAV is touched."""

    def __init__(self, created_uid: str = "new-uid") -> None:
        self.create_calls: list[CalendarEventDraft] = []
        self._created_uid = created_uid

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        raise NotImplementedError

    async def create_event(self, draft: CalendarEventDraft) -> str:
        self.create_calls.append(draft)
        return self._created_uid


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


async def test_a_read_command_outside_the_allowed_root_speaks_an_honest_error_not_a_crash(
    tmp_path: Path,
) -> None:
    """A real resilience regression (property-matrix/fuzzing/concurrency pass, Track 2, 2026-09-04).

    Before this fix, _handle_utterance had no exception handling
    around _authorize_and_execute at all -- unlike jarvis.cli.main's
    identical dispatch, which already catches this exact error.
    PathOutsideAllowedScopeError from authorize_and_read_file's own
    scope check would previously propagate uncaught out of
    run_voice_loop entirely, ending the whole voice loop after a
    single out-of-scope "read" command rather than just failing that
    one utterance. Proves the loop now completes and speaks a clean,
    honest error instead.
    """
    outside_target = tmp_path.parent / "definitely-outside.txt"
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort(f"read {outside_target}"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        allowed_root=tmp_path,
    )

    assert len(tts.spoken) == 1
    assert tts.spoken[0].startswith("Sorry, that failed:")


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


async def test_a_remember_command_against_a_real_corrupted_database_speaks_an_honest_error(
    tmp_path: Path,
) -> None:
    """A real, deliberately-corrupted memory.sqlite3 fails closed, not a crash.

    Real resilience finding (10-phase combined pass, Phase 2,
    2026-09-05): `sqlite3.DatabaseError`/`sqlite3.Error` is a bare
    `Exception` subclass, not `OSError` -- the exact same class of gap
    `imaplib.IMAP4.abort` was found to be in the prior
    adapter-resilience pass. Mirrors
    `test_a_read_command_outside_the_allowed_root_speaks_an_honest_error_not_a_crash`'s
    own real-corruption-not-a-mock discipline: a genuinely corrupted
    real file, not a monkeypatched exception.
    """
    tts = _FakeTtsPort()
    database_path = tmp_path / "memory.sqlite3"
    database_path.write_text("not a real sqlite file, just garbage bytes")

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("remember I prefer tabs"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )

    assert len(tts.spoken) == 1
    assert tts.spoken[0].startswith("Sorry, that failed:")


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


async def test_a_recognized_recall_command_speaks_back_a_previously_remembered_value(
    tmp_path: Path,
) -> None:
    """ "remember <text>" then "recall <query>" speaks the remembered content back."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    database_path = tmp_path / "memory.sqlite3"

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT, _A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_SequentialSttPort(["remember I prefer tabs", "recall my editor preferences"]),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )

    assert tts.spoken[0] == "Done."
    assert "I prefer tabs" in tts.spoken[1]


async def test_a_recall_command_with_nothing_stored_reports_nothing_remembered(
    tmp_path: Path,
) -> None:
    """A granted recall against an empty store speaks a real, honest "nothing" answer."""
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("recall my editor preferences"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
    )

    assert tts.spoken == ["I don't remember anything about that."]


async def test_a_recall_command_is_granted_even_when_confirmation_is_denied(
    tmp_path: Path,
) -> None:
    """memory.retrieve is Tier.ALLOW -- a denied spoken confirmation still doesn't block recall."""
    tts = _FakeTtsPort()
    database_path = tmp_path / "memory.sqlite3"

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT, _A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_SequentialSttPort(["remember I prefer tabs", "recall my editor preferences"]),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    remembered_via_confirmed_run = "I prefer tabs" in tts.spoken[1]

    tts_denied = _FakeTtsPort()
    await run_voice_loop(
        chain_path=tmp_path / "audit_chain_2.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("recall my editor preferences"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts_denied,
        play_fn=_no_playback,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )

    assert remembered_via_confirmed_run is True
    # A denied physical confirmation still finds and speaks the same real, already-stored
    # record -- ALLOW tier means the recall itself was never gated by the answer at all.
    assert "I prefer tabs" in tts_denied.spoken[0]


async def test_the_confirmation_prompt_names_the_recall_query(tmp_path: Path) -> None:
    """The prompt for a resolved "recall" command names the actual query, not a generic label."""
    confirmation = _FakePhysicalConfirmationPort(approve=True)

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("recall my editor preferences"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=_FakeTtsPort(),
        play_fn=_no_playback,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
    )

    assert len(confirmation.prompts) == 1
    prompt_text, _timeout = confirmation.prompts[0]
    assert "my editor preferences" in prompt_text


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


_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_NOT_A_REAL_PATCH = "this is not a real unified diff at all"


class _CountingProvider:
    """A minimal, test-local ReasoningPort that records every real call it receives.

    Mirrors tests/unit/test_coding_kernel.py's own fake exactly -- see
    that module's docstring for why only the reasoning provider, the
    true external-I/O edge, is faked here.
    """

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        self.call_count += 1
        candidate = Candidate(author="local", content=_NOT_A_REAL_PATCH)
        return Tainted(candidate, Provenance.system())


def _fake_dispatcher_factory_for(
    provider: _CountingProvider, orchestrator: AuthorizationOrchestrator
) -> DispatcherFactory:
    def _build(workspace: WorkspacePort) -> Dispatcher:
        router = ModelRouter(orchestrator)
        validator = PytestValidator(workspace)
        providers = {EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, provider),)}
        return Dispatcher(EscalationLadder(), Arbiter(), router, validator, providers)

    return _build


def _target_repo_with_pytest_convention(tmp_path: Path) -> Path:
    """A real target repo whose test convention auto-detects, so resolve_protected_patterns
    succeeds without run_voice_loop needing its own coding_protected_patterns override."""
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    (target_repo / "pytest.ini").write_text("[pytest]\n")
    return target_repo


async def test_a_recognized_code_command_is_granted_and_invokes_the_coding_agent(
    tmp_path: Path,
) -> None:
    """ "code <task>" -> confirmed -> granted -> the real coding agent actually runs."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    chain_path = tmp_path / "audit_chain.json"
    provider = _CountingProvider()
    target_repo = _target_repo_with_pytest_convention(tmp_path)

    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    await run_voice_loop(
        chain_path=chain_path,
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("code fix the failing test"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        coding_target_repo=target_repo,
        coding_dispatcher_factory=_fake_dispatcher_factory_for(provider, orchestrator),
    )

    assert tts.spoken == ["Done."]
    # No coding_max_climbs pass-through exists (deliberately, minimal scope) --
    # authorize_and_run_coding_task retries across DEFAULT_MAX_CLIMBS=3 climbs
    # since the fake provider's patch never validates, so this proves the
    # coding agent was actually invoked, not that it was invoked exactly once.
    assert provider.call_count >= 1


async def test_a_denied_code_command_never_invokes_the_coding_agent(tmp_path: Path) -> None:
    """A "code" request whose physical confirmation is denied never runs the coding agent
    -- mirroring test_coding_kernel.py's own provider.call_count == 0 proof, through voice."""
    tts = _FakeTtsPort()
    provider = _CountingProvider()
    target_repo = _target_repo_with_pytest_convention(tmp_path)

    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("code fix the failing test"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        coding_target_repo=target_repo,
        coding_dispatcher_factory=_fake_dispatcher_factory_for(provider, orchestrator),
    )

    assert tts.spoken == ["Sorry, that wasn't approved."]
    assert provider.call_count == 0


async def test_a_code_command_with_no_coding_configuration_speaks_an_honest_fallback(
    tmp_path: Path,
) -> None:
    """With coding_target_repo/coding_dispatcher_factory both omitted, a "code" command
    never crashes and never silently no-ops -- it speaks a real, honest message."""
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("code fix the failing test"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["Coding isn't configured on this device."]


async def test_the_confirmation_prompt_names_the_coding_task(tmp_path: Path) -> None:
    """The prompt shown for physical confirmation names the actual task text."""
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    provider = _CountingProvider()
    target_repo = _target_repo_with_pytest_convention(tmp_path)

    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("code fix the failing test"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=_FakeTtsPort(),
        play_fn=_no_playback,
        coding_target_repo=target_repo,
        coding_dispatcher_factory=_fake_dispatcher_factory_for(provider, orchestrator),
    )

    assert len(confirmation.prompts) == 1
    prompt_text, _timeout = confirmation.prompts[0]
    assert "fix the failing test" in prompt_text


async def test_a_recognized_send_email_command_is_granted_and_sends_a_real_email(
    tmp_path: Path,
) -> None:
    """ "send email ..." -> confirmed -> granted -> the real EmailPort actually sends."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    email_port = _FakeEmailPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("send email to alice@example.com subject Hello body See you soon"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        email_port=email_port,
    )

    assert tts.spoken == ["Done."]
    assert email_port.send_calls == [(("alice@example.com",), "Hello", "See you soon")]


async def test_a_denied_send_email_command_never_sends_a_real_email(tmp_path: Path) -> None:
    """A "send email" request denied at physical confirmation is never actually sent --
    proving voice does not bypass ADR-0059's Tier.MANUAL_ONLY floor in any way."""
    tts = _FakeTtsPort()
    email_port = _FakeEmailPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("send email to alice@example.com subject Hello body See you soon"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        email_port=email_port,
    )

    assert tts.spoken == ["Sorry, that wasn't approved."]
    assert email_port.send_calls == []


async def test_a_send_email_command_with_no_email_configuration_speaks_an_honest_fallback(
    tmp_path: Path,
) -> None:
    """With email_port omitted, "send email" never crashes and never silently no-ops."""
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("send email to alice@example.com subject Hello body See you soon"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["Email isn't configured on this device."]


async def test_a_recognized_create_event_command_is_granted_and_creates_a_real_event(
    tmp_path: Path,
) -> None:
    """ "create event ..." with attendees -> confirmed -> granted -> the real CalendarPort
    actually creates the event, at the same Tier.MANUAL_ONLY floor an attendee-bearing
    event requires (ADR-0059) -- physical confirmation alone makes this succeed."""
    tts = _FakeTtsPort()
    confirmation = _FakePhysicalConfirmationPort(approve=True)
    calendar_port = _FakeCalendarPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort(
            "create event Team sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00 "
            "with alice@example.com"
        ),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        calendar_port=calendar_port,
    )

    assert tts.spoken == ["Done."]
    assert len(calendar_port.create_calls) == 1
    draft = calendar_port.create_calls[0]
    assert draft.summary == "Team sync"
    assert draft.attendees == ("alice@example.com",)


async def test_a_denied_attendee_bearing_create_event_command_never_creates_a_real_event(
    tmp_path: Path,
) -> None:
    """An attendee-bearing "create event" request denied at physical confirmation is never
    actually created -- the single most important proof: voice cannot satisfy
    Tier.MANUAL_ONLY through remote confirmation alone (remote_confirmation_available is
    always False from this module, but this proves denial holds regardless)."""
    tts = _FakeTtsPort()
    calendar_port = _FakeCalendarPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=False),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort(
            "create event Team sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00 "
            "with alice@example.com"
        ),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
        calendar_port=calendar_port,
    )

    assert tts.spoken == ["Sorry, that wasn't approved."]
    assert calendar_port.create_calls == []


async def test_a_create_event_command_with_no_calendar_configuration_speaks_an_honest_fallback(
    tmp_path: Path,
) -> None:
    """With calendar_port omitted, "create event" never crashes and never silently no-ops."""
    tts = _FakeTtsPort()

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=_FakePhysicalConfirmationPort(approve=True),
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("create event Team sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=tts,
        play_fn=_no_playback,
    )

    assert tts.spoken == ["Calendar isn't configured on this device."]


async def test_the_confirmation_prompt_names_the_email_recipients_and_subject(
    tmp_path: Path,
) -> None:
    """The prompt shown for physical confirmation names the real recipients and subject."""
    confirmation = _FakePhysicalConfirmationPort(approve=True)

    await run_voice_loop(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation=confirmation,
        wake_word=_FakeWakeWordPort([_A_WAKE_EVENT]),
        vad=_FakeVadPort([_SOME_SEGMENT]),
        stt=_FakeSttPort("send email to alice@example.com subject Hello body See you soon"),
        speaker_id=_FakeSpeakerIdPort(),
        tts=_FakeTtsPort(),
        play_fn=_no_playback,
        email_port=_FakeEmailPort(),
    )

    assert len(confirmation.prompts) == 1
    prompt_text, _timeout = confirmation.prompts[0]
    assert "alice@example.com" in prompt_text
    assert "Hello" in prompt_text
