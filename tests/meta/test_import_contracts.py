"""Tests that the import-linter contracts actually fire on violations.

Each test builds a full copy of the real ``src/`` tree, injects one
deliberate, single-contract violation, and asserts that exactly the
targeted contract is reported ``BROKEN`` by the real ``lint-imports``
binary — not a stand-in assertion about ``pyproject.toml`` text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.meta.helpers import build_project_copy, inject_import_violation, run_lint_imports

if TYPE_CHECKING:
    from pathlib import Path

_ALL_CONTRACTS = (
    "C1 layered architecture",
    "C2 domain purity",
    "C6 no GLib in the core",
    "C7 plugin_api depends only on domain",
)


def _contract_status(output: str, contract_name: str) -> str:
    """Return ``"BROKEN"`` or ``"KEPT"`` for ``contract_name`` in lint-imports output.

    lint-imports prints either ``"<name> KEPT"`` / ``"<name> BROKEN"`` on one
    line, or the name alone followed by the status a line or two later —
    this checks both shapes.
    """
    lines = output.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == contract_name:
            for later in lines[index : index + 4]:
                if "BROKEN" in later:
                    return "BROKEN"
                if "KEPT" in later:
                    return "KEPT"
        elif stripped.startswith(contract_name):
            remainder = stripped[len(contract_name) :].strip()
            if remainder in {"BROKEN", "KEPT"}:
                return remainder
    msg = f"Contract {contract_name!r} not found in lint-imports output:\n{output}"
    raise AssertionError(msg)


def test_baseline_all_contracts_kept(tmp_path: Path) -> None:
    """An unmodified copy of the tree keeps every configured contract."""
    src_root = build_project_copy(tmp_path)
    result = run_lint_imports(tmp_path, src_root)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in _ALL_CONTRACTS:
        assert _contract_status(result.stdout, name) == "KEPT"


def test_c1_layering_violation_is_caught(tmp_path: Path) -> None:
    """A lower layer importing a higher layer breaks C1."""
    src_root = build_project_copy(tmp_path)
    inject_import_violation(src_root / "jarvis" / "ports" / "__init__.py", "jarvis.adapters")
    result = run_lint_imports(tmp_path, src_root)
    assert result.returncode != 0
    assert _contract_status(result.stdout, "C1 layered architecture") == "BROKEN"


def test_c2_domain_purity_violation_is_caught(tmp_path: Path) -> None:
    """``domain/`` importing any other jarvis package breaks C2."""
    src_root = build_project_copy(tmp_path)
    inject_import_violation(src_root / "jarvis" / "domain" / "__init__.py", "jarvis.ports")
    result = run_lint_imports(tmp_path, src_root)
    assert result.returncode != 0
    assert _contract_status(result.stdout, "C2 domain purity") == "BROKEN"


def test_c6_no_glib_in_core_violation_is_caught(tmp_path: Path) -> None:
    """``domain``/``application``/``kernel`` importing ``gi`` breaks C6."""
    src_root = build_project_copy(tmp_path)
    inject_import_violation(src_root / "jarvis" / "kernel" / "__init__.py", "gi")
    result = run_lint_imports(tmp_path, src_root)
    assert result.returncode != 0
    assert _contract_status(result.stdout, "C6 no GLib in the core") == "BROKEN"


def test_c7_plugin_api_violation_is_caught(tmp_path: Path) -> None:
    """``plugin_api`` importing anything but ``domain`` breaks C7."""
    src_root = build_project_copy(tmp_path)
    inject_import_violation(src_root / "jarvis" / "plugin_api" / "__init__.py", "jarvis.kernel")
    result = run_lint_imports(tmp_path, src_root)
    assert result.returncode != 0
    assert _contract_status(result.stdout, "C7 plugin_api depends only on domain") == "BROKEN"


def test_violation_does_not_spuriously_break_unrelated_contracts(tmp_path: Path) -> None:
    """A C6 violation must not also flip C1, C2, or C7 to BROKEN."""
    src_root = build_project_copy(tmp_path)
    inject_import_violation(src_root / "jarvis" / "kernel" / "__init__.py", "gi")
    result = run_lint_imports(tmp_path, src_root)
    assert _contract_status(result.stdout, "C6 no GLib in the core") == "BROKEN"
    for name in (
        "C1 layered architecture",
        "C2 domain purity",
        "C7 plugin_api depends only on domain",
    ):
        assert _contract_status(result.stdout, name) == "KEPT"
