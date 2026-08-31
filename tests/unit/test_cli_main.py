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
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.memory import UnsupportedMemoryValueError
from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter
from jarvis.cli.main import main
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.files import FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.memory import MemoryRecallOutcome, MemoryWriteOutcome
from jarvis.kernel.music import MusicCommand
from jarvis.ports.media_player import NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError

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
