"""End-to-end smoke test: `python -m jarvis.cli` as a real, separate OS process.

Everything else about the CLI is tested more cheaply via direct
main(argv) calls in tests/unit/test_cli_main.py -- those exercise the
exact same argparse code path with none of the process-spawn cost.
This one test exists for a different reason: a direct call shares the
test process's already-successful import state, so it structurally
cannot catch packaging/entry-point-level breakage (a typo'd module
path, an import-time error only surfaced in a genuinely fresh
interpreter). A single real invocation catches that class of bug at
low, one-time cost.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def test_python_dash_m_jarvis_cli_runs_as_a_real_process(tmp_path: Path) -> None:
    """`python -m jarvis.cli` succeeds, prints the decision, and persists a chain file."""
    chain_path = tmp_path / "audit_chain.json"

    result = subprocess.run(
        [sys.executable, "-m", "jarvis.cli", "ping", "--chain-path", str(chain_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "ping: GRANTED" in result.stdout
    assert chain_path.exists()
