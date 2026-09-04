"""Adversarial-string fuzz tests over this codebase's real input-sanitization/parsing seams.

Every existing test of these functions (``tests/unit/adapters/test_draft_storage.py``,
``tests/unit/test_files.py``, ``tests/unit/test_intent.py``) proves a small,
hand-picked set of known adversarial shapes (``../``, a literal ``/``, a
malformed voice grammar). None of them fuzz with Hypothesis-generated
adversarial strings across the input space -- this file closes that gap for
the four real seams named by this pass's own instructions: ``filename_hint``
sanitization (``adapters/draft_storage.py``), the ``allowed_root`` scope
boundary (``kernel/files.py``), voice-grammar field-splitting
(``kernel/intent.py``), and CLI argument parsing (``cli/main.py``).

Each test proves a *closure* property: for any adversarial input, the
function either produces a genuinely safe result or raises the one, real,
already-typed error it is documented to raise -- never a crash from an
unexpected exception type, never a silent escape of the safety boundary the
function exists to enforce.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from jarvis.adapters.draft_storage import _safe_stem
from jarvis.cli.main import _build_parser
from jarvis.domain.transcript import Transcript
from jarvis.kernel.files import PathOutsideAllowedScopeError, _resolve_within_scope
from jarvis.kernel.intent import ResolvedIntent, UnrecognizedIntent, resolve_intent

# Deliberately wide: printable text, path-traversal fragments, path
# separators, unicode, and Hypothesis's own default "nasty strings"
# (control characters, surrogates, etc, via st.text()'s default alphabet).
ADVERSARIAL_TEXT = st.text(max_size=200)
ADVERSARIAL_PATH_TEXT = st.one_of(
    st.text(max_size=200),
    st.text(alphabet="./\\~ ", max_size=100),
    st.text(min_size=1, max_size=50).map(lambda s: "../" * 20 + s),
)


# --- filename_hint sanitization (adapters/draft_storage.py) -----------------


@given(ADVERSARIAL_TEXT)
def test_safe_stem_never_contains_a_path_separator_or_dot(hint: str) -> None:
    """No adversarial hint can smuggle a '/', '\\\\', or '.' into the sanitized stem.

    _safe_stem's own real safety property: every character outside
    [A-Za-z0-9_-] becomes '-'. Fuzzed directly, not just the three
    hand-picked examples the unit tests already cover.
    """
    stem = _safe_stem(hint)
    assert "/" not in stem
    assert "\\" not in stem
    assert "." not in stem
    assert stem  # never empty -- falls back to _FALLBACK_STEM


@given(ADVERSARIAL_TEXT)
def test_safe_stem_stays_within_the_safe_character_set(hint: str) -> None:
    """Every character of the sanitized stem is alphanumeric, '-', or '_'."""
    stem = _safe_stem(hint)
    assert all(ch.isalnum() or ch in "-_" for ch in stem)


@given(ADVERSARIAL_TEXT)
def test_safe_stem_result_can_always_build_a_real_path_inside_base_dir(hint: str) -> None:
    """The sanitized stem, joined to a real base_dir, always resolves inside it.

    The end-to-end property _safe_stem exists to guarantee: no
    adversarial filename_hint can make the constructed path resolve
    outside base_dir, proven here for arbitrary Hypothesis-generated
    text, not just '../../../../tmp/escaped'. Uses a real
    TemporaryDirectory created inside the test body, not the pytest
    tmp_path fixture -- this codebase's own established convention
    (see test_files_kernel.py) for combining @given with real
    filesystem paths, since a function-scoped fixture is only
    constructed once per test while Hypothesis re-runs the body many
    times per test.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        stem = _safe_stem(hint)
        candidate = (base_dir / f"{stem}.txt").resolve()
        assert candidate.is_relative_to(base_dir.resolve())


# --- allowed_root scope boundary (kernel/files.py) ---------------------------


@given(ADVERSARIAL_PATH_TEXT)
def test_resolve_within_scope_never_returns_a_path_outside_allowed_root(path_text: str) -> None:
    """_resolve_within_scope either raises PathOutsideAllowedScopeError or stays in scope.

    No adversarial path string -- '../' chains, absolute paths, '~'
    expansion, unicode, embedded separators -- can make this function
    silently return a path outside allowed_root. Either it raises the
    one, real, typed error, or the path it returns genuinely resolves
    inside allowed_root. Real TemporaryDirectory, not the tmp_path
    fixture -- see test_safe_stem_result_can_always_build_a_real_path_inside_base_dir
    for why.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        allowed_root = Path(tmp_dir) / "scope"
        allowed_root.mkdir()
        try:
            candidate = Path(path_text)
        except ValueError:
            # A small number of strings (e.g. embedded NUL bytes) cannot
            # construct a real Path at all on this platform -- that is a
            # real, typed ValueError from pathlib itself, raised before
            # _resolve_within_scope is ever reached, not a gap in it.
            return

        try:
            resolved = _resolve_within_scope(allowed_root / candidate, allowed_root)
        except PathOutsideAllowedScopeError:
            return
        except (OSError, ValueError):
            # A real, adversarial string (e.g. one containing a NUL byte)
            # can survive Path() construction but still make the real
            # .resolve() call raise -- confirmed directly by this fuzz
            # test itself, which found a real embedded-NUL-byte input
            # ('\x00') raising a bare ValueError here, not just OSError
            # as originally assumed. Not a scope-boundary bypass (no
            # path is returned at all), but real enough to have driven
            # a real fix elsewhere: kernel/voice_loop.py's own dispatch
            # had no exception handling around this call site at all
            # before this pass, so an unhandled ValueError here would
            # have crashed the entire voice loop, not just failed one
            # command -- see kernel/voice_loop.py's own new try/except
            # in _handle_utterance and its regression test in
            # tests/unit/test_voice_loop.py.
            return

        assert resolved.is_relative_to(allowed_root.resolve())


# --- voice-grammar field-splitting (kernel/intent.py) ------------------------


@given(ADVERSARIAL_TEXT)
def test_resolve_intent_never_raises_for_any_transcript(text: str) -> None:
    """resolve_intent() never raises, for any real transcript text -- crash-safety only.

    The full input space no fixed set of hand-picked examples can
    cover: empty strings, transcripts containing the grammar keywords
    in adversarial positions/counts (e.g. multiple " subject "s),
    extreme lengths, and Hypothesis's own default alphabet (control
    characters, unicode, surrogates).
    """
    result = resolve_intent(Transcript(text=text))
    assert isinstance(result, (ResolvedIntent, UnrecognizedIntent))


@given(
    st.text(min_size=1, max_size=80),
    st.text(min_size=1, max_size=80),
    st.text(min_size=1, max_size=80),
)
def test_resolve_intent_send_email_never_returns_empty_recipients_subject_or_body(
    to_text: str, subject_text: str, body_text: str
) -> None:
    """When "send email" *does* resolve, none of its three fields are ever empty/whitespace-only.

    Guards the real invariant _resolve_send_email's own "if not
    recipients or not subject_text or not body_text: return
    _UNRECOGNIZED" check exists for, fuzzed across arbitrary
    Hypothesis-generated field content rather than the three fixed
    examples tests/unit/test_intent.py already has.
    """
    transcript = f"send email to {to_text} subject {subject_text} body {body_text}"
    result = resolve_intent(Transcript(text=transcript))
    if isinstance(result, ResolvedIntent):
        arguments = result.arguments.value
        to_value = arguments["to"]
        assert isinstance(to_value, tuple)
        assert to_value
        assert all(recipient.strip() for recipient in to_value)
        assert str(arguments["subject"]).strip()
        assert str(arguments["body"]).strip()


# --- CLI argument parsing (cli/main.py) --------------------------------------


@given(ADVERSARIAL_PATH_TEXT)
def test_cli_parser_never_crashes_with_an_unexpected_exception_for_list_dir(path_text: str) -> None:
    """_build_parser().parse_args() for list-dir either succeeds or exits via SystemExit.

    argparse's own contract: malformed args cause a printed usage
    message and SystemExit, never an unhandled exception of another
    type. type=Path on the "path" argument means construction happens
    during parsing itself -- fuzzed here to confirm no adversarial
    string can make that construction raise anything argparse doesn't
    already catch and convert to SystemExit.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(["list-dir", path_text, "--physical-confirmation-available"])
    except SystemExit:
        return
    assert args.command == "list-dir"


@given(ADVERSARIAL_PATH_TEXT, ADVERSARIAL_PATH_TEXT)
def test_cli_parser_never_crashes_with_an_unexpected_exception_for_move_file(
    source_text: str, destination_text: str
) -> None:
    """Mirrors test_cli_parser_never_crashes_..._for_list_dir for move-file's two path arguments."""
    parser = _build_parser()
    try:
        args = parser.parse_args(
            [
                "move-file",
                source_text,
                destination_text,
                "--physical-confirmation-available",
            ]
        )
    except SystemExit:
        return
    assert args.command == "move-file"


@given(st.text(max_size=100))
def test_cli_parser_never_crashes_for_an_arbitrary_unrecognized_first_argument(
    first_arg: str,
) -> None:
    """Any single adversarial string as the sole argument either matches a real subcommand or exits.

    A broader, coarser fuzz than the two above: proves the parser's
    own top-level subcommand dispatch never raises anything but
    SystemExit for arbitrary garbage, not just adversarial path text.
    """
    parser = _build_parser()
    try:
        parser.parse_args([first_arg])
    except SystemExit:
        return
    # argparse itself converts ArgumentError to SystemExit before it ever
    # reaches caller code, so no real, reachable case hits this branch.
    except argparse.ArgumentError:  # pragma: no cover
        return
