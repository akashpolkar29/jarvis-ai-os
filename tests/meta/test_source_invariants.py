"""AST-based tests for invariants ruff's import-level checks cannot fully cover.

``tests/meta/test_gate_integrity.py`` verifies the gates exist and are
wired into CI; this file verifies the underlying invariants those gates
exist to protect actually hold, against the real source tree.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.meta.helpers import dotted_attribute_calls, iter_py_files, top_level_imports

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
DOMAIN_ROOT = SRC_ROOT / "jarvis" / "domain"

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


def test_every_src_init_has_a_docstring() -> None:
    """Every ``__init__.py`` under ``src/jarvis`` must carry a real docstring."""
    for init_file in sorted(SRC_ROOT.rglob("__init__.py")):
        module_ast = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
        docstring = ast.get_docstring(module_ast)
        assert docstring, f"{init_file} has no module docstring"
