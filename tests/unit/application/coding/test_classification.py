"""Unit tests for jarvis.application.coding.classification.

Real file I/O against real tmp_path directories throughout -- every
detection signal is checked against a real pytest.ini/pyproject.toml/
go.mod/.rspec/package.json this test itself writes, not mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.application.coding.classification import (
    UnrecognizedTestConventionError,
    code_write_effect_for,
    detect_protected_patterns,
    resolve_protected_patterns,
)
from jarvis.domain.capability import Effect

_PATTERNS = ("test_*.py", "*_test.py", "tests/*")


# --- code_write_effect_for -------------------------------------------------


def test_ordinary_path_maps_to_code_write() -> None:
    assert code_write_effect_for(Path("src/widget.py"), _PATTERNS) is Effect.CODE_WRITE


def test_test_prefixed_file_maps_to_protected_path_write() -> None:
    assert code_write_effect_for(Path("test_widget.py"), _PATTERNS) is Effect.PROTECTED_PATH_WRITE


def test_test_suffixed_file_maps_to_protected_path_write() -> None:
    assert code_write_effect_for(Path("widget_test.py"), _PATTERNS) is Effect.PROTECTED_PATH_WRITE


def test_tests_directory_file_maps_to_protected_path_write() -> None:
    assert (
        code_write_effect_for(Path("tests/test_widget.py"), _PATTERNS)
        is Effect.PROTECTED_PATH_WRITE
    )


def test_non_python_file_under_tests_directory_is_still_protected() -> None:
    """The tests/* pattern protects the whole directory, not just *.py files inside it."""
    assert (
        code_write_effect_for(Path("tests/fixtures/data.json"), _PATTERNS)
        is Effect.PROTECTED_PATH_WRITE
    )


def test_empty_patterns_never_protects_anything() -> None:
    assert code_write_effect_for(Path("test_widget.py"), ()) is Effect.CODE_WRITE


# --- detect_protected_patterns: Python/pytest -------------------------------


def test_detects_pytest_ini(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("test_*.py", "*_test.py")


def test_detects_pyproject_toml_pytest_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n', encoding="utf-8"
    )

    assert detect_protected_patterns(tmp_path) == ("test_*.py", "*_test.py")


def test_pyproject_toml_without_pytest_section_is_not_detected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 100\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


def test_malformed_pyproject_toml_is_not_detected_not_raised(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("this is not valid toml [[[", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


def test_detects_setup_cfg_pytest_section(tmp_path: Path) -> None:
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\ntestpaths = tests\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("test_*.py", "*_test.py")


def test_detects_tox_ini_pytest_section(tmp_path: Path) -> None:
    (tmp_path / "tox.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("test_*.py", "*_test.py")


def test_malformed_setup_cfg_is_not_detected_not_raised(tmp_path: Path) -> None:
    """A real, invalid INI file (duplicate section) makes configparser raise -- handled here."""
    (tmp_path / "setup.cfg").write_text(
        "[tool:pytest]\nx = 1\n[tool:pytest]\ny = 2\n", encoding="utf-8"
    )

    assert detect_protected_patterns(tmp_path) is None


def test_setup_cfg_without_pytest_section_is_not_detected(tmp_path: Path) -> None:
    """A real, valid setup.cfg that parses cleanly but lacks [tool:pytest] entirely.

    Found by mutation testing (overnight Track 2, 2026-09-04): the real
    `_ini_file_has_section` internal helper is `bool(read_files) and
    parser.has_section(section)`, and no existing test distinguished
    "file could not be read at all" (read_files == []) from "file was
    read fine but the target section just isn't in it" (read_files
    non-empty, has_section() False) -- an `and`-to-`or` mutant on that
    line survived because every prior test only ever exercised the
    read_files == [] side of that expression, never this side.
    """
    (tmp_path / "setup.cfg").write_text("[metadata]\nname = example\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


def test_tox_ini_without_pytest_section_is_not_detected(tmp_path: Path) -> None:
    """Mirrors test_setup_cfg_without_pytest_section_is_not_detected for tox.ini's own [pytest]."""
    (tmp_path / "tox.ini").write_text("[testenv]\ndeps = pytest\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


# --- detect_protected_patterns: Go ------------------------------------------


def test_detects_go_mod(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/widget\n\ngo 1.22\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("*_test.go",)


# --- detect_protected_patterns: Ruby/RSpec ----------------------------------


def test_detects_rspec_config_file(tmp_path: Path) -> None:
    (tmp_path / ".rspec").write_text("--require spec_helper\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("*_spec.rb", "spec/*")


def test_detects_gemfile_mentioning_rspec(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text('gem "rspec"\n', encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("*_spec.rb", "spec/*")


def test_gemfile_without_rspec_is_not_detected(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text('gem "rails"\n', encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


# --- detect_protected_patterns: JavaScript/TypeScript -----------------------


def test_detects_jest_in_package_json_dev_dependencies(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"jest": "^29.0.0"}}), encoding="utf-8"
    )

    patterns = detect_protected_patterns(tmp_path)

    assert patterns is not None
    assert "*.test.js" in patterns
    assert "__tests__/*" in patterns


def test_detects_vitest_in_package_json_dependencies(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"vitest": "^2.0.0"}}), encoding="utf-8"
    )

    assert detect_protected_patterns(tmp_path) is not None


def test_detects_mocha_with_its_own_weaker_default(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"mocha": "^10.0.0"}}), encoding="utf-8"
    )

    assert detect_protected_patterns(tmp_path) == ("test/*",)


def test_package_json_naming_no_known_framework_is_not_detected(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0"}}), encoding="utf-8"
    )

    assert detect_protected_patterns(tmp_path) is None


def test_malformed_package_json_is_not_detected_not_raised(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not valid json", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


def test_package_json_that_is_valid_json_but_not_an_object_is_not_detected(tmp_path: Path) -> None:
    """Real, valid JSON (a bare array) that just isn't the object shape package.json requires."""
    (tmp_path / "package.json").write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    assert detect_protected_patterns(tmp_path) is None


# --- detect_protected_patterns: real, honest absence ------------------------


def test_empty_repository_root_detects_nothing(tmp_path: Path) -> None:
    """No real signal at all -- a real, expected, fail-closed-triggering outcome."""
    assert detect_protected_patterns(tmp_path) is None


def test_precedence_pytest_checked_before_go_when_both_signals_present(tmp_path: Path) -> None:
    """A real, stated precedence, not an error, when a repository has more than one real signal."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example.com/widget\n", encoding="utf-8")

    assert detect_protected_patterns(tmp_path) == ("test_*.py", "*_test.py")


# --- resolve_protected_patterns ---------------------------------------------


def test_explicit_patterns_always_win_over_detection(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/widget\n", encoding="utf-8")

    resolved = resolve_protected_patterns(tmp_path, explicit_patterns=("custom_*.py",))

    assert resolved == ("custom_*.py",)


def test_resolves_to_the_real_detected_patterns_when_no_override_given(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/widget\n", encoding="utf-8")

    assert resolve_protected_patterns(tmp_path) == ("*_test.go",)


def test_raises_the_fail_closed_error_when_nothing_is_detected_and_no_override_given(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnrecognizedTestConventionError, match="Could not detect"):
        resolve_protected_patterns(tmp_path)
