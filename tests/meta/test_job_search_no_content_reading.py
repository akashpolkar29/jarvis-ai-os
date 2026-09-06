"""Mechanical enforcement: job_search.open_results never reads/scrapes page content.

Real, direct decision recorded in
``docs/architecture/job-search-scoping-notes.md``: LinkedIn's and
Indeed's own current Terms of Service both explicitly prohibit
automated scraping/bot access to their job-search surfaces. This
capability's only real action is building a URL string and opening it
in the user's own, real, ordinary Brave browser -- a human does the
actual searching and reading. This is that boundary's own real,
mechanical proof, mirroring
``tests/meta/test_job_assistance_no_submission.py``'s own established
AST-scan pattern for ADR-0058's identically-shaped guarantee.

Two real, separate assertions:

1. **No content-reading identifier anywhere in real code** under
   ``kernel/job_search.py`` -- both the two real, current
   ``BrowserAutomationPort`` content-reading methods
   (``inspect_dom``/``query_dom``, ``capture_screenshot``) and a
   fixed, named set of raw-HTTP-client identifiers (mirroring
   ``test_job_assistance_no_submission.py``'s own "no raw HTTP client"
   check -- this module has no legitimate reason to make any network
   call other than through ``BravePort.open_url``).
2. **`kernel/job_search.py` never imports `BrowserAutomationPort` or
   any of its real adapters at all** -- a real, stronger, additional
   guarantee this module's own narrower scope allows that
   ``test_job_assistance_no_submission.py`` could not make (M6b's own
   drafting capability legitimately opens pages via
   ``browser.open_page`` for research; this capability has no
   legitimate reason to import that port at all, only ``BravePort``).
   AST-based (real `ast.Import`/`ast.ImportFrom` module paths only),
   the same docstring-blind discipline as assertion 1 -- this
   docstring's own prose naming `adapters/browser_automation.py` must
   never itself trip the check.

Per this project's own Meta-tests convention (``CLAUDE.md``), every
predicate below also proves it actually fires against a deliberate
violation, and that it does not false-positive on legitimate code (a
real ``browser.open_url``-shaped call must never trip it) -- not just
that today's tree happens to be clean.
"""

from __future__ import annotations

import ast

from tests.meta.helpers import SRC_ROOT, referenced_code_identifiers

_JOB_SEARCH_KERNEL = SRC_ROOT / "jarvis" / "kernel" / "job_search.py"

_BANNED_IDENTIFIERS = frozenset(
    {
        # The two real, current BrowserAutomationPort content-reading
        # methods -- job_search.open_results must never call either.
        "inspect_dom",
        "query_dom",
        "capture_screenshot",
        # Raw HTTP clients -- BravePort.open_url (a subprocess launch,
        # no network call of this module's own) is the only real
        # mechanism this module may use to reach either site.
        "requests",
        "httpx",
        "aiohttp",
        "urlopen",
        "urlretrieve",
    }
)

_BANNED_IMPORT_MODULE_SUBSTRINGS = ("browser_automation",)


def _imported_module_names(source: str) -> set[str]:
    """Return every real module dotted-path referenced by an Import/ImportFrom node.

    AST-based, same docstring-blind discipline as
    `referenced_code_identifiers` -- a module's own docstring
    discussing `adapters/browser_automation.py` in prose must never
    trip this, only a real `import`/`from ... import` statement.
    """
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_job_search_kernel_module_references_no_banned_content_reading_identifier() -> None:
    """The real, current kernel/job_search.py never references a banned identifier."""
    source = _JOB_SEARCH_KERNEL.read_text(encoding="utf-8")
    identifiers = referenced_code_identifiers(source)
    found = identifiers & _BANNED_IDENTIFIERS
    assert not found, f"{_JOB_SEARCH_KERNEL} references banned identifier(s): {found}"


def test_job_search_kernel_module_never_imports_browser_automation_port() -> None:
    """job_search.open_results has no legitimate reason to import BrowserAutomationPort at all."""
    source = _JOB_SEARCH_KERNEL.read_text(encoding="utf-8")
    modules = _imported_module_names(source)
    for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS:
        matches = {module for module in modules if banned in module}
        assert not matches, (
            f"{_JOB_SEARCH_KERNEL} imports {matches} -- job_search.open_results "
            "must only ever use BravePort, never BrowserAutomationPort."
        )


def test_the_identifier_ban_actually_detects_a_real_content_reading_violation() -> None:
    """The predicate genuinely fires on a hypothetical inspect_dom()/query_dom() call."""
    violating_snippet = (
        "async def f(browser, handle):\n    return await browser.query_dom(handle, 'body')\n"
    )

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "query_dom" in identifiers & _BANNED_IDENTIFIERS


def test_the_identifier_ban_actually_detects_a_raw_http_client_violation() -> None:
    """The predicate genuinely fires on a real, hypothetical raw HTTP call."""
    violating_snippet = "import requests\n\ndef f(url):\n    return requests.get(url)\n"

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "requests" in identifiers & _BANNED_IDENTIFIERS


def test_the_identifier_ban_does_not_false_positive_on_a_real_open_url_call() -> None:
    """A real, legitimate BravePort.open_url() call is never flagged."""
    legitimate_snippet = "def f(browser, url):\n    browser.open_url(url)\n"

    identifiers = referenced_code_identifiers(legitimate_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == set()


def test_the_import_ban_actually_detects_a_real_browser_automation_import() -> None:
    """The predicate genuinely fires on a hypothetical BrowserAutomationPort import."""
    violating_snippet = "from jarvis.ports.browser_automation import BrowserAutomationPort\n"

    modules = _imported_module_names(violating_snippet)

    assert any("browser_automation" in module for module in modules)


def test_the_import_ban_does_not_false_positive_on_a_real_brave_port_import() -> None:
    """A real, legitimate BravePort import is never flagged."""
    legitimate_snippet = "from jarvis.ports.brave import BravePort\n"

    modules = _imported_module_names(legitimate_snippet)

    assert not any("browser_automation" in module for module in modules)


def test_the_import_ban_ignores_a_docstring_that_merely_discusses_the_guarantee() -> None:
    """Prose naming adapters/browser_automation.py in a docstring must not itself be a violation."""
    documentation_only_snippet = (
        '"""This module must never import adapters/browser_automation.py.\n"""\n\nX = 1\n'
    )

    modules = _imported_module_names(documentation_only_snippet)

    assert not any("browser_automation" in module for module in modules)


def test_the_identifier_ban_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this restriction (naming a banned word) must not itself be a violation."""
    documentation_only_snippet = (
        '"""This module must never call inspect_dom, query_dom, or capture_screenshot.\n'
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    identifiers = referenced_code_identifiers(documentation_only_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == set()
