"""Unit tests for jarvis.kernel.music.authorize_and_run_music_command.

What's mocked and why: a small stub MediaPlayerPort (with call
tracking) is injected in place of a real MprisMediaPlayerAdapter, for
the same reason WP-11 injected a stub ConfirmationPort -- these tests
must be hermetic and not depend on a live D-Bus session bus or a real
media player being open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.music import MusicCommand, authorize_and_run_music_command
from jarvis.ports.media_player import NoMediaPlayerRunningError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1
_TWO_INVOCATIONS = 2


class _StubMediaPlayer:
    """A MediaPlayerPort test double that records which methods were called, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        """Start with an empty call log; optionally raise NoMediaPlayerRunningError on any call."""
        self.calls: list[str] = []
        self._raise_on_call = raise_on_call

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if self._raise_on_call:
            msg = "No MPRIS media player is currently running on the session bus."
            raise NoMediaPlayerRunningError(msg)

    def play(self) -> None:
        """Record a play() call."""
        self._record("play")

    def pause(self) -> None:
        """Record a pause() call."""
        self._record("pause")

    def next_track(self) -> None:
        """Record a next_track() call."""
        self._record("next_track")

    def previous_track(self) -> None:
        """Record a previous_track() call."""
        self._record("previous_track")


@pytest.mark.parametrize(
    ("command", "expected_method"),
    [
        (MusicCommand.PLAY, "play"),
        (MusicCommand.PAUSE, "pause"),
        (MusicCommand.NEXT, "next_track"),
        (MusicCommand.PREVIOUS, "previous_track"),
    ],
)
def test_granted_command_invokes_the_matching_media_player_method(
    tmp_path: Path, command: MusicCommand, expected_method: str
) -> None:
    """A granted command (confirmation flag set) calls exactly the matching port method."""
    player = _StubMediaPlayer()

    decision = authorize_and_run_music_command(
        command,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        media_player=player,
    )

    assert decision.granted is True
    assert player.calls == [expected_method]


def test_denied_command_never_touches_the_media_player(tmp_path: Path) -> None:
    """With no confirmation flags, CONFIRM-tier music.pause is denied and the port untouched.

    This is the enforcement-ordering guarantee the whole module exists
    to prove: authorization happens before any real side effect.
    """
    player = _StubMediaPlayer()

    decision = authorize_and_run_music_command(
        MusicCommand.PAUSE,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        media_player=player,
    )

    assert decision.granted is False
    assert player.calls == []


def test_remote_confirmation_alone_is_sufficient_to_grant(tmp_path: Path) -> None:
    """CONFIRM tier grants on physical OR remote confirmation -- remote alone is enough."""
    player = _StubMediaPlayer()

    decision = authorize_and_run_music_command(
        MusicCommand.NEXT,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        media_player=player,
    )

    assert decision.granted is True
    assert player.calls == ["next_track"]


def test_a_single_granted_call_appends_one_verifiable_record(tmp_path: Path) -> None:
    """One authorize_and_run_music_command() call persists exactly one record that verifies."""
    chain_path = tmp_path / "audit_chain.json"

    authorize_and_run_music_command(
        MusicCommand.PLAY,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        media_player=_StubMediaPlayer(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain.verify().valid is True


def test_state_persists_across_separate_calls_against_the_same_path(tmp_path: Path) -> None:
    """Two calls against the same path grow the chain, mirroring two separate CLI invocations."""
    chain_path = tmp_path / "audit_chain.json"

    authorize_and_run_music_command(
        MusicCommand.PLAY,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        media_player=_StubMediaPlayer(),
    )
    authorize_and_run_music_command(
        MusicCommand.PAUSE,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        media_player=_StubMediaPlayer(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _TWO_INVOCATIONS
    assert chain.verify().valid is True


def test_audit_record_is_saved_even_when_the_media_player_raises(tmp_path: Path) -> None:
    """A granted decision is persisted even if the subsequent real-world action fails.

    This is the try/finally audit-save guarantee: without it, a
    NoMediaPlayerRunningError raised after authorize_by_id() already
    appended the record in-memory would cause storage.save() to be
    skipped, silently losing that record from disk.
    """
    chain_path = tmp_path / "audit_chain.json"
    player = _StubMediaPlayer(raise_on_call=True)

    with pytest.raises(NoMediaPlayerRunningError):
        authorize_and_run_music_command(
            MusicCommand.PAUSE,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            media_player=player,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True
