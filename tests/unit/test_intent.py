"""Unit tests for jarvis.kernel.intent.resolve_intent."""

from __future__ import annotations

from jarvis.application.communications.writer import (
    CALENDAR_CREATE_EVENT_CAPABILITY_ID,
    EMAIL_SEND_CAPABILITY_ID,
)
from jarvis.application.memory.writer import MEMORY_WRITE_CAPABILITY_ID
from jarvis.domain.transcript import Transcript
from jarvis.kernel.capabilities import (
    CODING_RUN_TASK_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    MUSIC_NEXT_CAPABILITY_ID,
    MUSIC_PAUSE_CAPABILITY_ID,
    MUSIC_PLAY_CAPABILITY_ID,
    MUSIC_PREVIOUS_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
)
from jarvis.kernel.intent import ResolvedIntent, UnrecognizedIntent, resolve_intent


def test_ping_resolves_to_the_ping_capability_with_no_arguments() -> None:
    """The bare word "ping" resolves cleanly."""
    result = resolve_intent(Transcript(text="ping"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == PING_CAPABILITY_ID
    assert result.arguments.value == {}


def test_ping_matching_is_case_insensitive() -> None:
    """Command matching does not depend on exact casing."""
    result = resolve_intent(Transcript(text="PING"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == PING_CAPABILITY_ID


def test_surrounding_whitespace_is_ignored() -> None:
    """Leading/trailing whitespace around the whole transcript does not prevent a match."""
    result = resolve_intent(Transcript(text="  ping  "))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == PING_CAPABILITY_ID


def test_play_resolves_to_the_music_play_capability() -> None:
    """ "play" resolves to music.play."""
    result = resolve_intent(Transcript(text="play"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MUSIC_PLAY_CAPABILITY_ID


def test_pause_resolves_to_the_music_pause_capability() -> None:
    """ "pause" resolves to music.pause."""
    result = resolve_intent(Transcript(text="pause"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MUSIC_PAUSE_CAPABILITY_ID


def test_next_resolves_to_the_music_next_capability() -> None:
    """ "next" resolves to music.next."""
    result = resolve_intent(Transcript(text="next"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MUSIC_NEXT_CAPABILITY_ID


def test_previous_resolves_to_the_music_previous_capability() -> None:
    """ "previous" resolves to music.previous."""
    result = resolve_intent(Transcript(text="previous"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MUSIC_PREVIOUS_CAPABILITY_ID


def test_read_with_a_path_resolves_with_the_rest_of_the_text_as_the_path_argument() -> None:
    """ "read <path>" resolves to fs.read_file with the trailing text as the path argument."""
    result = resolve_intent(Transcript(text="read notes.txt"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == READ_FILE_CAPABILITY_ID
    assert result.arguments.value == {"path": "notes.txt"}


def test_read_preserves_the_full_rest_of_the_text_including_spaces() -> None:
    """A multi-word path/phrase after "read" is kept whole, not just the next single word."""
    result = resolve_intent(Transcript(text="read my notes file.txt"))

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value == {"path": "my notes file.txt"}


def test_read_with_no_path_is_unrecognized() -> None:
    """ "read" alone, with nothing after it, is not a valid request -- never a guessed path."""
    result = resolve_intent(Transcript(text="read"))

    assert isinstance(result, UnrecognizedIntent)


def test_remember_with_text_resolves_with_the_rest_of_the_text_as_the_text_argument() -> None:
    """ "remember <text>" resolves to memory.write with the trailing text as the argument."""
    result = resolve_intent(Transcript(text="remember I prefer tabs"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MEMORY_WRITE_CAPABILITY_ID
    assert result.arguments.value == {"text": "I prefer tabs"}


def test_remember_preserves_the_full_rest_of_the_text_including_spaces() -> None:
    """A multi-word phrase after "remember" is kept whole, not just the next single word."""
    result = resolve_intent(Transcript(text="remember my favorite color is blue"))

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value == {"text": "my favorite color is blue"}


def test_remember_with_no_text_is_unrecognized() -> None:
    """ "remember" alone, with nothing after it, is not a valid request -- never a guessed value."""
    result = resolve_intent(Transcript(text="remember"))

    assert isinstance(result, UnrecognizedIntent)


def test_recall_with_query_resolves_to_memory_retrieve_with_the_query_argument() -> None:
    """ "recall <query>" resolves to memory.retrieve with the trailing text as the query."""
    result = resolve_intent(Transcript(text="recall my favorite editor"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MEMORY_RETRIEVE_CAPABILITY_ID
    assert result.arguments.value == {"query": "my favorite editor"}


def test_recall_preserves_the_full_rest_of_the_text_including_spaces() -> None:
    """A multi-word phrase after "recall" is kept whole, not just the next single word."""
    result = resolve_intent(Transcript(text="recall what I said about tabs versus spaces"))

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value == {"query": "what I said about tabs versus spaces"}


def test_recall_with_no_query_is_unrecognized() -> None:
    """ "recall" alone, with nothing after it, is not a valid request -- never a guessed value."""
    result = resolve_intent(Transcript(text="recall"))

    assert isinstance(result, UnrecognizedIntent)


def test_recall_matching_is_case_insensitive() -> None:
    """Command matching does not depend on exact casing, mirroring every other command."""
    result = resolve_intent(Transcript(text="RECALL my favorite editor"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == MEMORY_RETRIEVE_CAPABILITY_ID


def test_code_with_task_resolves_to_coding_run_task_with_the_task_argument() -> None:
    """ "code <task>" resolves to coding.run_task with the trailing text as the task."""
    result = resolve_intent(Transcript(text="code add a docstring to main.py"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == CODING_RUN_TASK_CAPABILITY_ID
    assert result.arguments.value == {"task": "add a docstring to main.py"}


def test_code_preserves_the_full_rest_of_the_text_including_spaces() -> None:
    """A multi-word phrase after "code" is kept whole, not just the next single word."""
    result = resolve_intent(Transcript(text="code fix the failing test in test_foo.py"))

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value == {"task": "fix the failing test in test_foo.py"}


def test_code_with_no_task_is_unrecognized() -> None:
    """ "code" alone, with nothing after it, is not a valid request -- never a guessed value."""
    result = resolve_intent(Transcript(text="code"))

    assert isinstance(result, UnrecognizedIntent)


def test_code_matching_is_case_insensitive() -> None:
    """Command matching does not depend on exact casing, mirroring every other command."""
    result = resolve_intent(Transcript(text="CODE add a docstring to main.py"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == CODING_RUN_TASK_CAPABILITY_ID


def test_send_email_resolves_with_to_subject_and_body_arguments() -> None:
    """ "send email to <addr> subject <s> body <b>" resolves to communications.send_email."""
    result = resolve_intent(
        Transcript(text="send email to alice@example.com subject Hello body See you soon")
    )

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == EMAIL_SEND_CAPABILITY_ID
    assert result.arguments.value == {
        "to": ("alice@example.com",),
        "subject": "Hello",
        "body": "See you soon",
    }


def test_send_email_splits_multiple_recipients_on_comma_and_and() -> None:
    """Multiple recipients, separated by "," or " and ", each become a real, distinct address."""
    result = resolve_intent(
        Transcript(
            text="send email to alice@example.com, bob@example.com and carol@example.com "
            "subject Team update body We shipped it"
        )
    )

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value["to"] == (
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
    )


def test_send_email_matching_is_case_insensitive() -> None:
    """Command matching does not depend on exact casing, mirroring every other command."""
    result = resolve_intent(Transcript(text="SEND EMAIL to alice@example.com subject Hi body Hey"))

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == EMAIL_SEND_CAPABILITY_ID


def test_send_email_missing_the_body_keyword_is_unrecognized() -> None:
    """Without a real " body " keyword, this is not a valid request -- never a guessed value."""
    result = resolve_intent(Transcript(text="send email to alice@example.com subject Hello"))

    assert isinstance(result, UnrecognizedIntent)


def test_send_email_missing_the_subject_keyword_is_unrecognized() -> None:
    """Without a real " subject " keyword, this is not a valid request."""
    result = resolve_intent(Transcript(text="send email to alice@example.com body Hi there"))

    assert isinstance(result, UnrecognizedIntent)


def test_send_email_with_no_recipient_is_unrecognized() -> None:
    """ "send email" with nothing recognizable after it is not a valid request."""
    result = resolve_intent(Transcript(text="send email"))

    assert isinstance(result, UnrecognizedIntent)


def test_create_event_resolves_with_summary_start_and_end_and_no_attendees() -> None:
    """ "create event <summary> from <start> to <end>" resolves with an empty attendees tuple."""
    result = resolve_intent(
        Transcript(text="create event Team sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00")
    )

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == CALENDAR_CREATE_EVENT_CAPABILITY_ID
    assert result.arguments.value == {
        "summary": "Team sync",
        "start": "2026-09-05T10:00:00",
        "end": "2026-09-05T10:30:00",
        "attendees": (),
    }


def test_create_event_with_a_trailing_with_clause_resolves_the_attendees() -> None:
    """A trailing " with <attendees>" clause becomes the real, distinct attendee addresses."""
    result = resolve_intent(
        Transcript(
            text="create event Team sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00 "
            "with alice@example.com and bob@example.com"
        )
    )

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.value["attendees"] == ("alice@example.com", "bob@example.com")


def test_create_event_matching_is_case_insensitive() -> None:
    """Command matching does not depend on exact casing, mirroring every other command."""
    result = resolve_intent(
        Transcript(text="CREATE EVENT Sync from 2026-09-05T10:00:00 to 2026-09-05T10:30:00")
    )

    assert isinstance(result, ResolvedIntent)
    assert result.capability_id == CALENDAR_CREATE_EVENT_CAPABILITY_ID


def test_create_event_missing_the_to_keyword_is_unrecognized() -> None:
    """Without a real " to " keyword separating start from end, this is not a valid request."""
    result = resolve_intent(Transcript(text="create event Team sync from 2026-09-05T10:00:00"))

    assert isinstance(result, UnrecognizedIntent)


def test_create_event_missing_the_from_keyword_is_unrecognized() -> None:
    """Without a real " from " keyword, this is not a valid request."""
    result = resolve_intent(Transcript(text="create event Team sync"))

    assert isinstance(result, UnrecognizedIntent)


def test_create_event_with_no_arguments_is_unrecognized() -> None:
    """ "create event" with nothing recognizable after it is not a valid request."""
    result = resolve_intent(Transcript(text="create event"))

    assert isinstance(result, UnrecognizedIntent)


def test_a_zero_argument_command_with_trailing_words_is_unrecognized() -> None:
    """ "ping now" does not silently resolve to ping -- trailing words are not ignored."""
    result = resolve_intent(Transcript(text="ping now"))

    assert isinstance(result, UnrecognizedIntent)


def test_completely_unknown_text_is_unrecognized() -> None:
    """Text matching no known command resolves to UnrecognizedIntent, never a guess."""
    result = resolve_intent(Transcript(text="what time is it"))

    assert isinstance(result, UnrecognizedIntent)


def test_empty_text_is_unrecognized() -> None:
    """An empty transcript is not a valid request."""
    result = resolve_intent(Transcript(text=""))

    assert isinstance(result, UnrecognizedIntent)


def test_whitespace_only_text_is_unrecognized() -> None:
    """A transcript containing only whitespace is not a valid request."""
    result = resolve_intent(Transcript(text="   "))

    assert isinstance(result, UnrecognizedIntent)


def test_resolved_intent_arguments_are_tainted_as_user_provenance() -> None:
    """A spoken command's arguments carry USER_DIRECT trust, per the M1 doc's own rule."""
    result = resolve_intent(Transcript(text="ping"))

    assert isinstance(result, ResolvedIntent)
    assert result.arguments.provenance.trust.name == "USER_DIRECT"
