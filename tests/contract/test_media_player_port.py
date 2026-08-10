"""Contract test: adapters must structurally satisfy jarvis.ports.media_player.MediaPlayerPort."""

from __future__ import annotations

from jarvis.adapters.media_player import MprisMediaPlayerAdapter
from jarvis.ports.media_player import MediaPlayerPort


def test_mpris_media_player_adapter_satisfies_media_player_port() -> None:
    """MprisMediaPlayerAdapter is structurally a MediaPlayerPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no D-Bus connection.
    """
    adapter = MprisMediaPlayerAdapter()

    assert isinstance(adapter, MediaPlayerPort)


def test_an_object_missing_the_four_methods_does_not_satisfy_media_player_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAMediaPlayerSource:
        """Deliberately lacks play()/pause()/next_track()/previous_track()."""

    assert isinstance(NotAMediaPlayerSource(), MediaPlayerPort) is False
