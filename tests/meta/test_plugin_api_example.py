"""Mechanical proof that jarvis.plugin_api is a real, sufficient plugin-authoring surface.

Two independent checks, mirroring `tests/meta/test_speaker_id_isolation.py`'s
own "structural check needs its own proof it actually fires" discipline:

1. `test_example_plugin_imports_only_plugin_api_and_stdlib` -- AST-scans
   `docs/plugin-guide/example_plugin.py` and asserts every real import
   resolves to `jarvis.plugin_api` (or a stdlib/`__future__` module),
   never `jarvis.application`/`jarvis.adapters`/`jarvis.kernel`/
   `jarvis.ipc`/`jarvis.cli`. `test_the_scan_predicate_actually_detects_a_violation`
   proves the predicate itself would catch a real violation, not just
   that today's example file happens to be clean.
2. `test_the_example_capability_authorizes_correctly_end_to_end` --
   builds a real, fresh `CapabilityRegistry`/`AuditChain`/
   `AuthorizationOrchestrator` (the same real components every kernel
   composition function uses), registers the example's own
   `CapabilityDescriptor`, and authorizes it under every real
   confirmation-state combination, proving the descriptor a
   plugin_api-only file builds really does behave per the real policy
   engine's own `Tier.ALLOW` rule -- not merely that it *compiles*.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from jarvis.domain.capability import CapabilityId

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_PLUGIN_PATH = _REPO_ROOT / "docs" / "plugin-guide" / "example_plugin.py"

_ALLOWED_TOP_LEVEL_IMPORTS = frozenset({"__future__", "jarvis"})


def _load_example_plugin_module() -> Any:
    """Load `docs/plugin-guide/example_plugin.py` without adding it to `sys.path`.

    Standalone (not a real installed package), so `importlib.util`'s
    file-based loading is used rather than a plain `import` statement
    -- avoids mutating `sys.path` for every other test in this suite.
    """
    spec = importlib.util.spec_from_file_location("example_plugin", _EXAMPLE_PLUGIN_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover -- only if the file is missing
        msg = f"Could not load spec for {_EXAMPLE_PLUGIN_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_example_plugin = _load_example_plugin_module()
EXAMPLE_WORD_COUNT_CAPABILITY_ID: CapabilityId = _example_plugin.EXAMPLE_WORD_COUNT_CAPABILITY_ID
build_example_word_count_descriptor = _example_plugin.build_example_word_count_descriptor
count_words = _example_plugin.count_words


def _real_imported_module_paths(py_file: Path) -> set[str]:
    """Return every real, dotted module path `py_file` imports (never a docstring/comment)."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            paths.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            paths.add(node.module)
    return paths


def test_example_plugin_imports_only_plugin_api_and_stdlib() -> None:
    """The real, mechanical proof: no jarvis.application/adapters/kernel/ipc/cli import exists."""
    imported = _real_imported_module_paths(_EXAMPLE_PLUGIN_PATH)

    for module_path in imported:
        top_level = module_path.split(".")[0]
        assert top_level in _ALLOWED_TOP_LEVEL_IMPORTS, (
            f"example_plugin.py imports {module_path!r}, outside stdlib/jarvis.plugin_api"
        )
        if top_level == "jarvis":
            assert module_path == "jarvis.plugin_api" or module_path.startswith(
                "jarvis.plugin_api."
            ), f"example_plugin.py imports {module_path!r}, not jarvis.plugin_api"


def test_the_scan_predicate_actually_detects_a_violation(tmp_path: Path) -> None:
    """Proves the check above isn't vacuously true -- it really flags a real violation."""
    violating_file = tmp_path / "violating_plugin.py"
    violating_file.write_text(
        "from jarvis.kernel.capabilities import build_default_registry\n",
        encoding="utf-8",
    )

    imported = _real_imported_module_paths(violating_file)

    assert any(
        module_path.split(".")[0] == "jarvis" and module_path != "jarvis.plugin_api"
        for module_path in imported
    )


def test_the_example_capability_registers_without_collision() -> None:
    """A plugin-authored descriptor registers cleanly into a real, fresh registry."""
    registry = CapabilityRegistry()

    registry.register(build_example_word_count_descriptor())

    assert registry.get(EXAMPLE_WORD_COUNT_CAPABILITY_ID) is not None


def test_the_example_capability_authorizes_correctly_end_to_end() -> None:
    """The real orchestrator grants example.word_count regardless of confirmation (Tier.ALLOW)."""
    registry = CapabilityRegistry()
    registry.register(build_example_word_count_descriptor())
    orchestrator = AuthorizationOrchestrator(AuditChain(), registry, clock=SystemClockAdapter())

    for physical in (True, False):
        for remote in (True, False):
            context = PolicyContext(
                physical_confirmation_available=physical, remote_confirmation_available=remote
            )
            decision = orchestrator.authorize_by_id(
                EXAMPLE_WORD_COUNT_CAPABILITY_ID,
                Tainted({"text": "four real words here"}, Provenance.user()),
                context,
            )
            assert decision.granted is True


def test_the_example_handler_actually_works() -> None:
    """The real, pure handler a granted invocation would call -- proves it does something real."""
    assert count_words("four real words here") == 4  # noqa: PLR2004 -- the real word count above
    assert count_words("") == 0
