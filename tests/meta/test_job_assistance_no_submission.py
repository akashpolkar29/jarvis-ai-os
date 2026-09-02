"""Mechanical enforcement of ADR-0058: M6b has no submission mechanism at all, structurally.

ADR-0058 (Accepted, 2026-09-02, directly by the user): "no auto-apply"
is a structural boundary, not a policy-tier gate -- no `CapabilityId`
for submission exists or will exist without a new ADR explicitly
superseding this one; no port, adapter, or module under M6b's own
package path may call, import, or reference anything capable of
submitting data to an external system. This is that boundary's own
real, mechanical proof, written and proven *before* any real M6b
capability code exists (`docs/architecture/m6b-job-assistance.md`'s
own "Structural meta-test" section specifies exactly what this file
checks) -- mirroring this project's own established discipline (WP-58
before M4's other work, WP-70 before WP-71 for M5): the safety-critical
piece lands and is proven before the happy path is built on top of it.

Three real, separate assertions, each mirroring an already-established
meta-test pattern in this repo:

1. **No raw HTTP-client identifier anywhere in real code**
   (`test_no_response_scraping.py`'s own identifier-ban-list, AST-based,
   docstring-blind precedent, reusing `referenced_code_identifiers()`
   unmodified). Also covers a fixed, named set of hypothetical future
   `BrowserAutomationPort` form-interaction method names --
   `BrowserAutomationPort` has no such methods today (`open_page`,
   `query_dom`, `capture_screenshot`, `close` only), so this is a real,
   named future-bypass-risk check (mirroring ADR-0057's own finding 4
   for a hypothetical `CalendarPort.update_event`), not a check against
   a real, current gap.
2. **No submission-shaped function/method parameter name**
   (`submit`, `apply_to`, `application_payload`,
   `credentials_for_submission`, case-insensitive substring match) --
   a new, real AST helper (`_function_parameter_names`), since
   `referenced_code_identifiers()` does not capture `ast.arg` nodes.

**A real, honest, named limitation, stated now rather than discovered
later** (matching `m6b-job-assistance.md`'s own "Assertion 1" note):
`post` is a common short word; a hypothetical, entirely unrelated
future identifier literally named `post` inside this package would
false-positive. Accepted deliberately -- narrower ever needed later,
not looser, the same trade-off `test_source_invariants.py`'s own
vendor-name grep already makes.

Per this project's own Meta-tests convention (`CLAUDE.md`), every
predicate below also proves it actually fires against a deliberate
violation, and that it does not false-positive on legitimate code
(a real `browser.open_page`-shaped call must never trip it) -- not
just that today's tree happens to be clean.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.meta.helpers import SRC_ROOT, iter_py_files, referenced_code_identifiers

if TYPE_CHECKING:
    from pathlib import Path

_JOB_ASSISTANCE_PACKAGE = SRC_ROOT / "jarvis" / "application" / "job_assistance"
_JOB_ASSISTANCE_KERNEL = SRC_ROOT / "jarvis" / "kernel" / "job_assistance.py"
_DRAFT_STORAGE_PORT = SRC_ROOT / "jarvis" / "ports" / "draft_storage.py"
_DRAFT_STORAGE_ADAPTER = SRC_ROOT / "jarvis" / "adapters" / "draft_storage.py"

_BANNED_IDENTIFIERS = frozenset(
    {
        # Raw HTTP clients -- BrowserAutomationPort (CDP-mediated) is the
        # only real network-reaching mechanism this package may use.
        "requests",
        "httpx",
        "aiohttp",
        "urlopen",
        "urlretrieve",
        "Request",
        "post",
        # Hypothetical future BrowserAutomationPort form-interaction
        # methods -- none exist today; named now so a future, unrelated
        # addition to that port can never be called from this package
        # without ADR-0058 being reopened first.
        "submit_form",
        "click",
        "fill",
        "fill_form",
        "dispatch_form_submit",
        "press_key",
        "type_text",
    }
)

_BANNED_PARAMETER_SUBSTRINGS = (
    "submit",
    "apply_to",
    "application_payload",
    "credentials_for_submission",
)


def _m6b_module_paths() -> list[Path]:
    """Return every real .py file under M6b's own package path -- the meta-test's own scope."""
    paths = list(iter_py_files(_JOB_ASSISTANCE_PACKAGE))
    for single in (_JOB_ASSISTANCE_KERNEL, _DRAFT_STORAGE_PORT, _DRAFT_STORAGE_ADAPTER):
        if single.exists():
            paths.append(single)
    return paths


def _function_parameter_names(source: str) -> set[str]:
    """Return every real parameter name declared on any function/method in ``source``.

    A new, real AST helper: `referenced_code_identifiers()` walks
    `ast.Name`/`ast.Attribute`/`ast.ImportFrom` only, never `ast.arg`
    (a function's own declared parameters), so parameter names need
    their own scan -- mirroring `tests/meta/helpers.py`'s own
    docstring-blind, real-code-only discipline (only `ast.parse`d
    structure, nothing string-scanned).
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.update(arg.arg for arg in node.args.args)
            names.update(arg.arg for arg in node.args.kwonlyargs)
            if node.args.vararg is not None:
                names.add(node.args.vararg.arg)
            if node.args.kwarg is not None:
                names.add(node.args.kwarg.arg)
    return names


def _has_submission_shaped_parameter(names: set[str]) -> bool:
    """Return whether any parameter name in ``names`` matches a banned submission-shaped pattern."""
    lowered = {name.lower() for name in names}
    return any(banned in name for name in lowered for banned in _BANNED_PARAMETER_SUBSTRINGS)


def test_no_m6b_module_references_a_banned_submission_identifier() -> None:
    """No real code under M6b's own package path references any banned identifier (ADR-0058)."""
    for path in _m6b_module_paths():
        identifiers = referenced_code_identifiers(path.read_text(encoding="utf-8"))
        found = identifiers & _BANNED_IDENTIFIERS
        assert not found, f"{path} references banned identifier(s): {found}"


def test_no_m6b_module_declares_a_submission_shaped_parameter() -> None:
    """No function/method under M6b's own package path takes a submission-shaped parameter."""
    for path in _m6b_module_paths():
        names = _function_parameter_names(path.read_text(encoding="utf-8"))
        assert not _has_submission_shaped_parameter(names), (
            f"{path} declares a submission-shaped parameter among: {names}"
        )


def test_the_identifier_ban_actually_detects_a_raw_http_client_violation() -> None:
    """The predicate genuinely fires on a real violation (a raw HTTP POST call), not just on a clean tree."""  # noqa: E501
    violating_snippet = (
        "import requests\n\ndef f(url, payload):\n    return requests.post(url, json=payload)\n"
    )

    identifiers = referenced_code_identifiers(violating_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == {"requests", "post"}


def test_the_identifier_ban_actually_detects_a_future_form_interaction_call() -> None:
    """The predicate fires on a hypothetical future BrowserAutomationPort.submit_form() call."""
    violating_snippet = "def f(browser, handle):\n    browser.submit_form(handle)\n"

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "submit_form" in identifiers & _BANNED_IDENTIFIERS


def test_the_identifier_ban_does_not_false_positive_on_a_real_open_page_call() -> None:
    """A real, legitimate browser.open_page()/query_dom() call is never flagged."""
    legitimate_snippet = (
        "async def research(browser, url):\n"
        "    handle = await browser.open_page(url)\n"
        "    html = await browser.query_dom(handle, 'body')\n"
        "    await browser.close(handle)\n"
        "    return html\n"
    )

    identifiers = referenced_code_identifiers(legitimate_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == set()


def test_the_identifier_ban_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this restriction (naming a banned word) must not itself be a violation."""
    documentation_only_snippet = (
        '"""This module must never call requests.post or browser.submit_form.\n'
        "\n"
        "See ADR-0058.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    identifiers = referenced_code_identifiers(documentation_only_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == set()


def test_the_parameter_ban_actually_detects_a_submission_shaped_signature() -> None:
    """The predicate fires on a real, submission-shaped function signature."""
    violating_snippet = (
        "def handle_application(self, application_payload: dict) -> None:\n    pass\n"
    )

    names = _function_parameter_names(violating_snippet)

    assert _has_submission_shaped_parameter(names) is True


def test_the_parameter_ban_does_not_false_positive_on_an_ordinary_drafting_signature() -> None:
    """A real, legitimate drafting-capability signature is never flagged."""
    legitimate_snippet = (
        "async def draft_document(self, task: str, target_repo=None) -> str:\n    pass\n"
    )

    names = _function_parameter_names(legitimate_snippet)

    assert _has_submission_shaped_parameter(names) is False
