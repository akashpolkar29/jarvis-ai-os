"""AST-based tests for invariants ruff's import-level checks cannot fully cover.

``tests/meta/test_gate_integrity.py`` verifies the gates exist and are
wired into CI; this file verifies the underlying invariants those gates
exist to protect actually hold, against the real source tree.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.meta.helpers import (
    attribute_name_equality_comparisons,
    dotted_attribute_calls,
    iter_py_files,
    top_level_imports,
)

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
DOMAIN_ROOT = SRC_ROOT / "jarvis" / "domain"
APPLICATION_ROOT = SRC_ROOT / "jarvis" / "application"
PORTS_ROOT = SRC_ROOT / "jarvis" / "ports"

# ADR-0021: these strings may never appear in domain/, application/, or
# ports/ -- a port describes a role, never a specific integration.
_BANNED_VENDOR_STRINGS = frozenset({"openai", "anthropic", "chatgpt", "claude", "gpt"})

_BANNED_CLOCK_AND_ID_CALLS = frozenset(
    {
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "time.monotonic",
        "uuid.uuid1",
        "uuid.uuid4",
    }
)

# Future ClockPort/IdPort adapter implementations are the one place these
# calls are legitimate. Empty for now — no adapters exist yet.
_CLOCK_ID_ADAPTER_ALLOWLIST: frozenset[Path] = frozenset()


def test_domain_imports_stdlib_only() -> None:
    """Every top-level import in ``domain/`` must be a stdlib module."""
    for py_file in iter_py_files(DOMAIN_ROOT):
        for name in top_level_imports(py_file):
            assert name in sys.stdlib_module_names, f"{py_file} imports non-stdlib module {name!r}"


def test_no_banned_clock_or_id_calls_in_src() -> None:
    """No file in ``src/`` calls the banned wall-clock/randomness APIs directly.

    Catches what ruff's TID251 banned-api rule cannot: attribute calls
    like ``time.time()`` reached via a bare ``import time``.
    """
    for py_file in iter_py_files(SRC_ROOT):
        if py_file in _CLOCK_ID_ADAPTER_ALLOWLIST:
            continue
        for call in dotted_attribute_calls(py_file):
            assert call not in _BANNED_CLOCK_AND_ID_CALLS, f"{py_file} calls banned API {call!r}"


def test_no_vendor_names_in_domain_application_or_ports() -> None:
    """No banned vendor string (ADR-0021) appears anywhere in domain/, application/, or ports/.

    A real, pre-existing gap closed here: ADR-0021 and CLAUDE.md both
    describe this as already "enforced by static grep," but no such
    check existed anywhere in ``tests/`` before this test -- found while
    confirming WP-31's acceptance criterion that the check "actually
    covers ports/." It didn't; nothing did. Scans raw file text, not
    just imports/identifiers, since ADR-0021 bans the *strings*
    outright, including inside comments and docstrings.
    """
    for root in (DOMAIN_ROOT, APPLICATION_ROOT, PORTS_ROOT):
        for py_file in iter_py_files(root):
            text = py_file.read_text(encoding="utf-8").lower()
            for banned in _BANNED_VENDOR_STRINGS:
                assert banned not in text, f"{py_file} contains banned vendor string {banned!r}"


def test_no_provider_profile_name_identity_conditionals_outside_adapters() -> None:
    """No branching on `.name` identity in domain/, application/, or ports/ (task #21, WP-32).

    ``ProviderProfile.name`` (WP-30) is real, registered-once metadata.
    Branching application logic on which specific provider a ``name``
    identifies (``if profile.name == "...": ...``) would leak
    provider-specific behavior into a layer that is supposed to stay
    provider-agnostic -- the same abstraction leak ADR-0021's
    vendor-string grep guards against, one level more indirect (a
    conditional on the field, not a literal banned string in it).
    Deliberately not scoped to ``adapters/``: WP-32's own
    ``family_a.py``/``family_b.py``/``local.py`` are the first modules
    to define a real ``ProviderProfile`` at all, and none of them
    branch on ``.name`` -- routing by provider identity is
    ``application.reasoning.router``'s job (WP-36), not decided yet,
    and this check exists so that whenever it lands, it cannot do so
    by string-comparing ``.name``.
    """
    for root in (DOMAIN_ROOT, APPLICATION_ROOT, PORTS_ROOT):
        for py_file in iter_py_files(root):
            lines = attribute_name_equality_comparisons(py_file)
            assert not lines, f"{py_file} branches on .name identity at line(s) {lines}"


def test_every_src_init_has_a_docstring() -> None:
    """Every ``__init__.py`` under ``src/jarvis`` must carry a real docstring."""
    for init_file in sorted(SRC_ROOT.rglob("__init__.py")):
        module_ast = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
        docstring = ast.get_docstring(module_ast)
        assert docstring, f"{init_file} has no module docstring"
