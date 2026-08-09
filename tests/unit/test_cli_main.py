"""Unit tests for jarvis.cli.main.main, called directly with explicit argv (no subprocess)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.cli.main import main

if TYPE_CHECKING:
    import pytest


def test_main_default_flags_grants_and_exits_zero(tmp_path: Path) -> None:
    """With no flags, ping is granted and main() returns 0."""
    chain_path = tmp_path / "audit_chain.json"

    exit_code = main(["--chain-path", str(chain_path)])

    assert exit_code == 0


def test_main_prints_the_decision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main() prints granted status, tier, and reasons for a human to read."""
    chain_path = tmp_path / "audit_chain.json"

    main(["--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert "ping" in captured.out
    assert "GRANTED" in captured.out
    assert "ALLOW" in captured.out


def test_main_with_confirmation_flags_still_grants(tmp_path: Path) -> None:
    """Both confirmation flags can be set without error; ping is still granted."""
    chain_path = tmp_path / "audit_chain.json"

    exit_code = main(
        [
            "--physical-confirmation-available",
            "--remote-confirmation-available",
            "--chain-path",
            str(chain_path),
        ]
    )

    assert exit_code == 0


def test_main_persists_the_chain_at_the_given_path(tmp_path: Path) -> None:
    """main() saves the chain at --chain-path, readable by a fresh adapter afterward."""
    chain_path = tmp_path / "audit_chain.json"

    main(["--chain-path", str(chain_path)])

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1


def test_main_default_chain_path_is_relative_audit_chain_json(tmp_path: Path) -> None:
    """Omitting --chain-path falls back to ./audit_chain.json in the current directory."""
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        exit_code = main([])
    finally:
        os.chdir(original_cwd)

    assert exit_code == 0
    assert (tmp_path / "audit_chain.json").exists()


def test_main_reports_a_tampered_chain_cleanly_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tampered chain file surfaces as a clean error message, not a raw traceback.

    JarvisError exists precisely so a caller can catch "any domain-level
    problem" without committing to a specific failure mode -- this is
    that catch actually being exercised.
    """
    chain_path = tmp_path / "audit_chain.json"
    main(["--chain-path", str(chain_path)])
    raw = json.loads(chain_path.read_text(encoding="utf-8"))
    raw[0]["record_hash"] = "0" * 64
    chain_path.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = main(["--chain-path", str(chain_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err
