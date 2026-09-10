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

import importlib.metadata
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
from jarvis.application.planning.executor import PlanExecutionResult, PlanStepRecord
from jarvis.application.planning.planner import PlanStep
from jarvis.application.routing.router import RouteKind, RouteResult
from jarvis.cli.main import _check_binary, _check_ollama_reachable, main
from jarvis.domain.browser import PageHandle
from jarvis.domain.calendar import CalendarEvent
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.domain.file_system import DirEntry
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.communications import CalendarEventCreateOutcome
from jarvis.kernel.desktop import ChatApp, DockerListContainersOutcome, GitStatusOutcome
from jarvis.kernel.files import (
    ContentSearchOutcome,
    DirListOutcome,
    FileFindOutcome,
    FileReadOutcome,
    PathOutsideAllowedScopeError,
    RecentFilesOutcome,
)
from jarvis.kernel.job_application import JobApplicationListOutcome
from jarvis.kernel.job_assistance import (
    ApplicationFolderAlreadyExistsError,
    DraftOutcome,
    PrepareApplicationFolderOutcome,
)
from jarvis.kernel.job_search import JobSearchSite
from jarvis.kernel.memory import MemoryRecallOutcome, MemoryWriteOutcome
from jarvis.kernel.music import MusicCommand
from jarvis.kernel.project import ProjectStartOutcome, ProjectStatusOutcome
from jarvis.kernel.router import RouteOutcome
from jarvis.kernel.tasks import TaskCreateOutcome, TaskGetOutcome, TaskListOutcome, TaskRunOutcome
from jarvis.ports.brave import BrowserLaunchFailedError
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError
from jarvis.ports.docker import DockerCommandFailedError
from jarvis.ports.email import EmailConnectionError, EmailMessageNotFoundError
from jarvis.ports.git import GitCommandFailedError
from jarvis.ports.media_player import NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from jarvis.cli.ui_server import UiServerConfig
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


class _FakeBoundServer:
    """A minimal stand-in for a real JarvisUiServer -- only `server_address` is ever read."""

    def __init__(self, port: int) -> None:
        self.server_address = ("127.0.0.1", port)


_TEST_UI_PORT = 9999
_REBOUND_UI_PORT = 54321
_EXPECTED_DEFAULT_UI_PORT = 8765  # mirrors jarvis.cli.main's own _DEFAULT_UI_PORT


def test_ui_starts_a_real_server_with_the_given_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`jarvis ui` builds a real UiServerConfig from its own flags and serves it."""
    received: list[tuple[int, UiServerConfig]] = []

    def fake_create_server(port: int, config: UiServerConfig) -> object:
        received.append((port, config))
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    chain_path = tmp_path / "audit_chain.json"
    exit_code = main(
        [
            "ui",
            "--port",
            str(_TEST_UI_PORT),
            "--chain-path",
            str(chain_path),
            "--physical-confirmation-available",
        ]
    )

    assert exit_code == 0
    assert len(received) == 1
    port, config = received[0]
    assert port == _TEST_UI_PORT
    assert config.chain_path == chain_path
    assert config.physical_confirmation_available is True
    assert config.remote_confirmation_available is False


def test_ui_default_port_is_8765(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    received: list[int] = []

    def fake_create_server(port: int, _config: object) -> object:
        received.append(port)
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(["ui", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert received == [_EXPECTED_DEFAULT_UI_PORT]


def test_ui_stops_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_create_server(port: int, _config: object) -> object:
        return _FakeBoundServer(port)

    def fake_run_ui_server(_server: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", fake_run_ui_server)

    exit_code = main(["ui", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Stopped" in captured.out


def test_ui_prints_the_real_bound_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The printed URL reflects the real, bound port -- not blindly the requested one."""

    def fake_create_server(_port: int, _config: object) -> object:
        return _FakeBoundServer(_REBOUND_UI_PORT)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(["ui", "--port", "0", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert f"http://127.0.0.1:{_REBOUND_UI_PORT}" in captured.out


def test_ui_has_no_host_flag() -> None:
    """No --host/bind-address flag exists at all, on purpose -- see ui_server's own docstring."""
    with pytest.raises(SystemExit):
        main(["ui", "--host", "0.0.0.0"])


def test_ui_with_no_email_or_calendar_flags_leaves_both_ports_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WP-114: omitting the new, optional email/calendar flags behaves exactly as before."""
    received: list[UiServerConfig] = []

    def fake_create_server(port: int, config: UiServerConfig) -> object:
        received.append(config)
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(["ui", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert len(received) == 1
    assert received[0].email_port is None
    assert received[0].calendar_port is None


def test_ui_with_all_four_email_flags_constructs_a_real_email_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WP-114: a real ImapEmailAdapter is constructed when all four email flags are given."""
    received: list[UiServerConfig] = []

    def fake_create_server(port: int, config: UiServerConfig) -> object:
        received.append(config)
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(
        [
            "ui",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
            "--email-imap-host",
            "imap.example.com",
            "--email-smtp-host",
            "smtp.example.com",
            "--email-username",
            "user@example.com",
            "--email-password-reference",
            "example-ref",
        ]
    )

    assert len(received) == 1
    assert isinstance(received[0].email_port, ImapEmailAdapter)
    assert received[0].calendar_port is None


def test_ui_with_a_partial_set_of_email_flags_leaves_the_port_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WP-114: all-or-nothing -- three of four email flags is the same as zero."""
    received: list[UiServerConfig] = []

    def fake_create_server(port: int, config: UiServerConfig) -> object:
        received.append(config)
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(
        [
            "ui",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
            "--email-imap-host",
            "imap.example.com",
            "--email-smtp-host",
            "smtp.example.com",
            "--email-username",
            "user@example.com",
        ]
    )

    assert len(received) == 1
    assert received[0].email_port is None


def test_ui_with_all_three_calendar_flags_constructs_a_real_calendar_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WP-114: a real CalDavCalendarAdapter is constructed when all three calendar flags are given."""  # noqa: E501
    received: list[UiServerConfig] = []

    def fake_create_server(port: int, config: UiServerConfig) -> object:
        received.append(config)
        return _FakeBoundServer(port)

    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "create_server", fake_create_server)
    monkeypatch.setattr(sys.modules["jarvis.cli.main"], "run_ui_server", lambda _server: None)

    main(
        [
            "ui",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
            "--calendar-caldav-url",
            "https://caldav.example.com",
            "--calendar-username",
            "user@example.com",
            "--calendar-password-reference",
            "example-ref",
        ]
    )

    assert len(received) == 1
    assert received[0].email_port is None
    assert isinstance(received[0].calendar_port, CalDavCalendarAdapter)


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


def test_memory_wipe_subcommand_reports_the_real_deleted_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_wipe_memory(
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        decision = _make_decision(granted=True, capability_id="memory.wipe")
        return type("Outcome", (), {"decision": decision, "deleted_count": 3})()

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_wipe_memory",
        fake_authorize_and_wipe_memory,
    )

    exit_code = main(
        [
            "memory",
            "wipe",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "deleted: 3" in captured.out


def test_memory_wipe_subcommand_denied_by_remote_confirmation_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """memory.wipe is MANUAL_ONLY -- remote confirmation alone must not grant it."""

    def fake_authorize_and_wipe_memory(
        *,
        physical_confirmation_available: bool,
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        decision = _make_decision(
            granted=physical_confirmation_available, capability_id="memory.wipe"
        )
        deleted_count = 0 if physical_confirmation_available else None
        return type("Outcome", (), {"decision": decision, "deleted_count": deleted_count})()

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_wipe_memory",
        fake_authorize_and_wipe_memory,
    )

    exit_code = main(
        [
            "memory",
            "wipe",
            "--remote-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert exit_code == 1


def test_audit_history_subcommand_shows_a_real_prior_ping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real, unmocked, end-to-end proof: a real prior ping shows up in real audit history."""
    chain_path = tmp_path / "audit_chain.json"
    main(["ping", "--chain-path", str(chain_path)])
    capsys.readouterr()

    exit_code = main(["audit-history", "--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "0: ping GRANTED" in captured.out


def test_audit_history_subcommand_respects_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "audit_chain.json"
    main(["ping", "--chain-path", str(chain_path)])
    main(["ping", "--chain-path", str(chain_path)])
    capsys.readouterr()

    exit_code = main(["audit-history", "--chain-path", str(chain_path), "--limit", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    # Real, honest behavior: the audit-history call itself is already
    # appended to the chain by the time filtering runs, so the single
    # most recent record is this view's own call, not either ping.
    assert "2: audit.history GRANTED" in captured.out
    assert "1: ping GRANTED" not in captured.out
    assert "0: ping GRANTED" not in captured.out


def test_audit_history_subcommand_respects_capability_id_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `read` (not `memory retrieve`) deliberately: the CLI has no
    # --database-path override, so a real `memory retrieve` call would
    # default to a relative `memory.sqlite3` resolved against the real
    # process CWD -- a real, known, pre-existing hazard in this
    # project's own CLI wiring, avoided here rather than reproduced.
    real_file = tmp_path / "some_file.txt"
    real_file.write_text("content", encoding="utf-8")
    chain_path = tmp_path / "audit_chain.json"
    main(["ping", "--chain-path", str(chain_path)])
    main(["read", str(real_file), "--chain-path", str(chain_path)])
    capsys.readouterr()

    exit_code = main(["audit-history", "--chain-path", str(chain_path), "--capability-id", "ping"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ping GRANTED" in captured.out
    assert "fs.read_file" not in captured.out


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


_PREPARE_APPLICATION_COMMON_FLAGS = [
    "--base-dir",
    "/tmp/jarvis-test-applications",
    "--month-label",
    "September 2026",
    "--cv-template",
    "/tmp/jarvis-test-cv.tex",
    "--cover-letter-template",
    "/tmp/jarvis-test-cover-letter.tex",
]


def test_prepare_application_subcommand_routes_job_title_and_company(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[Path, str, Path, Path, str, str, str | None]] = []

    async def fake_authorize_and_prepare_application_folder(  # noqa: PLR0913, PLR0917 -- mirrors the real signature
        base_dir: Path,
        month_label: str,
        cv_template_path: Path,
        cover_letter_template_path: Path,
        job_title: str,
        company: str,
        task_description: str | None,
        providers: object | None = None,  # noqa: ARG001
        *,
        force: bool,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> PrepareApplicationFolderOutcome:
        received.append(
            (
                base_dir,
                month_label,
                cv_template_path,
                cover_letter_template_path,
                job_title,
                company,
                task_description,
            )
        )
        decision = _make_decision(
            granted=True, capability_id="job_assistance.prepare_application_folder"
        )
        return PrepareApplicationFolderOutcome(
            decision=decision,
            cv_path=tmp_path / "CV" / "main.tex",
            cover_letter_template_path=tmp_path / "Cover Letter" / "main.tex",
            draft_decision=_make_decision(granted=True, capability_id="job_assistance.draft"),
            body_path=tmp_path / "Cover Letter" / "body.tex",
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        fake_authorize_and_prepare_application_folder,
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [
        (
            Path("/tmp/jarvis-test-applications"),
            "September 2026",
            Path("/tmp/jarvis-test-cv.tex"),
            Path("/tmp/jarvis-test-cover-letter.tex"),
            "Software Engineer",
            "Acme Corp",
            None,
        )
    ]
    assert exit_code == 0


def test_prepare_application_subcommand_prints_the_real_paths_and_reminder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cv_path = tmp_path / "September 2026" / "CV" / "main.tex"
    copied_cover_letter_template_path = tmp_path / "September 2026" / "Cover Letter" / "main.tex"
    body_path = tmp_path / "September 2026" / "Cover Letter" / "body.tex"

    async def fake_authorize_and_prepare_application_folder(  # noqa: PLR0913, PLR0917 -- mirrors the real signature
        base_dir: Path,  # noqa: ARG001
        month_label: str,  # noqa: ARG001
        cv_template_path: Path,  # noqa: ARG001
        cover_letter_template_path: Path,  # noqa: ARG001
        job_title: str,  # noqa: ARG001
        company: str,  # noqa: ARG001
        task_description: str | None,  # noqa: ARG001
        providers: object | None = None,  # noqa: ARG001
        *,
        force: bool,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> PrepareApplicationFolderOutcome:
        decision = _make_decision(
            granted=True, capability_id="job_assistance.prepare_application_folder"
        )
        return PrepareApplicationFolderOutcome(
            decision=decision,
            cv_path=cv_path,
            cover_letter_template_path=copied_cover_letter_template_path,
            draft_decision=_make_decision(granted=True, capability_id="job_assistance.draft"),
            body_path=body_path,
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        fake_authorize_and_prepare_application_folder,
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "prepare-application: GRANTED" in captured.out
    assert f"CV copied to: {cv_path}" in captured.out
    assert f"Cover letter template copied to: {copied_cover_letter_template_path}" in captured.out
    assert "cover-letter body drafting: GRANTED" in captured.out
    assert f"Cover letter body drafted to: {body_path}" in captured.out
    assert r"\input{body.tex}" in captured.out
    assert exit_code == 0


def test_prepare_application_subcommand_denied_prints_no_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_prepare_application_folder(  # noqa: PLR0913, PLR0917 -- mirrors the real signature
        base_dir: Path,  # noqa: ARG001
        month_label: str,  # noqa: ARG001
        cv_template_path: Path,  # noqa: ARG001
        cover_letter_template_path: Path,  # noqa: ARG001
        job_title: str,  # noqa: ARG001
        company: str,  # noqa: ARG001
        task_description: str | None,  # noqa: ARG001
        providers: object | None = None,  # noqa: ARG001
        *,
        force: bool,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> PrepareApplicationFolderOutcome:
        decision = _make_decision(
            granted=False, capability_id="job_assistance.prepare_application_folder"
        )
        return PrepareApplicationFolderOutcome(
            decision=decision,
            cv_path=None,
            cover_letter_template_path=None,
            draft_decision=None,
            body_path=None,
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        fake_authorize_and_prepare_application_folder,
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "prepare-application: DENIED" in captured.out
    assert "CV copied to:" not in captured.out
    assert exit_code == 1


def test_prepare_application_subcommand_already_exists_reports_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real idempotency safety check surfaces as a clean CLI error, not a crash."""

    async def fake_authorize_and_prepare_application_folder(  # noqa: PLR0913, PLR0917 -- mirrors the real signature
        base_dir: Path,  # noqa: ARG001
        month_label: str,  # noqa: ARG001
        cv_template_path: Path,  # noqa: ARG001
        cover_letter_template_path: Path,  # noqa: ARG001
        job_title: str,  # noqa: ARG001
        company: str,  # noqa: ARG001
        task_description: str | None,  # noqa: ARG001
        providers: object | None = None,  # noqa: ARG001
        *,
        force: bool,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> PrepareApplicationFolderOutcome:
        msg = "already has real application content -- pass force=True (CLI: --force)"
        raise ApplicationFolderAlreadyExistsError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        fake_authorize_and_prepare_application_folder,
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "--force" in captured.err


def test_prepare_application_subcommand_requires_job_title_company_and_flags() -> None:
    with pytest.raises(SystemExit):
        main(["prepare-application"])
    with pytest.raises(SystemExit):
        main(["prepare-application", "Software Engineer", "Acme Corp"])


async def _fake_prepare_application_folder_granted(  # noqa: PLR0913, PLR0917 -- mirrors the real signature
    base_dir: Path,  # noqa: ARG001
    month_label: str,  # noqa: ARG001
    cv_template_path: Path,  # noqa: ARG001
    cover_letter_template_path: Path,  # noqa: ARG001
    job_title: str,  # noqa: ARG001
    company: str,  # noqa: ARG001
    task_description: str | None,  # noqa: ARG001
    providers: object | None = None,  # noqa: ARG001
    *,
    force: bool,  # noqa: ARG001
    physical_confirmation_available: bool,  # noqa: ARG001
    remote_confirmation_available: bool,  # noqa: ARG001
    chain_path: Path,  # noqa: ARG001
) -> PrepareApplicationFolderOutcome:
    cv_path = Path("/tmp/jarvis-test-applications/September 2026/CV/main.tex")
    return PrepareApplicationFolderOutcome(
        decision=_make_decision(
            granted=True, capability_id="job_assistance.prepare_application_folder"
        ),
        cv_path=cv_path,
        cover_letter_template_path=cv_path.parent.parent / "Cover Letter" / "main.tex",
        draft_decision=_make_decision(granted=True, capability_id="job_assistance.draft"),
        body_path=cv_path.parent.parent / "Cover Letter" / "body.tex",
    )


def test_prepare_application_with_record_flag_also_records_a_ledger_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--record calls job_application.record with status=drafted and the real created folder."""
    received: list[tuple[str, str, str, str | None]] = []

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        _fake_prepare_application_folder_granted,
    )

    def fake_authorize_and_record_job_application(  # noqa: PLR0913 -- one per composition-function pass-through
        company: str,
        role: str,
        *,
        status: str,
        folder: str | None = None,
        notes: str | None = None,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        received.append((company, role, status, folder))
        decision = _make_decision(granted=True, capability_id="memory.write")
        return MemoryWriteOutcome(decision=decision, identifier="mem:99")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_record_job_application",
        fake_authorize_and_record_job_application,
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--record",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [
        (
            "Acme Corp",
            "Software Engineer",
            "drafted",
            "/tmp/jarvis-test-applications/September 2026",
        )
    ]
    assert "job-application recorded: mem:99" in captured.out
    assert exit_code == 0


def test_prepare_application_without_record_flag_records_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Omitting --record is byte-for-byte the same as before this flag existed: no ledger call."""
    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_prepare_application_folder",
        _fake_prepare_application_folder_granted,
    )

    def fail_if_called(*args: object, **kwargs: object) -> MemoryWriteOutcome:  # noqa: ARG001
        msg = "authorize_and_record_job_application must not be called without --record"
        raise AssertionError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_record_job_application", fail_if_called
    )

    exit_code = main(
        [
            "prepare-application",
            "Software Engineer",
            "Acme Corp",
            *_PREPARE_APPLICATION_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "job-application recorded:" not in captured.out
    assert exit_code == 0


def test_plan_run_subcommand_executes_and_reports_each_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A granted plan run reports the outer decision plus one real line per plan step."""
    received: list[str] = []

    async def fake_authorize_and_run_plan(
        goal: str,
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, PlanExecutionResult]:
        received.append(goal)
        decision = _make_decision(granted=True, capability_id="planning.run_plan")
        step_decision = _make_decision(granted=True, capability_id="fs.read_file")
        step = PlanStep(CapabilityId("fs.read_file"), {"path": "/tmp/a.txt"})
        record = PlanStepRecord(step=step, decision=step_decision, result=None)
        return decision, PlanExecutionResult(step_records=(record,), aborted=False)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_run_plan", fake_authorize_and_run_plan
    )

    exit_code = main(
        [
            "plan",
            "run",
            "read a.txt",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["read a.txt"]
    assert exit_code == 0
    assert "plan run: GRANTED" in captured.out
    assert "step: fs.read_file GRANTED" in captured.out


def test_plan_run_subcommand_denied_attempts_no_plan_steps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A denied outer gate (no confirmation) never even calls the real kernel function's own planner."""  # noqa: E501
    exit_code = main(
        ["plan", "run", "do something", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "plan run: DENIED" in captured.out
    assert "step:" not in captured.out


def test_plan_run_subcommand_requires_goal() -> None:
    with pytest.raises(SystemExit):
        main(["plan", "run"])


def test_project_start_subcommand_reports_a_completed_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str] = []

    async def fake_authorize_and_start_project(
        goal: str,
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        received.append(goal)
        decision = _make_decision(granted=True, capability_id="planning.run_plan")
        return ProjectStartOutcome(
            decision=decision, state="completed", reason=None, record_identifier="mem:1"
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_start_project",
        fake_authorize_and_start_project,
    )

    exit_code = main(
        [
            "project",
            "start",
            "continue the LiDAR project",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["continue the LiDAR project"]
    assert exit_code == 0
    assert "project start: GRANTED" in captured.out
    assert "state: completed" in captured.out
    assert "recorded: mem:1" in captured.out


def test_project_start_subcommand_reports_a_stuck_state_with_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_start_project(
        goal: str,  # noqa: ARG001
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        decision = _make_decision(granted=True, capability_id="planning.run_plan")
        return ProjectStartOutcome(
            decision=decision,
            state="stuck",
            reason="Plan step 'git.commit' was denied.",
            record_identifier="mem:2",
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_start_project",
        fake_authorize_and_start_project,
    )

    exit_code = main(
        [
            "project",
            "start",
            "a goal with a blocked step",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "state: stuck" in captured.out
    assert "reason: Plan step 'git.commit' was denied." in captured.out


def test_project_start_subcommand_denied_with_no_confirmation_flags(tmp_path: Path) -> None:
    """CLI invocation alone denies planning.run_plan's own gate -- no confirmation flag at all."""
    exit_code = main(
        ["project", "start", "do something", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert exit_code == 1


def test_project_status_subcommand_prints_a_found_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-WP-109, legacy-stored "stuck" record still displays correctly -- pass-through."""
    received: list[str] = []

    def fake_authorize_and_get_project_status(
        goal: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        received.append(goal)
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        record = MemoryRecord(
            identifier="mem:3",
            value=Tainted(
                {
                    "kind": "task",
                    "goal": goal,
                    "status": "stuck",
                    "reason": "Plan validation failed.",
                    "created_at": "2026-09-08T00:00:00+00:00",
                    "updated_at": "2026-09-08T00:00:00+00:00",
                },
                Provenance.user(),
            ),
            written_at=datetime(2026, 9, 8, tzinfo=UTC),
            expires_at=None,
        )
        return ProjectStatusOutcome(decision=decision, record=record)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_get_project_status",
        fake_authorize_and_get_project_status,
    )

    exit_code = main(
        [
            "project",
            "status",
            "continue the LiDAR project",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["continue the LiDAR project"]
    assert exit_code == 0
    assert "goal: continue the LiDAR project" in captured.out
    assert "state: stuck" in captured.out
    assert "reason: Plan validation failed." in captured.out
    assert "updated_at: 2026-09-08T00:00:00+00:00" in captured.out


def test_project_status_subcommand_translates_canonical_failed_to_stuck_for_display(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """WP-109: a real, canonically-stored "failed" record still prints "state: stuck"."""

    def fake_authorize_and_get_project_status(
        goal: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        record = MemoryRecord(
            identifier="mem:4",
            value=Tainted(
                {
                    "kind": "task",
                    "goal": "continue the LiDAR project",
                    "status": "failed",
                    "reason": "PlanningError: not valid JSON",
                    "created_at": "2026-09-09T00:00:00+00:00",
                    "updated_at": "2026-09-09T00:00:00+00:00",
                },
                Provenance.user(),
            ),
            written_at=datetime(2026, 9, 9, tzinfo=UTC),
            expires_at=None,
        )
        return ProjectStatusOutcome(decision=decision, record=record)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_get_project_status",
        fake_authorize_and_get_project_status,
    )

    exit_code = main(
        [
            "project",
            "status",
            "continue the LiDAR project",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "state: stuck" in captured.out
    assert "state: failed" not in captured.out


def test_project_status_subcommand_reports_nothing_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_get_project_status(
        goal: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> object:
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return ProjectStatusOutcome(decision=decision, record=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_get_project_status",
        fake_authorize_and_get_project_status,
    )

    exit_code = main(
        [
            "project",
            "status",
            "a goal never started",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No project-goal record found for this goal." in captured.out


def test_project_subcommand_requires_a_real_project_command() -> None:
    with pytest.raises(SystemExit):
        main(["project"])


def test_project_start_subcommand_requires_goal() -> None:
    with pytest.raises(SystemExit):
        main(["project", "start"])


def test_project_status_subcommand_requires_goal() -> None:
    with pytest.raises(SystemExit):
        main(["project", "status"])


def test_task_create_subcommand_reports_a_real_task_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str] = []

    def fake_authorize_and_create_task(
        goal: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> TaskCreateOutcome:
        received.append(goal)
        decision = _make_decision(granted=True, capability_id="memory.write")
        return TaskCreateOutcome(decision=decision, task_id="task:1")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_create_task",
        fake_authorize_and_create_task,
    )

    exit_code = main(
        [
            "task",
            "create",
            "continue the LiDAR project",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["continue the LiDAR project"]
    assert exit_code == 0
    assert "task create: GRANTED" in captured.out
    assert "task_id: task:1" in captured.out


def test_task_run_subcommand_reports_status_and_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[tuple[str, str]] = []

    async def fake_authorize_and_run_task(  # noqa: PLR0913 -- mirrors the real signature
        task_id: str,
        goal: str,
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> TaskRunOutcome:
        received.append((task_id, goal))
        decision = _make_decision(granted=True, capability_id="planning.run_plan")
        return TaskRunOutcome(decision=decision, status="failed", reason="a real, stated reason")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_run_task", fake_authorize_and_run_task
    )

    exit_code = main(
        [
            "task",
            "run",
            "task:1",
            "continue the LiDAR project",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [("task:1", "continue the LiDAR project")]
    assert exit_code == 0
    assert "status: failed" in captured.out
    assert "reason: a real, stated reason" in captured.out


def test_task_status_subcommand_prints_a_found_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str] = []

    def fake_authorize_and_get_task(
        task_id: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> TaskGetOutcome:
        received.append(task_id)
        decision = _make_decision(granted=True, capability_id="memory.get")
        record = MemoryRecord(
            identifier=task_id,
            value=Tainted(
                {
                    "kind": "task",
                    "goal": "continue the LiDAR project",
                    "status": "completed",
                    "reason": None,
                    "created_at": "2026-09-09T00:00:00+00:00",
                    "updated_at": "2026-09-09T00:05:00+00:00",
                },
                Provenance.user(),
            ),
            written_at=datetime(2026, 9, 9, tzinfo=UTC),
            expires_at=None,
        )
        return TaskGetOutcome(decision=decision, record=record)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_get_task", fake_authorize_and_get_task
    )

    exit_code = main(
        ["task", "status", "task:1", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert received == ["task:1"]
    assert exit_code == 0
    assert "task:1: goal='continue the LiDAR project' status=completed" in captured.out


def test_task_status_subcommand_reports_nothing_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_get_task(
        task_id: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> TaskGetOutcome:
        decision = _make_decision(granted=True, capability_id="memory.get")
        return TaskGetOutcome(decision=decision, record=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_get_task", fake_authorize_and_get_task
    )

    exit_code = main(
        ["task", "status", "no-such-id", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No task found for this identifier." in captured.out


def test_task_list_subcommand_prints_each_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str | None] = []

    def fake_authorize_and_list_tasks(
        *,
        status: str | None = None,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> TaskListOutcome:
        received.append(status)
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        record = MemoryRecord(
            identifier="task:1",
            value=Tainted(
                {
                    "kind": "task",
                    "goal": "a goal",
                    "status": "completed",
                    "reason": None,
                    "created_at": "2026-09-09T00:00:00+00:00",
                    "updated_at": "2026-09-09T00:00:00+00:00",
                },
                Provenance.user(),
            ),
            written_at=datetime(2026, 9, 9, tzinfo=UTC),
            expires_at=None,
        )
        return TaskListOutcome(decision=decision, records=(record,))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_tasks", fake_authorize_and_list_tasks
    )

    exit_code = main(
        [
            "task",
            "list",
            "--status",
            "completed",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["completed"]
    assert exit_code == 0
    assert "task:1: goal='a goal' status=completed" in captured.out


def test_task_subcommand_requires_a_real_task_command() -> None:
    with pytest.raises(SystemExit):
        main(["task"])


def test_task_create_subcommand_requires_goal() -> None:
    with pytest.raises(SystemExit):
        main(["task", "create"])


def test_task_run_subcommand_requires_task_id_and_goal() -> None:
    with pytest.raises(SystemExit):
        main(["task", "run"])
    with pytest.raises(SystemExit):
        main(["task", "run", "task:1"])


def test_task_status_subcommand_requires_task_id() -> None:
    with pytest.raises(SystemExit):
        main(["task", "status"])


def test_do_subcommand_prints_a_granted_deterministic_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A granted, wired deterministic route prints its route, decision, and real result."""
    received: list[str] = []

    async def fake_authorize_and_route(  # noqa: PLR0913 -- mirrors the real signature
        text: str,
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        database_path: Path | None = None,  # noqa: ARG001
        embedding_port: object | None = None,  # noqa: ARG001
        clock: object | None = None,  # noqa: ARG001
        id_port: object | None = None,  # noqa: ARG001
    ) -> RouteOutcome:
        received.append(text)
        route = RouteResult(
            kind=RouteKind.DETERMINISTIC_COMMAND,
            original_input=text,
            confidence=1.0,
            source="deterministic",
            capability_id=CapabilityId("memory.retrieve"),
            arguments=Tainted({"query": "anything"}, Provenance.user()),
        )
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return RouteOutcome(
            route=route, decision=decision, execution_result="fake-result", task_id=None
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_route", fake_authorize_and_route
    )

    exit_code = main(["do", "recall anything", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert received == ["recall anything"]
    assert exit_code == 0
    assert "do: GRANTED" in captured.out
    assert "route: deterministic_command" in captured.out
    assert "capability_id: memory.retrieve" in captured.out
    assert "result: 'fake-result'" in captured.out


def test_do_subcommand_prints_not_routed_for_an_unknown_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A route with no downstream Decision prints NOT_ROUTED and exits non-zero, never GRANTED."""

    async def fake_authorize_and_route(  # noqa: PLR0913 -- mirrors the real signature
        text: str,  # noqa: ARG001
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        database_path: Path | None = None,  # noqa: ARG001
        embedding_port: object | None = None,  # noqa: ARG001
        clock: object | None = None,  # noqa: ARG001
        id_port: object | None = None,  # noqa: ARG001
    ) -> RouteOutcome:
        route = RouteResult(
            kind=RouteKind.UNKNOWN,
            original_input="asdkjaslkdj",
            confidence=0.0,
            source="deterministic",
            detail="No known deterministic command matched this request.",
        )
        return RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_route", fake_authorize_and_route
    )

    exit_code = main(["do", "asdkjaslkdj", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "do: NOT_ROUTED" in captured.out
    assert "GRANTED" not in captured.out
    assert "DENIED" not in captured.out
    assert "route: unknown" in captured.out
    assert "detail: No known deterministic command matched this request." in captured.out


def test_do_subcommand_reports_a_recognized_but_unwired_capability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real, recognized capability with no wired executor is reported, never executed."""

    async def fake_authorize_and_route(  # noqa: PLR0913 -- mirrors the real signature
        text: str,  # noqa: ARG001
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        database_path: Path | None = None,  # noqa: ARG001
        embedding_port: object | None = None,  # noqa: ARG001
        clock: object | None = None,  # noqa: ARG001
        id_port: object | None = None,  # noqa: ARG001
    ) -> RouteOutcome:
        route = RouteResult(
            kind=RouteKind.DETERMINISTIC_COMMAND,
            original_input="force push my repo",
            confidence=0.5,
            source="reasoning",
            capability_id=CapabilityId("git.force_push"),
            arguments=Tainted({}, Provenance.user()),
        )
        return RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_route", fake_authorize_and_route
    )

    exit_code = main(
        ["do", "force push my repo", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "do: NOT_ROUTED" in captured.out
    assert "capability_id: git.force_push" in captured.out
    assert "not wired for direct execution via 'do'" in captured.out


def test_do_subcommand_prints_a_complex_goal_routes_task_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A granted complex_goal route prints the real goal and the new task's own id."""

    async def fake_authorize_and_route(  # noqa: PLR0913 -- mirrors the real signature
        text: str,  # noqa: ARG001
        provider: object | None = None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        database_path: Path | None = None,  # noqa: ARG001
        embedding_port: object | None = None,  # noqa: ARG001
        clock: object | None = None,  # noqa: ARG001
        id_port: object | None = None,  # noqa: ARG001
    ) -> RouteOutcome:
        route = RouteResult(
            kind=RouteKind.COMPLEX_GOAL,
            original_input="find good internships",
            confidence=0.5,
            source="reasoning",
            goal="find good internships",
        )
        decision = _make_decision(granted=True, capability_id="memory.write")
        return RouteOutcome(route=route, decision=decision, execution_result=None, task_id="mem:9")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_route", fake_authorize_and_route
    )

    exit_code = main(
        [
            "do",
            "find good internships",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "do: GRANTED" in captured.out
    assert "goal: find good internships" in captured.out
    assert "task_id: mem:9" in captured.out
    assert captured.out.count("task_id:") == 1


def test_do_subcommand_requires_text() -> None:
    with pytest.raises(SystemExit):
        main(["do"])


_EMAIL_COMMON_FLAGS = [
    "--imap-host",
    "imap.example.com",
    "--smtp-host",
    "smtp.example.com",
    "--username",
    "user@example.com",
    "--password-reference",
    "example-ref",
]


def test_email_list_subcommand_reports_each_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[tuple[str, int]] = []

    async def fake_authorize_and_list_email(  # noqa: PLR0913 -- mirrors the real signature
        folder: str,
        limit: int,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> tuple[Decision, tuple[Tainted[EmailSummary], ...]]:
        received.append((folder, limit))
        decision = _make_decision(granted=True, capability_id="communications.list_email")
        summary = EmailSummary(
            message_id="<1@localhost>",
            sender="alice@example.com",
            subject="Hello",
            received_at="2026-09-06T00:00:00+00:00",
        )
        return decision, (Tainted(summary, Provenance.external("imap", Classification.PERSONAL)),)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_email", fake_authorize_and_list_email
    )

    exit_code = main(
        [
            "email",
            "list",
            "--folder",
            "INBOX",
            "--limit",
            "5",
            *_EMAIL_COMMON_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [("INBOX", 5)]
    assert exit_code == 0
    assert "email list: GRANTED" in captured.out
    assert "<1@localhost>: alice@example.com -- Hello" in captured.out


def test_email_read_subcommand_reports_the_full_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str] = []

    async def fake_authorize_and_read_email(
        message_id: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[EmailMessage]]:
        received.append(message_id)
        decision = _make_decision(granted=True, capability_id="communications.read_email")
        message = EmailMessage(
            message_id="<1@localhost>",
            sender="alice@example.com",
            recipients=("bob@example.com",),
            subject="Hello",
            body="The message body.",
            received_at="2026-09-06T00:00:00+00:00",
        )
        return decision, Tainted(message, Provenance.external("imap", Classification.PERSONAL))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_email", fake_authorize_and_read_email
    )

    exit_code = main(
        [
            "email",
            "read",
            "<1@localhost>",
            *_EMAIL_COMMON_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["<1@localhost>"]
    assert exit_code == 0
    assert "email read: GRANTED" in captured.out
    assert "Subject: Hello" in captured.out
    assert "The message body." in captured.out


def test_email_list_subcommand_denied_prints_no_summaries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``communications.list_email`` is ``Tier.ALLOW`` (always granted for real) --
    mirroring ``list-dir``'s own identical-tier precedent, a denied outcome is
    proven via a fake kernel function, not the real, unconditionally-granting one."""

    async def fake_authorize_and_list_email(  # noqa: PLR0913 -- mirrors the real signature
        folder: str,  # noqa: ARG001
        limit: int,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> tuple[Decision, tuple[Tainted[EmailSummary], ...] | None]:
        decision = _make_decision(granted=False, capability_id="communications.list_email")
        return decision, None

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_email", fake_authorize_and_list_email
    )

    exit_code = main(
        ["email", "list", *_EMAIL_COMMON_FLAGS, "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "email list: DENIED" in captured.out


def test_email_read_subcommand_reports_message_not_found_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_read_email(
        message_id: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[EmailMessage] | None]:
        msg = "No message found for id '<missing@localhost>'."
        raise EmailMessageNotFoundError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_read_email", fake_authorize_and_read_email
    )

    exit_code = main(
        [
            "email",
            "read",
            "<missing@localhost>",
            *_EMAIL_COMMON_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "No message found" in captured.err


def test_email_list_subcommand_reports_connection_error_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_list_email(  # noqa: PLR0913 -- mirrors the real signature
        folder: str,  # noqa: ARG001
        limit: int,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        email_port: object,  # noqa: ARG001
    ) -> tuple[Decision, tuple[Tainted[EmailSummary], ...] | None]:
        msg = "Connection to the IMAP server was lost."
        raise EmailConnectionError(msg)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_list_email", fake_authorize_and_list_email
    )

    exit_code = main(
        [
            "email",
            "list",
            *_EMAIL_COMMON_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
    assert "Connection to the IMAP server was lost" in captured.err


def test_email_read_subcommand_requires_message_id() -> None:
    with pytest.raises(SystemExit):
        main(["email", "read", *_EMAIL_COMMON_FLAGS])


def test_email_list_subcommand_requires_connection_flags() -> None:
    with pytest.raises(SystemExit):
        main(["email", "list"])


_CALENDAR_LIST_EVENTS_COMMON_FLAGS = [
    "--start",
    "2026-09-03T00:00:00+00:00",
    "--end",
    "2026-09-10T00:00:00+00:00",
    "--caldav-url",
    "https://caldav.example.com",
    "--username",
    "user@example.com",
    "--password-reference",
    "example-ref",
]


def test_calendar_list_events_subcommand_reports_each_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[tuple[str, str]] = []

    async def fake_authorize_and_list_calendar_events(  # noqa: PLR0913 -- mirrors the real signature
        start: str,
        end: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> tuple[Decision, tuple[Tainted[CalendarEvent], ...]]:
        received.append((start, end))
        decision = _make_decision(granted=True, capability_id="communications.list_calendar_events")
        event = CalendarEvent(
            uid="event-1",
            summary="Team sync",
            start="2026-09-03T10:00:00+00:00",
            end="2026-09-03T11:00:00+00:00",
            attendees=(),
        )
        return decision, (Tainted(event, Provenance.external("caldav", Classification.SENSITIVE)),)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_calendar_events",
        fake_authorize_and_list_calendar_events,
    )

    exit_code = main(
        [
            "calendar",
            "list-events",
            *_CALENDAR_LIST_EVENTS_COMMON_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [("2026-09-03T00:00:00+00:00", "2026-09-10T00:00:00+00:00")]
    assert exit_code == 0
    assert "calendar list-events: GRANTED" in captured.out
    assert (
        "event-1: Team sync (2026-09-03T10:00:00+00:00 -- 2026-09-03T11:00:00+00:00)"
        in captured.out
    )


def test_calendar_list_events_subcommand_denied_prints_no_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_list_calendar_events(  # noqa: PLR0913 -- mirrors the real signature
        start: str,  # noqa: ARG001
        end: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
        calendar_port: object,  # noqa: ARG001
    ) -> tuple[Decision, tuple[Tainted[CalendarEvent], ...] | None]:
        decision = _make_decision(
            granted=False, capability_id="communications.list_calendar_events"
        )
        return decision, None

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_calendar_events",
        fake_authorize_and_list_calendar_events,
    )

    exit_code = main(
        [
            "calendar",
            "list-events",
            *_CALENDAR_LIST_EVENTS_COMMON_FLAGS,
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "calendar list-events: DENIED" in captured.out
    assert exit_code == 1


def test_calendar_list_events_subcommand_requires_start_and_end() -> None:
    with pytest.raises(SystemExit):
        main(["calendar", "list-events", "--caldav-url", "https://caldav.example.com"])


def test_calendar_list_events_subcommand_requires_connection_flags() -> None:
    with pytest.raises(SystemExit):
        main(["calendar", "list-events", "--start", "2026-09-03T00:00:00+00:00"])


def test_calendar_subcommand_requires_a_real_calendar_command() -> None:
    with pytest.raises(SystemExit):
        main(["calendar"])


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


def test_fs_find_subcommand_routes_the_pattern(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_find_files(
        pattern: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileFindOutcome:
        received.append(pattern)
        decision = _make_decision(granted=True, capability_id="fs.find")
        return FileFindOutcome(decision=decision, matches=(tmp_path / "a.py",))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_find_files", fake_authorize_and_find_files
    )

    exit_code = main(["fs", "find", "*.py", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert received == ["*.py"]
    assert exit_code == 0


def test_fs_find_subcommand_prints_each_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_find_files(
        pattern: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> FileFindOutcome:
        decision = _make_decision(granted=True, capability_id="fs.find")
        return FileFindOutcome(decision=decision, matches=(tmp_path / "a.py", tmp_path / "b.py"))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_find_files", fake_authorize_and_find_files
    )

    exit_code = main(["fs", "find", "*.py", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "fs find: GRANTED" in captured.out
    assert str(tmp_path / "a.py") in captured.out
    assert str(tmp_path / "b.py") in captured.out
    assert exit_code == 0


def test_fs_find_subcommand_requires_pattern() -> None:
    with pytest.raises(SystemExit):
        main(["fs", "find"])


def test_fs_search_content_subcommand_routes_the_query(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_search_content(
        query: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> ContentSearchOutcome:
        received.append(query)
        decision = _make_decision(granted=True, capability_id="fs.search_content")
        return ContentSearchOutcome(decision=decision, matches=(), capped=False)

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_search_content",
        fake_authorize_and_search_content,
    )

    exit_code = main(
        ["fs", "search-content", "TODO", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == ["TODO"]
    assert exit_code == 0


def test_fs_search_content_subcommand_prints_matches_and_capped_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_search_content(
        query: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> ContentSearchOutcome:
        decision = _make_decision(granted=True, capability_id="fs.search_content")
        return ContentSearchOutcome(
            decision=decision,
            matches=((tmp_path / "a.txt", 3, "TODO: fix this"),),
            capped=True,
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_search_content",
        fake_authorize_and_search_content,
    )

    exit_code = main(
        ["fs", "search-content", "TODO", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "fs search-content: GRANTED" in captured.out
    assert f"{tmp_path / 'a.txt'}:3: TODO: fix this" in captured.out
    assert "cap was reached" in captured.err
    assert exit_code == 0


def test_fs_search_content_subcommand_requires_query() -> None:
    with pytest.raises(SystemExit):
        main(["fs", "search-content"])


def test_fs_recent_subcommand_routes_the_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[int] = []

    def fake_authorize_and_list_recent_files(
        *,
        limit: int,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> RecentFilesOutcome:
        received.append(limit)
        decision = _make_decision(granted=True, capability_id="fs.recent")
        return RecentFilesOutcome(decision=decision, files=())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_recent_files",
        fake_authorize_and_list_recent_files,
    )

    exit_code = main(
        ["fs", "recent", "--limit", "5", "--chain-path", str(tmp_path / "audit_chain.json")]
    )

    assert received == [5]
    assert exit_code == 0


def test_fs_recent_subcommand_defaults_limit_to_twenty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[int] = []

    def fake_authorize_and_list_recent_files(
        *,
        limit: int,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> RecentFilesOutcome:
        received.append(limit)
        decision = _make_decision(granted=True, capability_id="fs.recent")
        return RecentFilesOutcome(decision=decision, files=())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_recent_files",
        fake_authorize_and_list_recent_files,
    )

    main(["fs", "recent", "--chain-path", str(tmp_path / "audit_chain.json")])

    assert received == [20]


def test_fs_recent_subcommand_prints_each_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_list_recent_files(
        *,
        limit: int,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> RecentFilesOutcome:
        decision = _make_decision(granted=True, capability_id="fs.recent")
        return RecentFilesOutcome(decision=decision, files=(tmp_path / "new.txt",))

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_recent_files",
        fake_authorize_and_list_recent_files,
    )

    exit_code = main(["fs", "recent", "--chain-path", str(tmp_path / "audit_chain.json")])
    captured = capsys.readouterr()

    assert "fs recent: GRANTED" in captured.out
    assert str(tmp_path / "new.txt") in captured.out
    assert exit_code == 0


def test_fs_subcommand_requires_a_real_fs_command() -> None:
    with pytest.raises(SystemExit):
        main(["fs"])


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


def test_job_search_subcommand_routes_site_keywords_and_location(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[JobSearchSite, str, str | None]] = []

    def fake_authorize_and_open_job_search(  # noqa: PLR0913 -- mirrors the real signature
        site: JobSearchSite,
        keywords: str,
        location: str | None,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append((site, keywords, location))
        return _make_decision(granted=True, capability_id="job_search.open_results")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_job_search",
        fake_authorize_and_open_job_search,
    )

    exit_code = main(
        [
            "job-search",
            "python developer",
            "--site",
            "linkedin",
            "--location",
            "remote",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [(JobSearchSite.LINKEDIN, "python developer", "remote")]
    assert exit_code == 0


def test_job_search_subcommand_prints_the_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_open_job_search(  # noqa: PLR0913 -- mirrors the real signature
        site: JobSearchSite,  # noqa: ARG001
        keywords: str,  # noqa: ARG001
        location: str | None,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False, capability_id="job_search.open_results")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_open_job_search",
        fake_authorize_and_open_job_search,
    )

    exit_code = main(
        [
            "job-search",
            "data scientist",
            "--site",
            "indeed",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "job-search: DENIED" in captured.out
    assert exit_code == 1


def test_job_search_subcommand_requires_keywords_and_site() -> None:
    with pytest.raises(SystemExit):
        main(["job-search"])
    with pytest.raises(SystemExit):
        main(["job-search", "python developer"])


def test_job_search_subcommand_rejects_an_invalid_site() -> None:
    with pytest.raises(SystemExit):
        main(["job-search", "python developer", "--site", "monster"])


def test_find_careers_page_subcommand_routes_the_company(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str] = []

    def fake_authorize_and_find_careers_page(
        company: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(company)
        return _make_decision(granted=True, capability_id="job_search.find_careers_page")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_find_careers_page",
        fake_authorize_and_find_careers_page,
    )

    exit_code = main(
        [
            "find-careers-page",
            "Boston Dynamics",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["Boston Dynamics"]
    assert exit_code == 0


def test_find_careers_page_subcommand_prints_the_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_find_careers_page(
        company: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        return _make_decision(granted=False, capability_id="job_search.find_careers_page")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_find_careers_page",
        fake_authorize_and_find_careers_page,
    )

    exit_code = main(
        [
            "find-careers-page",
            "Boston Dynamics",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "find-careers-page: DENIED" in captured.out
    assert exit_code == 1


def test_find_careers_page_subcommand_requires_company() -> None:
    with pytest.raises(SystemExit):
        main(["find-careers-page"])


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


def _make_job_application_record(  # noqa: PLR0913 -- one per test-fixture field
    identifier: str,
    *,
    company: str,
    role: str,
    status: str,
    folder: str | None,
    date_applied: str = "2026-09-08T00:00:00+00:00",
    notes: str | None = None,
) -> MemoryRecord:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    value: dict[str, object] = {
        "kind": "job_application",
        "company": company,
        "role": role,
        "status": status,
        "date_applied": date_applied,
        "folder": folder,
        "notes": notes,
    }
    return MemoryRecord(
        identifier=identifier,
        value=Tainted(value, Provenance.user()),
        written_at=now,
        expires_at=now,
    )


def test_job_application_record_subcommand_routes_all_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[tuple[str, str, str, str | None, str | None]] = []

    def fake_authorize_and_record_job_application(  # noqa: PLR0913 -- one per composition-function pass-through
        company: str,
        role: str,
        *,
        status: str,
        folder: str | None,
        notes: str | None,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> MemoryWriteOutcome:
        received.append((company, role, status, folder, notes))
        decision = _make_decision(granted=True, capability_id="memory.write")
        return MemoryWriteOutcome(decision=decision, identifier="mem:1")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_record_job_application",
        fake_authorize_and_record_job_application,
    )

    exit_code = main(
        [
            "job-application",
            "record",
            "Acme Corp",
            "Software Engineer",
            "--status",
            "applied",
            "--folder",
            "/home/user/applications/2026-09/acme",
            "--notes",
            "Referred by a friend.",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == [
        (
            "Acme Corp",
            "Software Engineer",
            "applied",
            "/home/user/applications/2026-09/acme",
            "Referred by a friend.",
        )
    ]
    assert exit_code == 0


def test_job_application_record_subcommand_rejects_an_invalid_status(tmp_path: Path) -> None:
    """argparse's own `choices=` rejects an unknown status before any kernel call is made."""
    with pytest.raises(SystemExit):
        main(
            [
                "job-application",
                "record",
                "Acme Corp",
                "Software Engineer",
                "--status",
                "ghosted",
                "--chain-path",
                str(tmp_path / "audit_chain.json"),
            ]
        )


def test_job_application_list_subcommand_routes_status_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[str | None] = []

    def fake_authorize_and_list_job_applications(
        *,
        status: str | None,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> JobApplicationListOutcome:
        received.append(status)
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return JobApplicationListOutcome(decision=decision, records=())

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_job_applications",
        fake_authorize_and_list_job_applications,
    )

    exit_code = main(
        [
            "job-application",
            "list",
            "--status",
            "interviewing",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert received == ["interviewing"]
    assert exit_code == 0


def test_job_application_list_subcommand_prints_a_readable_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_authorize_and_list_job_applications(
        *,
        status: str | None,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> JobApplicationListOutcome:
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return JobApplicationListOutcome(
            decision=decision,
            records=(
                _make_job_application_record(
                    "mem:1",
                    company="Acme Corp",
                    role="Software Engineer",
                    status="applied",
                    folder="/home/user/applications/2026-09/acme",
                ),
            ),
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_job_applications",
        fake_authorize_and_list_job_applications,
    )

    exit_code = main(
        ["job-application", "list", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "COMPANY" in captured.out
    assert "ROLE" in captured.out
    assert "STATUS" in captured.out
    assert "FOLDER" in captured.out
    assert "Acme Corp" in captured.out
    assert "Software Engineer" in captured.out
    assert "applied" in captured.out
    assert "/home/user/applications/2026-09/acme" in captured.out
    assert exit_code == 0


def test_job_application_list_subcommand_displays_a_missing_folder_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manually-recorded application (no --folder) displays as '-', not 'None' or a crash."""

    def fake_authorize_and_list_job_applications(
        *,
        status: str | None,  # noqa: ARG001
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> JobApplicationListOutcome:
        decision = _make_decision(granted=True, capability_id="memory.retrieve")
        return JobApplicationListOutcome(
            decision=decision,
            records=(
                _make_job_application_record(
                    "mem:1",
                    company="Acme Corp",
                    role="Software Engineer",
                    status="drafted",
                    folder=None,
                ),
            ),
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_list_job_applications",
        fake_authorize_and_list_job_applications,
    )

    exit_code = main(
        ["job-application", "list", "--chain-path", str(tmp_path / "audit_chain.json")]
    )
    captured = capsys.readouterr()

    assert "None" not in captured.out
    assert "-" in captured.out
    assert exit_code == 0


_FAKE_HANDLE = PageHandle(
    debug_port=9222, target_id="target-abc", process_id=1234, user_data_dir="/tmp/fake-profile"
)
_HANDLE_FLAGS = [
    "--debug-port",
    "9222",
    "--target-id",
    "target-abc",
    "--process-id",
    "1234",
    "--user-data-dir",
    "/tmp/fake-profile",
]


def test_browser_open_subcommand_routes_url_and_prints_handle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[str] = []

    async def fake_authorize_and_open_page(
        url: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, PageHandle]:
        received.append(url)
        decision = _make_decision(granted=True, capability_id="browser.open_page")
        return decision, _FAKE_HANDLE

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_open_page", fake_authorize_and_open_page
    )

    exit_code = main(
        [
            "browser",
            "open",
            "https://example.com",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == ["https://example.com"]
    assert "browser open: GRANTED" in captured.out
    assert "debug_port: 9222" in captured.out
    assert "target_id: target-abc" in captured.out
    assert "process_id: 1234" in captured.out
    assert "user_data_dir: /tmp/fake-profile" in captured.out
    assert exit_code == 0


def test_browser_open_subcommand_denied_prints_no_handle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_authorize_and_open_page(
        url: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, PageHandle | None]:
        decision = _make_decision(granted=False, capability_id="browser.open_page")
        return decision, None

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_open_page", fake_authorize_and_open_page
    )

    exit_code = main(
        [
            "browser",
            "open",
            "https://example.com",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "browser open: DENIED" in captured.out
    assert "debug_port:" not in captured.out
    assert exit_code == 1


def test_browser_open_subcommand_requires_url() -> None:
    with pytest.raises(SystemExit):
        main(["browser", "open"])


def test_browser_screenshot_subcommand_reconstructs_handle_and_writes_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[PageHandle] = []
    output_path = tmp_path / "shot.png"

    async def fake_authorize_and_capture_screenshot(
        handle: PageHandle,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[bytes]]:
        received.append(handle)
        decision = _make_decision(granted=True, capability_id="browser.screenshot")
        content = Tainted(b"\x89PNGfakepixels", Provenance.external("t", Classification.SENSITIVE))
        return decision, content

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_capture_screenshot",
        fake_authorize_and_capture_screenshot,
    )

    exit_code = main(
        [
            "browser",
            "screenshot",
            *_HANDLE_FLAGS,
            "--output",
            str(output_path),
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [_FAKE_HANDLE]
    assert output_path.read_bytes() == b"\x89PNGfakepixels"
    assert f"saved to: {output_path}" in captured.out
    assert exit_code == 0


def test_browser_screenshot_subcommand_denied_writes_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "shot.png"

    async def fake_authorize_and_capture_screenshot(
        handle: PageHandle,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[bytes] | None]:
        decision = _make_decision(granted=False, capability_id="browser.screenshot")
        return decision, None

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "authorize_and_capture_screenshot",
        fake_authorize_and_capture_screenshot,
    )

    exit_code = main(
        [
            "browser",
            "screenshot",
            *_HANDLE_FLAGS,
            "--output",
            str(output_path),
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )

    assert not output_path.exists()
    assert exit_code == 1


def test_browser_inspect_dom_subcommand_routes_selector_and_prints_html(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[tuple[PageHandle, str]] = []

    async def fake_authorize_and_query_dom(
        handle: PageHandle,
        selector: str,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[str]]:
        received.append((handle, selector))
        decision = _make_decision(granted=True, capability_id="browser.inspect_dom")
        return decision, Tainted(
            "<h1>Hello</h1>", Provenance.external("t", Classification.SENSITIVE)
        )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_query_dom", fake_authorize_and_query_dom
    )

    exit_code = main(
        [
            "browser",
            "inspect-dom",
            *_HANDLE_FLAGS,
            "--selector",
            "h1",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [(_FAKE_HANDLE, "h1")]
    assert "<h1>Hello</h1>" in captured.out
    assert exit_code == 0


def test_browser_inspect_dom_subcommand_no_match_prints_no_html(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A granted query with no matching element returns None, not a crash or fake content."""

    async def fake_authorize_and_query_dom(
        handle: PageHandle,  # noqa: ARG001
        selector: str,  # noqa: ARG001
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> tuple[Decision, Tainted[str] | None]:
        decision = _make_decision(granted=True, capability_id="browser.inspect_dom")
        return decision, None

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_query_dom", fake_authorize_and_query_dom
    )

    exit_code = main(
        [
            "browser",
            "inspect-dom",
            *_HANDLE_FLAGS,
            "--selector",
            "h1",
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert "browser inspect-dom: GRANTED" in captured.out
    assert captured.out.strip() == (
        "browser inspect-dom: GRANTED (tier=CONFIRM, reasons=DecisionReason.BASE_TIER)"
    )
    assert exit_code == 0


def test_browser_inspect_dom_subcommand_requires_selector(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "browser",
                "inspect-dom",
                *_HANDLE_FLAGS,
                "--chain-path",
                str(tmp_path / "audit_chain.json"),
            ]
        )


def test_browser_close_subcommand_routes_reconstructed_handle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    received: list[PageHandle] = []

    async def fake_authorize_and_close_page(
        handle: PageHandle,
        *,
        physical_confirmation_available: bool,  # noqa: ARG001
        remote_confirmation_available: bool,  # noqa: ARG001
        chain_path: Path,  # noqa: ARG001
    ) -> Decision:
        received.append(handle)
        return _make_decision(granted=True, capability_id="browser.close_page")

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"], "authorize_and_close_page", fake_authorize_and_close_page
    )

    exit_code = main(
        [
            "browser",
            "close",
            *_HANDLE_FLAGS,
            "--physical-confirmation-available",
            "--chain-path",
            str(tmp_path / "audit_chain.json"),
        ]
    )
    captured = capsys.readouterr()

    assert received == [_FAKE_HANDLE]
    assert "browser close: GRANTED" in captured.out
    assert exit_code == 0


def test_browser_close_subcommand_requires_all_handle_flags(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "browser",
                "close",
                "--debug-port",
                "9222",
                "--chain-path",
                str(tmp_path / "audit_chain.json"),
            ]
        )


def test_browser_subcommand_requires_a_browser_command() -> None:
    with pytest.raises(SystemExit):
        main(["browser"])


_TOP_LEVEL_COMMANDS = (
    "send-email",
    "create-calendar-event",
    "code",
    "draft",
    "list-dir",
    "move-file",
    "delete-file",
    "open-brave-url",
    "job-search",
    "find-careers-page",
    "prepare-application",
    "open-vscode-file",
    "send-claude-text",
    "send-chatgpt-text",
    "list-docker-containers",
    "stop-docker-container",
    "git-status",
    "git-create-branch",
    "git-commit",
    "git-push",
    "git-force-push",
    "ping",
    "audit-history",
    "doctor",
    "play",
    "pause",
    "next",
    "previous",
    "read",
    "listen",
)
_MEMORY_SUBCOMMANDS = ("write", "retrieve", "forget", "pin", "backup", "restore", "wipe")
_PLANNING_SUBCOMMANDS = ("run",)
_EMAIL_SUBCOMMANDS = ("list", "read")
_CALENDAR_SUBCOMMANDS = ("list-events",)
_JOB_APPLICATION_SUBCOMMANDS = ("record", "list")
_BROWSER_SUBCOMMANDS = ("open", "screenshot", "inspect-dom", "close")
_FS_SUBCOMMANDS = ("find", "search-content", "recent")
_PROJECT_SUBCOMMANDS = ("start", "status")
_TASK_SUBCOMMANDS = ("create", "run", "status", "list")


def test_no_help_text_leaks_an_internal_adr_or_wp_reference(  # noqa: PLR0915
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Real regression guard (Phase 8, CLI UX audit): --help is for real users, not reviewers.

    Found and fixed three real instances of this (memory backup's own
    ADR-0061 reference, send-email/create-calendar-event's shared
    ADR-0017/ADR-0042 reference) -- this test mechanically prevents a
    future help string from reintroducing the same class of leak,
    across every real top-level and memory subcommand's own --help.
    """
    for command in _TOP_LEVEL_COMMANDS:
        with pytest.raises(SystemExit):
            main([command, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"{command} --help leaks an ADR reference"
        assert "WP-" not in captured.out, f"{command} --help leaks a work-package reference"

    for subcommand in _MEMORY_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["memory", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"memory {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, (
            f"memory {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _PLANNING_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["plan", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"plan {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, f"plan {subcommand} --help leaks a work-package reference"

    for subcommand in _EMAIL_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["email", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"email {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, (
            f"email {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _CALENDAR_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["calendar", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"calendar {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, (
            f"calendar {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _JOB_APPLICATION_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["job-application", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, (
            f"job-application {subcommand} --help leaks an ADR reference"
        )
        assert "WP-" not in captured.out, (
            f"job-application {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _BROWSER_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["browser", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"browser {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, (
            f"browser {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _FS_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["fs", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"fs {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, f"fs {subcommand} --help leaks a work-package reference"

    for subcommand in _PROJECT_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["project", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"project {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, (
            f"project {subcommand} --help leaks a work-package reference"
        )

    for subcommand in _TASK_SUBCOMMANDS:
        with pytest.raises(SystemExit):
            main(["task", subcommand, "--help"])
        captured = capsys.readouterr()
        assert "ADR-" not in captured.out, f"task {subcommand} --help leaks an ADR reference"
        assert "WP-" not in captured.out, f"task {subcommand} --help leaks a work-package reference"


def test_doctor_subcommand_always_returns_zero_and_prints_real_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real, unmocked run against this real machine's own environment."""
    exit_code = main(["doctor"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Python version" in captured.out
    assert "Ollama" in captured.out
    assert "libportaudio" in captured.out


def test_doctor_subcommand_does_not_accept_chain_path_or_confirmation_flags() -> None:
    """Real, structural proof: doctor is not a capability -- it shares none of the common flags."""
    with pytest.raises(SystemExit):
        main(["doctor", "--chain-path", "/tmp/audit_chain.json"])


def test_doctor_subcommand_never_creates_an_audit_chain_file(tmp_path: Path) -> None:
    """A real, empirical proof doctor never touches the audit chain -- no file appears."""
    monkeypatch_cwd = tmp_path
    original_cwd = Path.cwd()
    os.chdir(monkeypatch_cwd)
    try:
        main(["doctor"])
        assert not (monkeypatch_cwd / "audit_chain.json").exists()
    finally:
        os.chdir(original_cwd)


def test_check_binary_reports_missing_for_a_real_nonexistent_binary() -> None:
    name, ok, detail = _check_binary("definitely-not-a-real-binary-xyz123", why="test")

    assert ok is False
    assert "not found" in detail
    assert "definitely-not-a-real-binary-xyz123" in name


def test_check_binary_reports_found_for_a_real_binary_guaranteed_present() -> None:
    """`python3` (or an equivalent) must exist -- this test process is itself running under it."""
    name, ok, detail = _check_binary("python3", why="test")

    assert ok is True
    assert detail  # a real path was returned
    assert "python3" in name


def test_check_ollama_reachable_reports_unreachable_for_a_real_closed_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(url: str, timeout: float) -> None:  # noqa: ARG001
        raise OSError("Connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    name, ok, detail = _check_ollama_reachable()

    assert ok is False
    assert "not reachable" in detail
    assert "Ollama" in name


def test_version_flag_prints_the_real_installed_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real, unmocked check against this real environment's own installed jarvis package."""
    real_version = importlib.metadata.version("jarvis")

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert real_version in captured.out
