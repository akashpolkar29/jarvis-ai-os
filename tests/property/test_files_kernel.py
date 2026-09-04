"""Property-based tests for jarvis.kernel.files's fs.delete_file/fs.move_file composition roots.

Mirrors tests/property/test_policy.py's own
test_manual_only_requires_physical_confirmation_specifically and
tests/property/test_communications_writer.py's own identical shape
(ADR-0059) -- the real, required proof ADR-0060 exists to guarantee:
fs.delete_file (Tier.MANUAL_ONLY) is denied whenever
physical_confirmation_available is False, remote confirmation
notwithstanding. Exercised through the real
authorize_and_delete_file/authorize_and_move_file composition-root
functions, not just the domain-level property test
tests/property/test_capability.py already covers.

A real tempfile.TemporaryDirectory() is created fresh inside each
Hypothesis example (not the pytest `tmp_path` fixture, which is
function-scoped and would be silently reused/stale across every
example @given generates) -- no real file is ever touched by either
composition function here (both fail-fast at the scope check or the
confirmation check before any real FileSystemPort method would run),
so this is fully hermetic despite the real directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from hypothesis import given
from hypothesis import strategies as st

from jarvis.kernel.files import authorize_and_delete_file, authorize_and_move_file

if TYPE_CHECKING:
    from jarvis.domain.file_system import DirEntry

CONFIRMATION_FLAGS = st.booleans()


class _StubFileSystem:
    """A minimal FileSystemPort test double -- no real filesystem I/O."""

    def read_text(self, path: Path) -> str:
        raise NotImplementedError

    def list_dir(self, path: Path) -> tuple[DirEntry, ...]:
        raise NotImplementedError

    def move(self, source: Path, destination: Path) -> None:
        del source, destination

    def delete(self, path: Path) -> None:
        del path


@given(CONFIRMATION_FLAGS, CONFIRMATION_FLAGS)
def test_delete_file_granted_tracks_physical_confirmation_alone(
    physical_confirmation_available: bool, remote_confirmation_available: bool
) -> None:
    """fs.delete_file's own real Decision.granted equals physical_confirmation_available alone."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        decision = authorize_and_delete_file(
            tmp_path / "note.txt",
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=_StubFileSystem(),
        )

    assert decision.granted == physical_confirmation_available


@given(CONFIRMATION_FLAGS, CONFIRMATION_FLAGS)
def test_move_file_granted_tracks_either_confirmation_channel(
    physical_confirmation_available: bool, remote_confirmation_available: bool
) -> None:
    """fs.move_file's own real Decision.granted is physical OR remote -- the ordinary CONFIRM floor."""  # noqa: E501
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        decision = authorize_and_move_file(
            tmp_path / "source.txt",
            tmp_path / "destination.txt",
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=_StubFileSystem(),
        )

    expected = physical_confirmation_available or remote_confirmation_available
    assert decision.granted == expected
