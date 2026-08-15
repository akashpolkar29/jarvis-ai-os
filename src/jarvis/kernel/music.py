"""The composition root for the music.* capability family: real playback control.

:func:`authorize_and_run_music_command` extends the composition-root
pattern :func:`~jarvis.kernel.ping.authorize_ping` established: it
wires the same registry (built by
:func:`~jarvis.kernel.capabilities.build_default_registry`)/storage/
confirmation/orchestrator pieces together, plus a
:class:`~jarvis.ports.media_player.MediaPlayerPort`, and is the first
kernel function whose authorization decision gates a real, observable
side effect rather than a no-op.

Effect and tier: all four capabilities (``music.play``, ``music.pause``,
``music.next``, ``music.previous``) are registered with
``Effect.WRITE_LOCAL``, landing at ``Tier.CONFIRM``. Sending an MPRIS
command mutates a running process's playback state -- it is not a
read -- so ``READ_LOCAL`` (the tier ``ping`` correctly uses for its
true no-op) would not honestly describe it. ``CONFIRM`` requires
either ``physical_confirmation_available`` or
``remote_confirmation_available`` to be true; a real state-changing
capability granted unconditionally by default would make the tiered
policy engine pointless for the first capability that actually does
something.

Enforcement ordering is the entire point of this module:
``orchestrator.authorize_by_id()`` always runs first, and the media
player is only ever touched inside ``if decision.granted:`` --  an
unauthorized command never reaches ``media_player`` at all. This is
the single choke point (ADR-0005) actually gating a real side effect
for the first time.

Audit-save guarantee: the "run it if granted" step is wrapped in
``try``/``finally`` so ``storage.save(chain)`` always runs, even if
the media player raises (e.g.
:class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`).
Without this, a granted decision -- already appended to the in-memory
chain by ``authorize_by_id()`` per WP-06's guarantee -- would be lost
from disk if the subsequent real-world action failed, silently
breaking "every decision, granted or denied, no exceptions" at the
persistence boundary.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.media_player import MprisMediaPlayerAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    MUSIC_NEXT_CAPABILITY_ID,
    MUSIC_PAUSE_CAPABILITY_ID,
    MUSIC_PLAY_CAPABILITY_ID,
    MUSIC_PREVIOUS_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.policy import Decision
    from jarvis.ports.media_player import MediaPlayerPort


class MusicCommand(Enum):
    """One of the four MPRIS playback commands this module can authorize and run."""

    PLAY = auto()
    PAUSE = auto()
    NEXT = auto()
    PREVIOUS = auto()


MUSIC_COMMAND_NAMES: dict[str, MusicCommand] = {
    "play": MusicCommand.PLAY,
    "pause": MusicCommand.PAUSE,
    "next": MusicCommand.NEXT,
    "previous": MusicCommand.PREVIOUS,
}
"""The one place a command-name string maps to a MusicCommand -- shared by
``jarvis.cli.main`` (argparse subcommand dispatch) and
``jarvis.kernel.intent`` (voice intent resolution, WP-25), per ADR-0033's
sibling design note: neither module keeps its own separate copy of this
mapping, so a command added or renamed here cannot silently drift out of
sync with the other. C1 layering is why this lives here rather than in
``cli.main``: ``cli`` may import ``kernel``, never the reverse, so
``kernel.intent`` (which needs this mapping) could not have reached a
copy kept in ``cli.main``.
"""

MUSIC_CAPABILITY_IDS: dict[MusicCommand, CapabilityId] = {
    MusicCommand.PLAY: MUSIC_PLAY_CAPABILITY_ID,
    MusicCommand.PAUSE: MUSIC_PAUSE_CAPABILITY_ID,
    MusicCommand.NEXT: MUSIC_NEXT_CAPABILITY_ID,
    MusicCommand.PREVIOUS: MUSIC_PREVIOUS_CAPABILITY_ID,
}
"""Maps this module's own dispatch enum to the ids build_default_registry() registers.

The ids themselves are declared once in ``kernel.capabilities`` -- this
dict is purely a local dispatch concern (which enum member means which
id), not a second source of truth for what the ids are. Public (not
``_``-prefixed) since WP-25's ``kernel.intent``/``kernel.voice_loop``
also need this exact association -- one direction to go from a
resolved ``MusicCommand`` to the ``CapabilityId`` to authorize, the
other to go from an authorized capability back to which
``MusicCommand`` to actually run -- rather than each keeping its own
copy.
"""


def _run(media_player: MediaPlayerPort, command: MusicCommand) -> None:
    """Actually send the MPRIS command -- only ever called after a granted Decision."""
    if command is MusicCommand.PLAY:
        media_player.play()
    elif command is MusicCommand.PAUSE:
        media_player.pause()
    elif command is MusicCommand.NEXT:
        media_player.next_track()
    elif command is MusicCommand.PREVIOUS:
        media_player.previous_track()
    else:  # pragma: no cover
        msg = f"Unhandled MusicCommand: {command!r}"  # type: ignore[unreachable]
        raise AssertionError(msg)


def authorize_and_run_music_command(
    command: MusicCommand,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    media_player: MediaPlayerPort | None = None,
) -> Decision:
    """Wire up the stack, authorize ``command``, and run it only if granted.

    Args:
        command: Which of the four playback commands to authorize and run.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        media_player: The port ``command`` is sent to if granted.
            Defaults to a real ``MprisMediaPlayerAdapter`` talking to
            the session bus. Overridable for tests, exactly as
            ``AuthorizationOrchestrator``'s confirmation port is (WP-11).

    Returns:
        The ``Decision`` for this command -- durably appended to the
        chain regardless of outcome. If granted, ``media_player`` has
        already received the command by the time this returns
        (barring an exception it raised); if denied, it was never
        touched at all.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        MUSIC_CAPABILITY_IDS[command],
        Tainted({}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            player = media_player if media_player is not None else MprisMediaPlayerAdapter()
            _run(player, command)
    finally:
        storage.save(chain)

    return decision
