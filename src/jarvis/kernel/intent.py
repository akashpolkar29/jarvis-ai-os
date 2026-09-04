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

"code" (overnight Track 4 pass) mirrors the identical "keyword + rest
of text" shape once more: everything after the keyword becomes the
coding task's own description -- resolved to
``kernel.capabilities.CODING_RUN_TASK_CAPABILITY_ID``, another real,
already-registered static capability (M5, WP-72), the same shape
``memory.retrieve`` takes. **A real, deliberate departure from
``browser.*``/``memory.pin``/``memory.forget``'s own established "stay
kernel-level only" precedent** (`docs/threat-model/v0.md`'s own
"Milestone 5 additions"), made here because this pass was explicitly
asked to add it, unlike those capabilities' own real gaps, where no
one asked. The resolved intent carries only the task text -- which
real target repository a "code" command runs against, and which real
``ReasoningPort`` providers service it, are not something a single
voice phrase can safely express; see ``kernel/voice_loop.py``'s own
module docstring for how those get supplied.

"send email"/"create event" (overnight Track 3 pass) are this
module's first *two-word* command keywords -- every prior command
matches on its first word alone, but "send" and "create" alone are
too generic to commit to a single meaning ahead of a real M6b
"drafting" command or similar future addition, so both are matched as
fixed two-word prefixes first, in :func:`_resolve_two_word_command`,
before the single-word dispatch runs at all (see
:func:`resolve_intent`). Both resolve to
``jarvis.application.communications.writer``'s own
``EMAIL_SEND_CAPABILITY_ID``/``CALENDAR_CREATE_EVENT_CAPABILITY_ID`` --
not a ``kernel.capabilities`` id, mirroring "remember"'s own
dynamic-effect precedent exactly (neither is registered in
``build_default_registry()``; see ``kernel/communications.py``'s own
module docstring for why). Unlike every single-argument command
before them, a real email needs three distinct pieces of content
(recipients/subject/body) and a real calendar event needs three or
four (summary/start/end/optional attendees) that one verbatim string
cannot safely separate, so both introduce a small, real, fixed
keyword grammar (" subject "/" body " for email; " from "/" to "/
" with " for the event) -- see :func:`_resolve_send_email`/
:func:`_resolve_create_event` for the exact parsing and their own
real, named limitation (event start/end times are matched verbatim,
not parsed from natural spoken language like "tomorrow at 3"; a
caller must speak or otherwise supply an exact ISO-8601 string).
**Voice does not bypass ADR-0059 in any way**: both resolved
capabilities still route through
``authorize_and_send_email``/``authorize_and_create_calendar_event``
unmodified, the same ``Tier.MANUAL_ONLY`` floor (for email always;
for calendar, whenever attendees are present) that denies whenever
``physical_confirmation_available`` is ``False``, regardless of the
voice loop's own confirmation prompt answer -- proven by a real test
in ``tests/unit/test_voice_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.application.communications.writer import (
    CALENDAR_CREATE_EVENT_CAPABILITY_ID,
    EMAIL_SEND_CAPABILITY_ID,
)
from jarvis.application.memory.writer import MEMORY_WRITE_CAPABILITY_ID
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    CODING_RUN_TASK_CAPABILITY_ID,
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


def _resolve_code(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve the "code" command: everything after the keyword is the coding task's description."""
    if not rest:
        return _UNRECOGNIZED
    return ResolvedIntent(
        capability_id=CODING_RUN_TASK_CAPABILITY_ID,
        arguments=Tainted({"task": rest}, Provenance.user()),
    )


def _split_recipients(text: str) -> tuple[str, ...]:
    """Split a spoken recipient list on "," or " and ", trimming each address."""
    normalized = text.replace(" and ", ",")
    return tuple(part.strip() for part in normalized.split(",") if part.strip())


def _resolve_send_email(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve "send email to <recipients> subject <subject> body <body>".

    A minimal, real keyword grammar -- mirrors "read"/"remember"'s own
    "everything after the keyword is the argument" shape, extended
    with two more fixed keywords (" subject "/" body ") since a real
    email needs three distinct pieces of content a single verbatim
    string cannot safely separate. Matches ``_resolve_create_event``'s
    identical approach for calendar events.
    """
    lowered = rest.lower()
    if not lowered.startswith("to "):
        return _UNRECOGNIZED
    subject_index = lowered.find(" subject ")
    body_index = lowered.find(" body ")
    if subject_index == -1 or body_index == -1 or body_index <= subject_index:
        return _UNRECOGNIZED

    to_text = rest[len("to ") : subject_index].strip()
    subject_text = rest[subject_index + len(" subject ") : body_index].strip()
    body_text = rest[body_index + len(" body ") :].strip()
    recipients = _split_recipients(to_text)
    if not recipients or not subject_text or not body_text:
        return _UNRECOGNIZED

    return ResolvedIntent(
        capability_id=EMAIL_SEND_CAPABILITY_ID,
        arguments=Tainted(
            {"to": recipients, "subject": subject_text, "body": body_text}, Provenance.user()
        ),
    )


def _resolve_create_event(rest: str) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve "create event <summary> from <start> to <end> [with <attendees>]".

    ``start``/``end`` are matched verbatim, unparsed -- see the module
    docstring's own real, honest limitation: a spoken utterance is
    unlikely to ever produce a literal ISO-8601 timestamp on its own,
    so this grammar exists for a real caller who speaks (or a future
    upstream normalization step produces) exact times, not as a claim
    that natural spoken dates ("tomorrow at 3") resolve today. The
    trailing ``with <attendees>`` clause is optional -- its presence is
    what makes ``authorize_and_create_calendar_event`` float to
    ``Tier.MANUAL_ONLY`` at all (ADR-0059); an event with no attendees
    still floors at the ordinary ``Tier.CONFIRM``.
    """
    lowered = rest.lower()
    from_index = lowered.find(" from ")
    if from_index == -1:
        return _UNRECOGNIZED
    summary_text = rest[:from_index].strip()
    after_from = rest[from_index + len(" from ") :]
    lowered_after_from = after_from.lower()

    to_index = lowered_after_from.find(" to ")
    if to_index == -1:
        return _UNRECOGNIZED
    start_text = after_from[:to_index].strip()
    after_to = after_from[to_index + len(" to ") :]
    lowered_after_to = after_to.lower()

    with_index = lowered_after_to.find(" with ")
    if with_index == -1:
        end_text = after_to.strip()
        attendees: tuple[str, ...] = ()
    else:
        end_text = after_to[:with_index].strip()
        attendees = _split_recipients(after_to[with_index + len(" with ") :].strip())

    if not summary_text or not start_text or not end_text:
        return _UNRECOGNIZED

    return ResolvedIntent(
        capability_id=CALENDAR_CREATE_EVENT_CAPABILITY_ID,
        arguments=Tainted(
            {"summary": summary_text, "start": start_text, "end": end_text, "attendees": attendees},
            Provenance.user(),
        ),
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


def _split_two_word_command(text: str, command: str) -> str | None:
    """If ``text`` starts with the two-word ``command`` (case-insensitive), return the rest.

    Returns ``None`` if ``text`` doesn't start with ``command`` at all
    -- distinct from returning ``""``, which means the command matched
    with no arguments following it (itself unrecognized for these two,
    both of which require real content; see their own resolvers).
    """
    lowered = text.lower()
    if lowered == command:
        return ""
    prefix = command + " "
    if lowered.startswith(prefix):
        return text[len(prefix) :].strip()
    return None


def _resolve_two_word_command(text: str) -> ResolvedIntent | UnrecognizedIntent | None:
    """Try "send email"/"create event" -- the only two-word command keywords this module has.

    Returns ``None`` (not ``UnrecognizedIntent``) when neither
    two-word prefix matches at all, so :func:`resolve_intent` falls
    through to its existing single-word dispatch.
    """
    rest = _split_two_word_command(text, "send email")
    if rest is not None:
        return _resolve_send_email(rest)
    rest = _split_two_word_command(text, "create event")
    if rest is not None:
        return _resolve_create_event(rest)
    return None


def resolve_intent(  # noqa: PLR0911 -- one return per command keyword, mirrors the module's flat dispatch shape
    transcript: Transcript,
) -> ResolvedIntent | UnrecognizedIntent:
    """Resolve ``transcript``'s text to a known command, or ``UnrecognizedIntent`` if none matches.

    Matching is case-insensitive (on the command word(s) only) and
    whitespace-trimmed. "send email"/"create event" are matched as a
    fixed two-word prefix first (see :func:`_resolve_two_word_command`);
    every other command matches on its first word alone. For every
    single-word command except "read"/"remember"/"recall"/"code", any
    remaining text makes the match fail (a zero-argument command does
    not silently ignore trailing words) rather than resolving anyway.
    """
    text = transcript.text.strip()
    if not text:
        return _UNRECOGNIZED

    two_word_result = _resolve_two_word_command(text)
    if two_word_result is not None:
        return two_word_result

    words = text.split(maxsplit=1)
    command = words[0].lower()
    rest = words[1].strip() if len(words) > 1 else ""

    if command == "read":
        return _resolve_read(rest)
    if command == "remember":
        return _resolve_remember(rest)
    if command == "recall":
        return _resolve_recall(rest)
    if command == "code":
        return _resolve_code(rest)
    if rest:
        return _UNRECOGNIZED
    return _resolve_zero_argument_command(command)
