"""The media player port: the seam between an authorized command and a real player.

:class:`MediaPlayerPort` is the one abstract boundary between "some
real, currently-running media player" and the four playback commands
this system can authorize: play, pause, next track, previous track.
Nothing outside an adapter implementing this port knows or cares which
transport or technology actually reaches the player.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.media_player`` for the
concrete MPRIS-over-D-Bus adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class NoMediaPlayerRunningError(Exception):
    """Raised when no media player is currently reachable to run a command against.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass:
    ``JarvisError``'s own docstring scopes itself to "every exception
    raised from within ``jarvis.domain``" -- this is raised from an
    adapter, about a real-world operational condition (no player is
    open right now), not a domain-level security/policy concern.

    Defined on the port rather than the adapter so that any future,
    non-MPRIS implementation of this port raises the same,
    technology-independent type -- a caller should not need to know
    which concrete adapter is behind the port to catch this.
    """


class MediaPlayerCommandFailedError(Exception):
    """Raised when a player was found but rejected or failed the command sent to it.

    Distinct from :class:`NoMediaPlayerRunningError` on purpose: that
    one means discovery found nothing to talk to at all; this one
    means a real player was found and a real command reached it, but
    the player (or the transport's security policy -- e.g. AppArmor
    denying the call) refused it. The two are actionable differently:
    the first says "open a player first," the second says "the
    command itself didn't go through, and here's why." Not a
    ``JarvisError`` subclass for the same reason as
    ``NoMediaPlayerRunningError``.
    """


@runtime_checkable
class MediaPlayerPort(Protocol):
    """A currently-running media player that can be sent playback commands."""

    def play(self) -> None:
        """Resume playback.

        Raises:
            NoMediaPlayerRunningError: If no player is currently reachable.
            MediaPlayerCommandFailedError: If a player was found but
                rejected the command.
        """
        ...

    def pause(self) -> None:
        """Pause playback.

        Raises:
            NoMediaPlayerRunningError: If no player is currently reachable.
            MediaPlayerCommandFailedError: If a player was found but
                rejected the command.
        """
        ...

    def next_track(self) -> None:
        """Skip to the next track.

        Raises:
            NoMediaPlayerRunningError: If no player is currently reachable.
            MediaPlayerCommandFailedError: If a player was found but
                rejected the command.
        """
        ...

    def previous_track(self) -> None:
        """Go back to the previous track.

        Raises:
            NoMediaPlayerRunningError: If no player is currently reachable.
            MediaPlayerCommandFailedError: If a player was found but
                rejected the command.
        """
        ...
