"""Unit tests for jarvis.cli.main.main, called directly with explicit argv (no subprocess).

The `ping` subcommand's tests call the real jarvis.kernel.ping code
path -- fully hermetic (tmp_path chain file only, no external system
dependency), so no mocking is needed. The `play`/`pause`/`next`/
`previous` subcommands' tests monkeypatch
jarvis.cli.main.authorize_and_run_music_command itself rather than
letting it run for real, because its real default path constructs an
MprisMediaPlayerAdapter that needs a live D-Bus session bus -- exactly
what must not be required in CI. This tests the CLI's own
responsibility (does it route the right subcommand to the right
kernel call, with the right arguments, and format the result) without
re-testing jarvis.kernel.music's own logic, which
tests/unit/test_music.py already covers directly.

Patching note: ``jarvis.cli.__init__`` does ``from .main import main``,
which reassigns the *attribute* ``jarvis.cli.main`` (on the package
object) to the ``main`` function -- shadowing the submodule. Both
``import jarvis.cli.main as x`` and ``monkeypatch.setattr("jarvis.cli.main.X", ...)``
resolve via that same shadowed attribute once the package is already
imported, and would silently patch the wrong object. Fetching the
real submodule via ``sys.modules["jarvis.cli.main"]`` (keyed by full
dotted name, unaffected by the shadowing) and patching that object
directly is the reliable fix.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.calendar import CalDavCalendarAdapter, CalendarEventCreationError
from jarvis.adapters.email import ImapEmailAdapter
from jarvis.adapters.memory import UnsupportedMemoryValueError
from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter
from jarvis.application.coding.loop import CodingLoopOutcome, CodingLoopResult
from jarvis.cli.main import main
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.file_system import DirEntry
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.communications import CalendarEventCreateOutcome
from jarvis.kernel.desktop import ChatApp, DockerListContainersOutcome, GitStatusOutcome
from jarvis.kernel.files import DirListOutcome, FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.job_assistance import DraftOutcome
from jarvis.kernel.memory import MemoryRecallOutcome, MemoryWriteOutcome
from jarvis.kernel.music import MusicCommand
from jarvis.ports.brave import BrowserLaunchFailedError
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError
from jarvis.ports.docker import DockerCommandFailedError
from jarvis.ports.git import GitCommandFailedError
from jarvis.ports.media_player import NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from jarvis.ports.physical_confirmation import PhysicalConfirmationPort


def _make_decision(*, granted: bool, capability_id: str = "music.pause") -> Decision:
    """Build a minimal Decision for a stubbed kernel call to return."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId(capability_id),
        effects=Effect.WRITE_LOCAL,
        description="A test capability.",
    )
    invocation = CapabilityInvocation(descriptor, Tainted({}, Provenance.user()))
    return Decision(
        tier=Tier.CONFIRM,
        granted=granted,
        reasons=DecisionReason.BASE_TIER,
        invocation=invocation,
    )


def test_ping_default_flags_grants_and_exits_zero(tmp_path: Path) -> None:
    """With no flags, ping is granted and main() returns 0."""
    chain_path = tmp_path / "audit_chain.json"

    exit_code = main(["ping", "--chain-path", str(chain_path)])

    assert exit_code == 0


def test_ping_prints_the_decision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main() prints granted status, tier, and reasons for a human to read."""
    chain_path = tmp_path / "audit_chain.json"

    main(["ping", "--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert "ping" in captured.out
    assert "GRANTED" in captured.out
    assert "ALLOW" in captured.out


def test_ping_with_confirmation_flags_still_grants(tmp_path: Path) -> None:
    """Both confirmation flags can be set without error; ping is still granted."""
    chain_path = tmp_path / "audit_chain.json"

    exit_code = main(
        [
            "ping",
            "--physical-confirmation-available",
            "--remote-confirmation-available",
            "--chain-path",
            str(chain_path),
        ]
    )

    assert exit_code == 0


def test_ping_persists_the_chain_at_the_given_path(tmp_path: Path) -> None:
    """main() saves the chain at --chain-path, readable by a fresh adapter afterward."""
    chain_path = tmp_path / "audit_chain.json"

    main(["ping", "--chain-path", str(chain_path)])

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1


def test_ping_default_chain_path_is_relative_audit_chain_json(tmp_path: Path) -> None:
    """Omitting --chain-path falls back to ./audit_chain.json in the current directory."""
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        exit_code = main(["ping"])
    finally:
        os.chdir(original_cwd)

    assert exit_code == 0
    assert (tmp_path / "audit_chain.json").exists()


def test_ping_reports_a_tampered_chain_cleanly_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tampered chain file surfaces as a clean error message, not a raw traceback.

    JarvisError exists precisely so a caller can catch "any domain-level
    problem" without committing to a specific failure mode -- this is
    that catch actually being exercised.
    """
    chain_path = tmp_path / "audit_chain.json"
    main(["ping", "--chain-path", str(chain_path)])
    raw = json.loads(chain_path.read_text(encoding="utf-8"))
    raw[0]["record_hash"] = "0" * 64
    chain_path.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = main(["ping", "--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


def test_ping_reports_a_pre_digest_only_format_chain_cleanly_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A chain file written before work package 18 (raw "value", no "value_digest") errors cleanly.

    There is no migration path (see domain/audit.py's module
    docstring) -- the KeyError this raises during decode must still
    surface as a clean "Error: ..." message and exit 1, not a raw
    traceback, exactly like any other error a user can hit.
    """
    chain_path = tmp_path / "audit_chain.json"
    main(["ping", "--chain-path", str(chain_path)])
    raw = json.loads(chain_path.read_text(encoding="utf-8"))
    for record in raw:
        arguments = record["decision"]["invocation"]["arguments"]
        arguments["value"] = {}
        del arguments["value_digest"]
    chain_path.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = main(["ping", "--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


@pytest.mark.parametrize(
    ("subcommand", "expected_command"),
    [
        ("play", MusicCommand.PLAY),
        ("pause", MusicCommand.PAUSE),
        ("next", MusicCommand.NEXT),
        ("previous", MusicCommand.PREVIOUS),
    ],
)
def test_music_subcommand_routes_to_the_matching_music_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    subcommand: str,
    expected_command: MusicCommand,
) -> None:
    """Each music subcommand calls authorize_and_run_music_command with the right MusicCommand."""
    received: list[MusicCommand] = []

    def fake_authorize_and_run(
        command: MusicCommand,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(command)
        return _make_decision(granted=True)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_run_music_command", fake_authorize_and_run
    )

    exit_code = main([subcommand, "--chain-path", str(tmp_path / "audit_chain.json")])

    assert received == [expected_command]
    assert exit_code == 0


def test_music_subcommand_prints_the_command_name_and_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() prints the subcommand name (not "ping") for a music command."""

    def fake_authorize_and_run(
        command: MusicCommand,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_run_music_command", fake_authorize_and_run
    )

    exit_code = main(["pause", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "pause: DENIED" in captured.out
    assert exit_code == 1


def test_music_subcommand_reports_no_media_player_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NoMediaPlayerRunningError from the kernel surfaces as a clean message, not a traceback."""

    def fake_authorize_and_run(
        command: MusicCommand,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "No MPRIS media player is currently running on the session bus."
        raise NoMediaPlayerRunningError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_run_music_command", fake_authorize_and_run
    )

    chain_path = tmp_path / "audit_chain.json"
    exit_code = main(["play", "--physical-confirmation-available", "--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "No MPRIS media player" in captured.err


def test_read_subcommand_routes_the_given_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`jarvis read <path>` calls authorize_and_read_file with that path."""
    received: list[Path] = []
    file_path = tmp_path / "note.txt"

    def fake_authorize_and_read(
        path: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileReadOutcome:
        received.append(path)
        provenance = Provenance.external("note.txt", Classification.SENSITIVE)
        content = Tainted("file contents", provenance)
        decision = _make_decision(granted=True, capability_id="fs.read_file")
        return FileReadOutcome(decision=decision, content=content)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_file", fake_authorize_and_read
    )

    exit_code = main(["read", str(file_path), "--chain-path", str(tmp_path / "audit_chain.json")])

    assert received == [file_path]
    assert exit_code == 0


def test_read_subcommand_prints_the_file_content_when_granted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() prints the decision line and then the file's content."""

    def fake_authorize_and_read(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileReadOutcome:
        content = Tainted("hello from a file", Provenance.external("x", Classification.SENSITIVE))
        decision = _make_decision(granted=True, capability_id="fs.read_file")
        return FileReadOutcome(decision=decision, content=content)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_file", fake_authorize_and_read
    )

    exit_code = main(
        ["read", str(tmp_path / "note.txt"), "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "read: GRANTED" in captured.out
    assert "hello from a file" in captured.out
    assert exit_code == 0


def test_read_subcommand_reports_path_outside_scope_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PathOutsideAllowedScopeError from the kernel surfaces as a clean message, not a traceback."""

    def fake_authorize_and_read(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileReadOutcome:
        msg = "/etc/shadow is outside the allowed root /home/user."
        raise PathOutsideAllowedScopeError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_file", fake_authorize_and_read
    )

    exit_code = main(["read", "/etc/shadow", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "outside the allowed root" in captured.err


def test_read_subcommand_reports_file_not_found_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A granted-but-nonexistent path surfaces as a clean message, not a raw traceback."""

    def fake_authorize_and_read(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileReadOutcome:
        raise FileNotFoundError(2, "No such file or directory", "missing.txt")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_file", fake_authorize_and_read
    )

    exit_code = main(
        ["read", str(tmp_path / "missing.txt"), "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


def test_listen_calls_run_voice_loop_with_the_chain_path_and_a_real_confirmation_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`jarvis listen` calls run_voice_loop with --chain-path and a real confirmation adapter.

    A real Gtk4PhysicalConfirmationAdapter is safe to construct here
    (as opposed to actually running its dialog): its __init__ does no
    I/O, matching every other adapter's convention.
    """
    received: list[tuple[Path, PhysicalConfirmationPort]] = []

    async def fake_run_voice_loop(
        *, chain_path: Path, physical_confirmation: PhysicalConfirmationPort, **_kwargs: object
    ) -> None:
        received.append((chain_path, physical_confirmation))

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)

    chain_path = tmp_path / "audit_chain.json"
    exit_code = main(["listen", "--chain-path", str(chain_path)])

    assert len(received) == 1
    received_chain_path, received_confirmation = received[0]
    assert received_chain_path == chain_path
    assert isinstance(received_confirmation, Gtk4PhysicalConfirmationAdapter)
    assert exit_code == 0


def test_listen_default_chain_path_is_relative_audit_chain_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Omitting --chain-path for listen also falls back to ./audit_chain.json."""
    received: list[Path] = []

    async def fake_run_voice_loop(*, chain_path: Path, **_kwargs: object) -> None:
        received.append(chain_path)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        exit_code = main(["listen"])
    finally:
        os.chdir(original_cwd)

    assert received == [Path("audit_chain.json")]
    assert exit_code == 0


def test_listen_stops_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ctrl+C during the voice loop is treated as a normal stop, not an error -- exit 0."""

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)

    exit_code = main(["listen", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Stopped" in captured.out


def test_listen_prints_a_listening_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() tells the user it's listening before blocking on the voice loop."""

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        return

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)

    main(["listen", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "Listening" in captured.out


def test_listen_does_not_accept_the_confirmation_flags() -> None:
    """listen has no --physical-confirmation-available/--remote-confirmation-available.

    Those flags model a fixed, upfront confirmation state; the voice
    loop asks a real, per-utterance question through the GTK4 dialog
    instead -- see jarvis.cli.main's own module docstring.
    """
    with pytest.raises(SystemExit):
        main(["listen", "--physical-confirmation-available"])


def test_listen_without_verbose_leaves_jarvis_logger_at_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --verbose, the "jarvis" logger stays at WARNING -- no new debug output."""

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        return

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)
    logging.getLogger("jarvis").setLevel(logging.DEBUG)  # simulate a prior --verbose call

    main(["listen", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert logging.getLogger("jarvis").level == logging.WARNING


def test_listen_verbose_raises_the_jarvis_logger_to_debug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--verbose raises the "jarvis" logger (and everything under it) to DEBUG."""

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        return

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)
    logging.getLogger("jarvis").setLevel(logging.WARNING)  # simulate no prior --verbose call

    main(["listen", "--verbose", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert logging.getLogger("jarvis").level == logging.DEBUG
    assert logging.getLogger("jarvis.adapters.wake_word").getEffectiveLevel() == logging.DEBUG


def test_listen_verbose_does_not_touch_third_party_logger_levels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--verbose only raises jarvis's own loggers -- third-party loggers are untouched."""

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        return

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)
    third_party_logger = logging.getLogger("faster_whisper")
    third_party_logger.setLevel(logging.NOTSET)

    main(["listen", "--verbose", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert third_party_logger.getEffectiveLevel() == logging.WARNING


def test_listen_verbose_emits_the_wake_word_score_diagnostic_line(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--verbose actually surfaces a real DEBUG line from the wake-word adapter."""
    logger = logging.getLogger("jarvis.adapters.wake_word")

    async def fake_run_voice_loop(**_kwargs: object) -> None:
        logger.debug("score=%.4f", 0.7965)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_voice_loop", fake_run_voice_loop)

    with caplog.at_level(logging.DEBUG, logger="jarvis"):
        main(["listen", "--verbose", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert "score=0.7965" in caplog.text


def _make_memory_record(identifier: str = "mem:1", text: str = "prefers tabs") -> MemoryRecord:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryRecord(
        identifier=identifier,
        value=Tainted(text, Provenance.user()),
        written_at=now,
        expires_at=now,
    )


def test_memory_write_subcommand_routes_the_given_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`jarvis memory write <text>` calls authorize_and_remember with that text."""
    received: list[str] = []

    def fake_authorize_and_remember(
        text: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        received.append(text)
        decision = _make_decision(granted=True, capability_id="memory.write")
        return MemoryWriteOutcome(decision=decision, identifier="mem:1")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_remember", fake_authorize_and_remember
    )

    exit_code = main(
        ["memory", "write", "prefers tabs", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == ["prefers tabs"]
    assert exit_code == 0


def test_memory_write_subcommand_prints_the_command_label_and_identifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_remember(
        text: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        decision = _make_decision(granted=True, capability_id="memory.write")
        return MemoryWriteOutcome(decision=decision, identifier="mem:42")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_remember", fake_authorize_and_remember
    )

    exit_code = main(
        ["memory", "write", "prefers tabs", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "memory write: GRANTED" in captured.out
    assert "identifier: mem:42" in captured.out
    assert exit_code == 0


def test_memory_write_subcommand_reports_unsupported_value_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """UnsupportedMemoryValueError from the kernel surfaces as a clean message, not a traceback."""

    def fake_authorize_and_remember(
        text: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        msg = "SqliteMemoryAdapter only persists str-valued memories."
        raise UnsupportedMemoryValueError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_remember", fake_authorize_and_remember
    )

    exit_code = main(
        ["memory", "write", "prefers tabs", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


def test_memory_write_subcommand_reports_a_corrupted_database_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real, corrupted memory.sqlite3 file (sqlite3.DatabaseError) fails closed, not a crash.

    Real resilience finding (10-phase combined pass, Phase 2,
    2026-09-05): `sqlite3.DatabaseError`/`sqlite3.Error` is a bare
    `Exception` subclass, not `OSError` -- confirmed by directly
    running `jarvis memory write` against a real, deliberately
    corrupted `memory.sqlite3` file before this fix, which produced a
    raw, unhandled Python traceback instead of this module's own
    established "Error: ..." shape. Fixed by adding `sqlite3.Error` to
    `main()`'s own except tuple (and `kernel/voice_loop.py`'s
    identical one, for the same real "remember"/"recall" voice
    commands).
    """

    def fake_authorize_and_remember(
        text: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        raise sqlite3.DatabaseError("file is not a database")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_remember", fake_authorize_and_remember
    )

    exit_code = main(
        ["memory", "write", "prefers tabs", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


def test_memory_retrieve_subcommand_routes_query_and_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[str, int]] = []

    def fake_authorize_and_recall(
        query: str,
        *,
        limit: int,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryRecallOutcome:
        received.append((query, limit))
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return MemoryRecallOutcome(decision=decision, records=())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_recall", fake_authorize_and_recall
    )

    exit_code = main(
        [
            "memory",
            "retrieve",
            "tabs",
            "--limit",
            "3",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [("tabs", 3)]
    assert exit_code == 0


def test_memory_retrieve_subcommand_prints_each_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_recall(
        query: str,  # noqa: ARG001
        *,
        limit: int,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryRecallOutcome:
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return MemoryRecallOutcome(
            decision=decision, records=(_make_memory_record("mem:7", "prefers tabs"),)
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_recall", fake_authorize_and_recall
    )

    exit_code = main(
        ["memory", "retrieve", "tabs", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "memory retrieve: GRANTED" in captured.out
    assert "mem:7: prefers tabs" in captured.out
    assert exit_code == 0


def test_memory_forget_subcommand_routes_the_given_identifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_forget(
        identifier: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(identifier)
        return _make_decision(granted=True, capability_id="memory.forget")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_forget", fake_authorize_and_forget
    )

    exit_code = main(
        [
            "memory",
            "forget",
            "mem:1",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["mem:1"]
    assert exit_code == 0


def test_memory_forget_subcommand_reports_record_not_found_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_forget(
        identifier: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "No memory record found with identifier 'mem:does-not-exist'."
        raise MemoryRecordNotFoundError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_forget", fake_authorize_and_forget
    )

    exit_code = main(
        [
            "memory",
            "forget",
            "mem:does-not-exist",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "No memory record found" in captured.err


def test_memory_pin_subcommand_routes_the_given_identifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_pin(
        identifier: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(identifier)
        return _make_decision(granted=True, capability_id="memory.pin")

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "authorize_and_pin", fake_authorize_and_pin)

    exit_code = main(
        [
            "memory",
            "pin",
            "mem:1",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["mem:1"]
    assert exit_code == 0


def test_memory_backup_subcommand_routes_the_given_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[Path] = []

    def fake_authorize_and_backup_memory(
        destination_path: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(destination_path)
        return _make_decision(granted=True, capability_id="memory.backup")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_backup_memory",
        fake_authorize_and_backup_memory,
    )

    exit_code = main(
        [
            "memory",
            "backup",
            str(tmp_path / "backup.sqlite3"),
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [tmp_path / "backup.sqlite3"]
    assert exit_code == 0


def test_memory_restore_subcommand_routes_the_given_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[Path] = []

    def fake_authorize_and_restore_memory(
        source_path: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(source_path)
        return _make_decision(granted=True, capability_id="memory.restore")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_restore_memory",
        fake_authorize_and_restore_memory,
    )

    exit_code = main(
        [
            "memory",
            "restore",
            str(tmp_path / "backup.sqlite3"),
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [tmp_path / "backup.sqlite3"]
    assert exit_code == 0


def test_memory_restore_subcommand_denied_by_remote_confirmation_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """memory.restore is MANUAL_ONLY -- remote confirmation alone must not grant it."""

    def fake_authorize_and_restore_memory(
        source_path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(
            granted=physical_confirmation_available, capability_id="memory.restore"
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_restore_memory",
        fake_authorize_and_restore_memory,
    )

    exit_code = main(
        [
            "memory",
            "restore",
            str(tmp_path / "backup.sqlite3"),
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert exit_code == 1


def test_send_email_subcommand_routes_to_and_subject_and_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`jarvis send-email <to...> --subject S --body B` calls authorize_and_send_email."""
    received: list[tuple[tuple[str, ...], str, str]] = []

    async def fake_authorize_and_send_email(  # noqa: PLR0913 -- mirrors the real signature
        to: tuple[str, ...],
        subject: str,
        body: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> Decision:
        received.append((to, subject, body))
        return _make_decision(granted=True, capability_id="communications.send_email")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_send_email", fake_authorize_and_send_email
    )

    exit_code = main(
        [
            "send-email",
            "alice@example.com",
            "bob@example.com",
            "--subject",
            "Hello",
            "--body",
            "The message.",
            "--imap-host",
            "imap.example.com",
            "--smtp-host",
            "smtp.example.com",
            "--username",
            "user@example.com",
            "--password-reference",
            "example-ref",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(("alice@example.com", "bob@example.com"), "Hello", "The message.")]
    assert exit_code == 0


def test_send_email_subcommand_constructs_a_real_adapter_with_the_given_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The real ImapEmailAdapter is built from --imap-host/--smtp-host/--username/--password-reference."""  # noqa: E501
    received_ports: list[ImapEmailAdapter] = []

    async def fake_authorize_and_send_email(  # noqa: PLR0913 -- mirrors the real signature
        to: tuple[str, ...],  # noqa: ARG001
        subject: str,  # noqa: ARG001
        body: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: ImapEmailAdapter,
    ) -> Decision:
        received_ports.append(email_port)
        return _make_decision(granted=True, capability_id="communications.send_email")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_send_email", fake_authorize_and_send_email
    )

    exit_code = main(
        [
            "send-email",
            "alice@example.com",
            "--subject",
            "Hello",
            "--body",
            "The message.",
            "--imap-host",
            "imap.example.com",
            "--smtp-host",
            "smtp.example.com",
            "--username",
            "user@example.com",
            "--password-reference",
            "example-ref",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert len(received_ports) == 1
    assert isinstance(received_ports[0], ImapEmailAdapter)
    assert exit_code == 0


def test_send_email_subcommand_prints_the_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_send_email(  # noqa: PLR0913 -- mirrors the real signature
        to: tuple[str, ...],  # noqa: ARG001
        subject: str,  # noqa: ARG001
        body: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False, capability_id="communications.send_email")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_send_email", fake_authorize_and_send_email
    )

    exit_code = main(
        [
            "send-email",
            "alice@example.com",
            "--subject",
            "Hello",
            "--body",
            "The message.",
            "--imap-host",
            "imap.example.com",
            "--smtp-host",
            "smtp.example.com",
            "--username",
            "user@example.com",
            "--password-reference",
            "example-ref",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "send-email: DENIED" in captured.out
    assert exit_code == 1


def test_send_email_subcommand_reports_secret_not_found_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SecretNotFoundError (a bad --password-reference) surfaces as a clean message."""

    async def fake_authorize_and_send_email(  # noqa: PLR0913 -- mirrors the real signature
        to: tuple[str, ...],  # noqa: ARG001
        subject: str,  # noqa: ARG001
        body: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> Decision:
        msg = "No secret found for reference 'example-ref'."
        raise SecretNotFoundError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_send_email", fake_authorize_and_send_email
    )

    exit_code = main(
        [
            "send-email",
            "alice@example.com",
            "--subject",
            "Hello",
            "--body",
            "The message.",
            "--imap-host",
            "imap.example.com",
            "--smtp-host",
            "smtp.example.com",
            "--username",
            "user@example.com",
            "--password-reference",
            "example-ref",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "No secret found" in captured.err


def test_send_email_subcommand_requires_subject_and_body() -> None:
    with pytest.raises(SystemExit):
        main(["send-email", "alice@example.com"])


_CREATE_EVENT_COMMON_FLAGS = [
    "--summary",
    "Team sync",
    "--start",
    "2026-09-03T10:00:00+00:00",
    "--end",
    "2026-09-03T11:00:00+00:00",
    "--caldav-url",
    "https://caldav.example.com",
    "--username",
    "user@example.com",
    "--password-reference",
    "example-ref",
]


def test_create_calendar_event_subcommand_routes_summary_start_end_attendees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[str, str, str, tuple[str, ...]]] = []

    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,
        start: str,
        end: str,
        attendees: tuple[str, ...],
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> CalendarEventCreateOutcome:
        received.append((summary, start, end, attendees))
        decision = _make_decision(
            granted=True, capability_id="communications.create_calendar_event"
        )
        return CalendarEventCreateOutcome(decision=decision, uid="new-uid")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--attendee",
            "alice@example.com",
            "--attendee",
            "bob@example.com",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [
        (
            "Team sync",
            "2026-09-03T10:00:00+00:00",
            "2026-09-03T11:00:00+00:00",
            ("alice@example.com", "bob@example.com"),
        )
    ]
    assert exit_code == 0


def test_create_calendar_event_subcommand_defaults_to_no_attendees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[str, ...]] = []

    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,  # noqa: ARG001
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        attendees: tuple[str, ...],
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> CalendarEventCreateOutcome:
        received.append(attendees)
        decision = _make_decision(
            granted=True, capability_id="communications.create_calendar_event"
        )
        return CalendarEventCreateOutcome(decision=decision, uid="new-uid")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [()]
    assert exit_code == 0


def test_create_calendar_event_subcommand_constructs_a_real_adapter_with_the_given_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received_ports: list[CalDavCalendarAdapter] = []

    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,  # noqa: ARG001
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        attendees: tuple[str, ...],  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: CalDavCalendarAdapter,
    ) -> CalendarEventCreateOutcome:
        received_ports.append(calendar_port)
        decision = _make_decision(
            granted=True, capability_id="communications.create_calendar_event"
        )
        return CalendarEventCreateOutcome(decision=decision, uid="new-uid")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert len(received_ports) == 1
    assert isinstance(received_ports[0], CalDavCalendarAdapter)
    assert exit_code == 0


def test_create_calendar_event_subcommand_prints_the_decision_and_uid_when_granted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,  # noqa: ARG001
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        attendees: tuple[str, ...],  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> CalendarEventCreateOutcome:
        decision = _make_decision(
            granted=True, capability_id="communications.create_calendar_event"
        )
        return CalendarEventCreateOutcome(decision=decision, uid="brand-new-uid")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "create-calendar-event: GRANTED" in captured.out
    assert "uid: brand-new-uid" in captured.out
    assert exit_code == 0


def test_create_calendar_event_subcommand_prints_denied_without_a_uid_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,  # noqa: ARG001
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        attendees: tuple[str, ...],  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> CalendarEventCreateOutcome:
        decision = _make_decision(
            granted=False, capability_id="communications.create_calendar_event"
        )
        return CalendarEventCreateOutcome(decision=decision, uid=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "create-calendar-event: DENIED" in captured.out
    assert "uid:" not in captured.out
    assert exit_code == 1


def test_create_calendar_event_subcommand_reports_creation_error_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CalendarEventCreationError (a real CalDAV server anomaly) surfaces as a clean message."""

    async def fake_authorize_and_create_calendar_event(  # noqa: PLR0913 -- mirrors the real signature
        summary: str,  # noqa: ARG001
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        attendees: tuple[str, ...],  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> CalendarEventCreateOutcome:
        msg = "Real CalDAV server returned no UID for the newly created event."
        raise CalendarEventCreationError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_calendar_event",
        fake_authorize_and_create_calendar_event,
    )

    exit_code = main(
        [
            "create-calendar-event",
            *_CREATE_EVENT_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "no UID" in captured.err


def test_create_calendar_event_subcommand_requires_summary_start_end() -> None:
    with pytest.raises(SystemExit):
        main(["create-calendar-event", "--caldav-url", "https://caldav.example.com"])


def test_memory_pin_subcommand_prints_the_command_label(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_pin(
        identifier: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False, capability_id="memory.pin")

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "authorize_and_pin", fake_authorize_and_pin)

    exit_code = main(["memory", "pin", "mem:1", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "memory pin: DENIED" in captured.out
    assert exit_code == 1


def test_code_subcommand_routes_task_and_repo_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[str, Path]] = []
    repo_path = tmp_path / "target_repo"

    async def fake_authorize_and_run_coding_task(  # noqa: PLR0913 -- mirrors the real signature
        task: str,
        target_repo: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        max_climbs: int,  # noqa: ARG001
    ) -> tuple[Decision, CodingLoopResult]:
        received.append((task, target_repo))
        decision = _make_decision(granted=True, capability_id="coding.run_task")
        return decision, CodingLoopResult(CodingLoopOutcome.WRITTEN, ())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_run_coding_task",
        fake_authorize_and_run_coding_task,
    )

    exit_code = main(
        ["code", "fix the bug", str(repo_path), "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [("fix the bug", repo_path)]
    assert exit_code == 0


def test_code_subcommand_prints_the_result_label(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_run_coding_task(  # noqa: PLR0913 -- mirrors the real signature
        task: str,  # noqa: ARG001
        target_repo: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        max_climbs: int,  # noqa: ARG001
    ) -> tuple[Decision, CodingLoopResult]:
        decision = _make_decision(granted=True, capability_id="coding.run_task")
        return decision, CodingLoopResult(CodingLoopOutcome.WRITTEN, ())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_run_coding_task",
        fake_authorize_and_run_coding_task,
    )

    exit_code = main(
        [
            "code",
            "fix the bug",
            str(tmp_path / "target_repo"),
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "code: GRANTED" in captured.out
    assert "result: written" in captured.out
    assert exit_code == 0


def test_code_subcommand_requires_task_and_repo_path() -> None:
    with pytest.raises(SystemExit):
        main(["code", "fix the bug"])


def test_draft_subcommand_routes_the_task(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    received: list[str] = []

    async def fake_authorize_and_draft_document(
        task: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        drafts_dir: Path | None,  # noqa: ARG001
    ) -> DraftOutcome:
        received.append(task)
        decision = _make_decision(granted=True, capability_id="job_assistance.draft")
        return DraftOutcome(decision=decision, path=tmp_path / "draft.txt")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_draft_document",
        fake_authorize_and_draft_document,
    )

    exit_code = main(
        ["draft", "draft a cover letter", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == ["draft a cover letter"]
    assert exit_code == 0


def test_draft_subcommand_prints_the_result_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    draft_path = tmp_path / "draft.txt"

    async def fake_authorize_and_draft_document(
        task: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        drafts_dir: Path | None,  # noqa: ARG001
    ) -> DraftOutcome:
        decision = _make_decision(granted=True, capability_id="job_assistance.draft")
        return DraftOutcome(decision=decision, path=draft_path)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_draft_document",
        fake_authorize_and_draft_document,
    )

    exit_code = main(
        ["draft", "draft a cover letter", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "draft: GRANTED" in captured.out
    assert f"result: {draft_path}" in captured.out
    assert exit_code == 0


def test_draft_subcommand_denied_prints_no_result_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_draft_document(
        task: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        drafts_dir: Path | None,  # noqa: ARG001
    ) -> DraftOutcome:
        decision = _make_decision(granted=False, capability_id="job_assistance.draft")
        return DraftOutcome(decision=decision, path=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_draft_document",
        fake_authorize_and_draft_document,
    )

    exit_code = main(
        ["draft", "draft a cover letter", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "draft: DENIED" in captured.out
    assert "result:" not in captured.out
    assert exit_code == 1


def test_draft_subcommand_requires_task() -> None:
    with pytest.raises(SystemExit):
        main(["draft"])


def test_list_dir_subcommand_routes_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[Path] = []
    dir_path = tmp_path / "some_dir"

    def fake_authorize_and_list_dir(
        path: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> DirListOutcome:
        received.append(path)
        decision = _make_decision(granted=True, capability_id="fs.list_dir")
        provenance = Provenance.external(str(path / "note.txt"), Classification.SENSITIVE)
        entries = (Tainted(DirEntry(name="note.txt", is_dir=False), provenance),)
        return DirListOutcome(decision=decision, entries=entries)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_dir", fake_authorize_and_list_dir
    )

    exit_code = main(
        ["list-dir", str(dir_path), "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [dir_path]
    assert exit_code == 0


def test_list_dir_subcommand_prints_each_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_list_dir(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> DirListOutcome:
        decision = _make_decision(granted=True, capability_id="fs.list_dir")
        provenance = Provenance.external("x", Classification.SENSITIVE)
        entries = (
            Tainted(DirEntry(name="note.txt", is_dir=False), provenance),
            Tainted(DirEntry(name="subdir", is_dir=True), provenance),
        )
        return DirListOutcome(decision=decision, entries=entries)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_dir", fake_authorize_and_list_dir
    )

    exit_code = main(
        ["list-dir", str(tmp_path), "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "list-dir: GRANTED" in captured.out
    assert "note.txt" in captured.out
    assert "subdir/" in captured.out
    assert exit_code == 0


def test_list_dir_subcommand_denied_prints_no_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_list_dir(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> DirListOutcome:
        decision = _make_decision(granted=False, capability_id="fs.list_dir")
        return DirListOutcome(decision=decision, entries=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_dir", fake_authorize_and_list_dir
    )

    exit_code = main(
        ["list-dir", str(tmp_path), "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "list-dir: DENIED" in captured.out
    assert exit_code == 1


def test_list_dir_subcommand_requires_path() -> None:
    with pytest.raises(SystemExit):
        main(["list-dir"])


def test_move_file_subcommand_routes_source_and_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, Path]] = []
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"

    def fake_authorize_and_move_file(
        move_source: Path,
        move_destination: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((move_source, move_destination))
        return _make_decision(granted=True, capability_id="fs.move_file")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_move_file", fake_authorize_and_move_file
    )

    exit_code = main(
        [
            "move-file",
            str(source),
            str(destination),
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(source, destination)]
    assert exit_code == 0


def test_move_file_subcommand_requires_source_and_destination() -> None:
    with pytest.raises(SystemExit):
        main(["move-file", "only-one-path"])


def test_delete_file_subcommand_routes_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[Path] = []
    target = tmp_path / "note.txt"

    def fake_authorize_and_delete_file(
        path: Path,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(path)
        return _make_decision(granted=True, capability_id="fs.delete_file")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_delete_file",
        fake_authorize_and_delete_file,
    )

    exit_code = main(
        ["delete-file", str(target), "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [target]
    assert exit_code == 0


def test_delete_file_subcommand_denied_without_physical_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """fs.delete_file's Tier.MANUAL_ONLY floor -- remote confirmation alone is never enough."""

    def fake_authorize_and_delete_file(
        path: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False, capability_id="fs.delete_file")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_delete_file",
        fake_authorize_and_delete_file,
    )

    exit_code = main(
        [
            "delete-file",
            str(tmp_path / "note.txt"),
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "delete-file: DENIED" in captured.out
    assert exit_code == 1


def test_delete_file_subcommand_requires_path() -> None:
    with pytest.raises(SystemExit):
        main(["delete-file"])


_DESKTOP_CONFIRM_OR_ABOVE_INVOCATIONS: tuple[tuple[str, list[str]], ...] = (
    ("open-brave-url", ["open-brave-url", "https://example.com"]),
    ("open-vscode-file", ["open-vscode-file", "notes.txt"]),
    ("send-claude-text", ["send-claude-text", "hello"]),
    ("send-chatgpt-text", ["send-chatgpt-text", "hello"]),
    ("stop-docker-container", ["stop-docker-container", "some-container"]),
    ("git-create-branch", ["git-create-branch", "some-repo", "feature-x"]),
    ("git-commit", ["git-commit", "some-repo", "a real commit message"]),
    ("git-push", ["git-push", "some-repo", "origin", "main"]),
    ("git-force-push", ["git-force-push", "some-repo", "origin", "main"]),
)


@pytest.mark.parametrize(
    ("command_label", "argv"), _DESKTOP_CONFIRM_OR_ABOVE_INVOCATIONS, ids=lambda p: p[0]
)
def test_desktop_confirm_or_above_command_is_denied_with_no_confirmation_flags(
    command_label: str,  # noqa: ARG001 -- used only for the pytest id, not the test body
    argv: list[str],
    tmp_path: Path,
) -> None:
    """CLI invocation alone, with no confirmation flag at all, denies every real
    kernel/desktop.py capability at Tier.CONFIRM or above -- the real, unmocked
    kernel function is exercised directly (not faked), proving the CLI's own
    default confirmation flags (both False) do not silently grant anything.
    Real adapter construction (BraveCliAdapter/GitCliAdapter/etc.) only ever
    happens inside `if decision.granted:` in kernel/desktop.py itself, so this
    never touches a real browser, editor, or git/docker binary even though
    nothing here is mocked."""
    exit_code = main([*argv, "--chain-path", str(tmp_path / "audit_chain.json")])

    assert exit_code == 1


def test_open_brave_url_subcommand_routes_the_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_open_brave_url(
        url: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(url)
        return _make_decision(granted=True, capability_id="desktop.brave_open_url")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_brave_url",
        fake_authorize_and_open_brave_url,
    )

    exit_code = main(
        [
            "open-brave-url",
            "https://example.com",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["https://example.com"]
    assert exit_code == 0


def test_open_vscode_file_subcommand_routes_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_open_vscode_file(
        path: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(path)
        return _make_decision(granted=True, capability_id="desktop.vscode_open_file")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_vscode_file",
        fake_authorize_and_open_vscode_file,
    )

    exit_code = main(
        ["open-vscode-file", "notes.txt", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == ["notes.txt"]
    assert exit_code == 0


def test_send_claude_text_subcommand_routes_the_app_and_text_and_launch_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[ChatApp, str, tuple[str, ...] | None]] = []

    def fake_authorize_and_send_text_to_chat_app(  # noqa: PLR0913 -- mirrors the real signature
        app: ChatApp,
        text: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        desktop_window: object,  # noqa: ARG001
        launch_command: tuple[str, ...] | None,
    ) -> Decision:
        received.append((app, text, launch_command))
        return _make_decision(granted=True, capability_id="desktop.claude_app_send_text")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_send_text_to_chat_app",
        fake_authorize_and_send_text_to_chat_app,
    )

    exit_code = main(
        ["send-claude-text", "hello there", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [(ChatApp.CLAUDE, "hello there", ("claude-desktop",))]
    assert exit_code == 0


def test_send_chatgpt_text_subcommand_routes_with_no_launch_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unlike Claude, no confirmed real launch command exists for the ChatGPT app --
    the CLI passes launch_command=None honestly, never a guessed value."""
    received: list[tuple[ChatApp, str, tuple[str, ...] | None]] = []

    def fake_authorize_and_send_text_to_chat_app(  # noqa: PLR0913 -- mirrors the real signature
        app: ChatApp,
        text: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        desktop_window: object,  # noqa: ARG001
        launch_command: tuple[str, ...] | None,
    ) -> Decision:
        received.append((app, text, launch_command))
        return _make_decision(granted=True, capability_id="desktop.chatgpt_app_send_text")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_send_text_to_chat_app",
        fake_authorize_and_send_text_to_chat_app,
    )

    exit_code = main(
        ["send-chatgpt-text", "hello there", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [(ChatApp.CHATGPT, "hello there", None)]
    assert exit_code == 0


def test_list_docker_containers_subcommand_prints_each_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_list_docker_containers(
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> DockerListContainersOutcome:
        decision = _make_decision(granted=True, capability_id="docker.list_containers")
        return DockerListContainersOutcome(decision=decision, containers=("web", "db"))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_docker_containers",
        fake_authorize_and_list_docker_containers,
    )

    exit_code = main(["list-docker-containers", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "list-docker-containers: GRANTED" in captured.out
    assert "web" in captured.out
    assert "db" in captured.out
    assert exit_code == 0


def test_stop_docker_container_subcommand_routes_the_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_stop_docker_container(
        container: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(container)
        return _make_decision(granted=True, capability_id="docker.stop_container")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_stop_docker_container",
        fake_authorize_and_stop_docker_container,
    )

    exit_code = main(
        [
            "stop-docker-container",
            "web",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["web"]
    assert exit_code == 0


def test_git_status_subcommand_prints_the_real_status_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_get_git_status(
        repo_dir: Path,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> GitStatusOutcome:
        decision = _make_decision(granted=True, capability_id="git.status")
        return GitStatusOutcome(decision=decision, status="On branch main\nnothing to commit")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_get_git_status",
        fake_authorize_and_get_git_status,
    )

    exit_code = main(
        ["git-status", str(tmp_path), "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "git-status: GRANTED" in captured.out
    assert "On branch main" in captured.out
    assert exit_code == 0


def test_git_create_branch_subcommand_routes_repo_dir_and_branch_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, str]] = []

    def fake_authorize_and_create_git_branch(
        repo_dir: Path,
        branch_name: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((repo_dir, branch_name))
        return _make_decision(granted=True, capability_id="git.create_branch")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_git_branch",
        fake_authorize_and_create_git_branch,
    )

    exit_code = main(
        [
            "git-create-branch",
            str(tmp_path),
            "feature-x",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(tmp_path, "feature-x")]
    assert exit_code == 0


def test_git_commit_subcommand_routes_repo_dir_and_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, str]] = []

    def fake_authorize_and_commit_git(
        repo_dir: Path,
        message: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((repo_dir, message))
        return _make_decision(granted=True, capability_id="git.commit")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_commit_git", fake_authorize_and_commit_git
    )

    exit_code = main(
        [
            "git-commit",
            str(tmp_path),
            "a real commit message",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(tmp_path, "a real commit message")]
    assert exit_code == 0


def test_git_push_subcommand_routes_repo_dir_remote_and_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, str, str]] = []

    def fake_authorize_and_push_git(  # noqa: PLR0913 -- mirrors the real signature
        repo_dir: Path,
        remote: str,
        branch: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((repo_dir, remote, branch))
        return _make_decision(granted=True, capability_id="git.push")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_push_git", fake_authorize_and_push_git
    )

    exit_code = main(
        [
            "git-push",
            str(tmp_path),
            "origin",
            "main",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(tmp_path, "origin", "main")]
    assert exit_code == 0


def test_git_force_push_subcommand_routes_repo_dir_remote_and_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, str, str]] = []

    def fake_authorize_and_force_push_git(  # noqa: PLR0913 -- mirrors the real signature
        repo_dir: Path,
        remote: str,
        branch: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((repo_dir, remote, branch))
        return _make_decision(granted=True, capability_id="git.force_push")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_force_push_git",
        fake_authorize_and_force_push_git,
    )

    exit_code = main(
        [
            "git-force-push",
            str(tmp_path),
            "origin",
            "main",
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(tmp_path, "origin", "main")]
    assert exit_code == 0


def test_git_force_push_subcommand_denied_with_only_remote_confirmation(
    tmp_path: Path,
) -> None:
    """The single most important desktop-wiring proof: git.force_push's real
    Tier.MANUAL_ONLY floor is never satisfiable by --remote-confirmation-available
    alone through the CLI, exercising the real, unmocked kernel function."""
    exit_code = main(
        [
            "git-force-push",
            str(tmp_path),
            "origin",
            "main",
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert exit_code == 1


def test_open_brave_url_subcommand_requires_url() -> None:
    with pytest.raises(SystemExit):
        main(["open-brave-url"])


def test_git_push_subcommand_requires_repo_dir_remote_and_branch() -> None:
    with pytest.raises(SystemExit):
        main(["git-push", "some-repo"])


# --- Overnight hardening pass (2026-09-04): missing/malformed required
# arguments for all eleven newly-wired desktop.*/docker.*/git.* subcommands,
# and the real unhandled-exception bug found and fixed in main()'s own
# except tuple. Each "requires" test proves argparse itself fails closed
# with a clear SystemExit (its own usage/error message on stderr, exit
# code 2) -- never a stack trace, never a silent no-op -- before any real
# kernel/desktop.py call is ever reached.


@pytest.mark.parametrize(
    "argv",
    [
        ["open-brave-url"],
        ["open-vscode-file"],
        ["send-claude-text"],
        ["send-chatgpt-text"],
        ["stop-docker-container"],
        ["git-status"],
        ["git-create-branch"],
        ["git-create-branch", "some-repo"],
        ["git-commit"],
        ["git-commit", "some-repo"],
        ["git-push"],
        ["git-push", "some-repo"],
        ["git-push", "some-repo", "origin"],
        ["git-force-push"],
        ["git-force-push", "some-repo"],
        ["git-force-push", "some-repo", "origin"],
    ],
    ids=lambda argv: " ".join(argv) or "empty",
)
def test_desktop_subcommands_fail_closed_on_missing_required_arguments(
    argv: list[str],
) -> None:
    """Every newly-wired command with a missing required positional argument
    fails closed via a clean SystemExit -- argparse's own real, existing
    mechanism -- never a stack trace, never a silent no-op."""
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code != 0


def test_list_docker_containers_subcommand_requires_no_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """list-docker-containers takes zero positional arguments -- confirming
    it is not silently missing one, unlike every other newly-wired command."""

    def fake_authorize_and_list_docker_containers(
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> DockerListContainersOutcome:
        return DockerListContainersOutcome(
            decision=_make_decision(granted=True, capability_id="docker.list_containers"),
            containers=(),
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_docker_containers",
        fake_authorize_and_list_docker_containers,
    )

    exit_code = main(["list-docker-containers", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert exit_code == 0


def test_send_chatgpt_text_with_no_confirmed_window_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real bug this hardening pass found and fixed: a granted
    "send-chatgpt-text" whose real AT-SPI2 lookup can't find or launch the
    app (no confirmed launch_command exists for ChatGPT, see
    _CLAUDE_APP_LAUNCH_COMMAND's own docstring) used to crash main() with
    an unhandled WindowNotFoundError instead of printing a clean error and
    exiting 1. Proven fixed here by making the real kernel function raise
    the real, typed exception AtspiDesktopWindowAdapter.find_or_launch()
    actually raises in this scenario, confirming main() now catches it."""

    def fake_authorize_and_send_text_to_chat_app(  # noqa: PLR0913 -- mirrors the real signature
        app: ChatApp,  # noqa: ARG001
        text: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        desktop_window: object,  # noqa: ARG001
        launch_command: tuple[str, ...] | None,  # noqa: ARG001
    ) -> Decision:
        msg = "No window found for app_id 'chatgpt'."
        raise WindowNotFoundError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_send_text_to_chat_app",
        fake_authorize_and_send_text_to_chat_app,
    )

    exit_code = main(
        [
            "send-chatgpt-text",
            "hello",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "No window found" in captured.err


def test_send_claude_text_window_action_failure_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same real bug class, for WindowActionFailedError (a real focus/
    type_text failure after the window was actually found) -- proven fixed
    for both real exception types this port can raise, not just one."""

    def fake_authorize_and_send_text_to_chat_app(  # noqa: PLR0913 -- mirrors the real signature
        app: ChatApp,  # noqa: ARG001
        text: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        desktop_window: object,  # noqa: ARG001
        launch_command: tuple[str, ...] | None,  # noqa: ARG001
    ) -> Decision:
        msg = "Focusing window for 'claude' failed."
        raise WindowActionFailedError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_send_text_to_chat_app",
        fake_authorize_and_send_text_to_chat_app,
    )

    exit_code = main(
        [
            "send-claude-text",
            "hello",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Focusing window" in captured.err


def test_open_brave_url_browser_launch_failure_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """BrowserLaunchFailedError (ports/brave.py) -- the real exception a
    failed real `brave-browser` subprocess launch raises -- is now caught."""

    def fake_authorize_and_open_brave_url(
        url: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "Failed to launch Brave."
        raise BrowserLaunchFailedError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_brave_url",
        fake_authorize_and_open_brave_url,
    )

    exit_code = main(
        [
            "open-brave-url",
            "https://example.com",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed to launch Brave" in captured.err


def test_open_vscode_file_editor_launch_failure_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """EditorLaunchFailedError (ports/vscode.py) is now caught."""

    def fake_authorize_and_open_vscode_file(
        path: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "Failed to launch VS Code."
        raise EditorLaunchFailedError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_vscode_file",
        fake_authorize_and_open_vscode_file,
    )

    exit_code = main(
        [
            "open-vscode-file",
            "notes.txt",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed to launch VS Code" in captured.err


def test_stop_docker_container_command_failure_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DockerCommandFailedError (ports/docker.py) is now caught."""

    def fake_authorize_and_stop_docker_container(
        container: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "docker stop exited non-zero."
        raise DockerCommandFailedError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_stop_docker_container",
        fake_authorize_and_stop_docker_container,
    )

    exit_code = main(
        [
            "stop-docker-container",
            "web",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "docker stop exited non-zero" in captured.err


def test_git_commit_command_failure_fails_closed_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """GitCommandFailedError (ports/git.py) is now caught."""

    def fake_authorize_and_commit_git(
        repo_dir: Path,  # noqa: ARG001
        message: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        msg = "git commit exited non-zero."
        raise GitCommandFailedError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_commit_git", fake_authorize_and_commit_git
    )

    exit_code = main(
        [
            "git-commit",
            str(tmp_path),
            "a real commit message",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "git commit exited non-zero" in captured.err
