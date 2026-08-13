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
import os
import sys
from pathlib import Path

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.cli.main import main
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.files import FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.music import MusicCommand
from jarvis.ports.media_player import NoMediaPlayerRunningError


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
