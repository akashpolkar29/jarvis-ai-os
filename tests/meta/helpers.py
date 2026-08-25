"""Test utilities for the meta-test suite.

These helpers let ``tests/meta`` build a deliberately-broken copy of the
real source tree, run the actual ``lint-imports`` binary against it, and
inspect the results — so the meta-tests exercise the real gate, not a
stand-in assertion about configuration text.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sysconfig
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
PYPROJECT = REPO_ROOT / "pyproject.toml"

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences (color, cursor movement) from ``text``.

    ``lint-imports``' output is colorized/animated even when captured
    from a subprocess; callers that parse its text for contract names
    and KEPT/BROKEN status need the plain text underneath.
    """
    return _ANSI_ESCAPE.sub("", text)


def build_project_copy(destination: Path) -> Path:
    """Copy the real ``src/`` tree and ``pyproject.toml`` into ``destination``.

    Returns the path to the copied ``src/`` directory, which callers put
    on ``PYTHONPATH`` so import-linter's dependency graph builder can
    locate the ``jarvis`` package.
    """
    dest_src = destination / "src"
    shutil.copytree(SRC_ROOT, dest_src)
    shutil.copy2(PYPROJECT, destination / "pyproject.toml")
    return dest_src


def inject_import_violation(package_init: Path, forbidden_import: str) -> None:
    """Append an import of ``forbidden_import`` to ``package_init``.

    Used to construct a deliberate, single-line contract violation in a
    copy of the tree, never in the real source tree.
    """
    with package_init.open("a", encoding="utf-8") as handle:
        handle.write(f"\nimport {forbidden_import}\n")


def find_lint_imports_executable() -> str:
    """Locate the ``lint-imports`` console script.

    ``python -m importlinter.cli`` silently does nothing because
    import-linter ships no ``__main__`` module; the console script entry
    point is the only supported invocation.
    """
    candidate = Path(sysconfig.get_path("scripts")) / "lint-imports"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("lint-imports")
    if found is not None:
        return found
    msg = "Could not locate the lint-imports console script."
    raise RuntimeError(msg)


def run_lint_imports(project_root: Path, src_root: Path) -> subprocess.CompletedProcess[str]:
    """Run ``lint-imports --no-cache`` against the copy rooted at ``project_root``."""
    executable = find_lint_imports_executable()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src_root)
    return subprocess.run(
        [executable, "--config", str(project_root / "pyproject.toml"), "--no-cache"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def top_level_imports(py_file: Path) -> list[str]:
    """Return the top-level module names imported by ``py_file``."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.append(node.module.split(".")[0])
    return names


def dotted_attribute_calls(py_file: Path) -> list[str]:
    """Return dotted attribute calls (e.g. ``time.time``) found in ``py_file``.

    Catches usages ruff's import-level banned-api rule cannot, such as
    ``time.time()`` reached via a bare ``import time``.
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            parts: list[str] = [node.func.attr]
            value = node.func.value
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
            calls.append(".".join(reversed(parts)))
    return calls


def attribute_name_equality_comparisons(py_file: Path) -> list[int]:
    """Return line numbers of `.name == ...` / `... == .name`-shaped comparisons in `py_file`.

    Catches branching on an attribute literally called ``name`` --
    e.g. ``provider.name == "..."`` -- the same class of abstraction
    leak a vendor-string grep catches, one level more indirect: a
    conditional on a registered-once identity field instead of a
    literal banned string.
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not all(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        is_name_comparison = any(
            isinstance(operand, ast.Attribute) and operand.attr == "name" for operand in operands
        )
        if is_name_comparison:
            lines.append(node.lineno)
    return lines


def iter_py_files(package_dir: Path) -> list[Path]:
    """Return every ``.py`` file under ``package_dir``, sorted for determinism."""
    return sorted(package_dir.rglob("*.py"))


def referenced_code_identifiers(source: str) -> set[str]:
    """Return every identifier referenced in actual code -- names, attributes, imports.

    Deliberately excludes docstrings and comments: those are string
    literals and stripped tokens to the AST, not ``ast.Name``/
    ``ast.Attribute``/``ast.ImportFrom`` nodes. Shared by every
    meta-test that bans a specific identifier from appearing in a
    module's real code while still letting that module's own
    docstrings name the identifier in prose to explain the rule
    (``tests/meta/test_no_response_scraping.py``,
    ``tests/meta/test_memory_adapter_isolation.py``).
    """
    tree = ast.parse(source)
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            identifiers.update(alias.asname or alias.name for alias in node.names)
    return identifiers
