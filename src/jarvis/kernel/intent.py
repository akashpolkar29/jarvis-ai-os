"""Rule-based intent resolution: mapping recognized text to a capability call.

WP-25 finding, documented for real, not a footnote: the M1 architecture
doc's pipeline (docs/architecture/m1-voice-architecture.md section 2)
names "Intent resolution (M0's existing rule-based resolver...)" as an
existing piece this module just wires in. It does not exist -- M0 never
built any text -> capability mapping; the closest analog is argparse's
own subcommand dispatch in ``jarvis.cli.main``, which only works
because argparse has already done the parsing, and never faces raw
free-form text the way an ``SttPort`` transcript does. This module is
that missing piece, built fresh here, deliberately minimal (fixed
keyword/phrase matching only -- full natural-language understanding is
explicitly M2, not M1). See ADR-0033's sibling design note (this
module's own history) for the full account.

:func:`resolve_intent` never guesses: text that doesn't match one of
the known commands resolves to :class:`UnrecognizedIntent`, explicitly,
never to some "closest" command. Its caller (``kernel.voice_loop``) is
expected to speak that back to the user rather than authorizing
anything, and must never construct a ``PolicyContext`` or reach
``AuthorizationOrchestrator`` for an unrecognized result.

Command identity (which six commands exist, and their ``CapabilityId``)
is sourced from ``kernel.capabilities`` -- already the single place
every capability jarvis knows about is declared, so this module
introduces no second copy of that. The play/pause/next/previous
sub-mapping is sourced from ``kernel.music.MUSIC_COMMAND_NAMES``, which
is shared with ``jarvis.cli.main`` for exactly the same reason (see
that constant's own docstring for the C1-layering note on why it lives
in ``kernel``, not ``cli``).

Remaining, real duplication -- flagged, not hidden: "ping" and "read"
have no equivalent shared structure to draw from. ``jarvis.cli.main``
matches them as bare string literals inside argparse subcommand
construction (``_build_parser()``), not through any dict or list a
second module could import; unifying that would mean restructuring
``cli.main``'s argparse construction beyond what this work package's
scope covers. The literal strings ``"ping"``/``"read"`` each appear in
both modules as a result -- a small, low-risk (single-word, unlikely to
silently drift) duplication, unlike the music family's, which this
module deliberately did not force a shared structure for.

"read" is the one command taking an argument: everything after the
"read" keyword, verbatim and untrimmed of anything but surrounding
whitespace, becomes the candidate path text. This module does no
further path validation or sanitization -- ``jarvis.kernel.files``'s
existing ``PathOutsideAllowedScopeError`` scope check (unchanged by
this work package) is the actual security boundary, exercised
downstream at authorization time exactly as it already is for the
CLI's typed ``read`` argument. A fuzzy, voice-derived path string
reaching that check unvalidated is the intended design, not an
oversight.

"remember" (M4, WP-63) mirrors "read"'s exact shape: everything after
the keyword, verbatim, becomes the text to memorize -- resolved to
``application.memory.writer.MEMORY_WRITE_CAPABILITY_ID``, not a
``kernel.capabilities`` id (see ``kernel/memory.py``'s own module
docstring for why memory.write is deliberately never registered in
``build_default_registry()``). Added specifically because ADR-0053
names the ``kernel/voice_loop.py`` dispatch branch a granted memory
write needs for its own spoken confirmation as real, necessary work
for this work package -- without a real way to resolve to that
capability id, that branch would be unreachable dead code.

"recall" (overnight Track 3 pass) mirrors "remember"'s/"read"'s
identical shape: everything after the keyword, verbatim, becomes the
search query -- resolved to ``kernel.capabilities.MEMORY_RETRIEVE_CAPABILITY_ID``,
a real ``kernel.capabilities`` id this time (unlike "remember"'s
dynamic-effect ``memory.write``, ``memory.retrieve`` is a static,
fixed-effect capability, already registered in
``build_default_registry()`` -- ``kernel/memory.py``'s own module
docstring explains why the two capabilities take different
registration shapes). Closes a real, previously-named gap: this
module's own docstring used to state flatly that "nothing in this
milestone's ADRs names voice-triggered recall as required work" --
true when M4 was built, but the real, named gap it left behind
(`docs/threat-model/v0.md`'s own M4 closeout: "voice-triggered *recall*
was not built") was never actually resolved until this pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.application.memory.writer import MEMORY_WRITE_CAPABILITY_ID
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    MEMORY_RETRIEVE_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
)
from jarvis.kernel.music import MUSIC_CAPABILITY_IDS, MUSIC_COMMAND_NAMES

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.transcript import Transcript

_NO_ARGUMENTS: Tainted[Mapping[str, object]] = Tainted({}, Provenance.user())


@dataclass(frozen=True)
class ResolvedIntent:
    """A transcript successfully matched one of the known commands.

    Attributes:
        capability_id: The capability the caller should authorize.
        arguments: The call's ``Tainted`` arguments, in the same shape
            ``AuthorizationOrchestrator.authorize_by_id()`` expects.
    """

    capability_id: CapabilityId
    arguments: Tainted[Mapping[str, object]]


class UnrecognizedIntent:
    """A transcript matched no known command. Never a guess -- see module docstring."""


_UNRECOGNIZED = UnrecognizedIntent()


def _resolve_read(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve the "read" command: everything after the keyword is the candidate path."""
    if not rest:
        return _UNRECOGNIZED
    return ResolvedIntent(
        capability_id=READ_FILE_CAPABILITY_ID,
        arguments=Tainted({"path": rest}, Provenance.user()),
    )


def _resolve_remember(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve the "remember" command: everything after the keyword is the text to memorize."""
    if not rest:
        return _UNRECOGNIZED
    return ResolvedIntent(
        capability_id=MEMORY_WRITE_CAPABILITY_ID,
        arguments=Tainted({"text": rest}, Provenance.user()),
    )


def _resolve_recall(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve the "recall" command: everything after the keyword is the search query."""
    if not rest:
        return _UNRECOGNIZED
    return ResolvedIntent(
        capability_id=MEMORY_RETRIEVE_CAPABILITY_ID,
        arguments=Tainted({"query": rest}, Provenance.user()),
    )


def _resolve_zero_argument_command(command: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve a zero-argument command: "ping" or one of the four music commands."""
    if command == "ping":
        return ResolvedIntent(capability_id=PING_CAPABILITY_ID, arguments=_NO_ARGUMENTS)

    music_command = MUSIC_COMMAND_NAMES.get(command)
    if music_command is not None:
        return ResolvedIntent(
            capability_id=MUSIC_CAPABILITY_IDS[music_command], arguments=_NO_ARGUMENTS
        )

    return _UNRECOGNIZED


def resolve_intent(transcript: Transcript) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve ``transcript``'s text to a known command, or ``UnrecognizedIntent`` if none matches.

    Matching is case-insensitive (on the command word only) and
    whitespace-trimmed. The first word selects the command; for every
    command except "read"/"remember"/"recall", any remaining text makes
    the match fail (a zero-argument command does not silently ignore
    trailing words) rather than resolving anyway.
    """
    words = transcript.text.strip().split(maxsplit=1)
    if not words:
        return _UNRECOGNIZED

    command = words[0].lower()
    rest = words[1].strip() if len(words) > 1 else ""

    if command == "read":
        return _resolve_read(rest)
    if command == "remember":
        return _resolve_remember(rest)
    if command == "recall":
        return _resolve_recall(rest)
    if rest:
        return _UNRECOGNIZED
    return _resolve_zero_argument_command(command)
