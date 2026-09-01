"""Property-based tests for jarvis.application.coding.writer.CodeWriteAuthorizer.

Mirrors tests/property/test_memory_writer.py exactly -- ADR-0056's own
required acceptance criterion, matching ADR-0038/ADR-0049's own rigor:
"a write to any path matching the real default protected_patterns
never reaches a real workspace at any rung, under any circumstance,
including physical_confirmation_available=True." Exercised through the
real CodeWriteAuthorizer/AuthorizationOrchestrator code path, not just
the domain-level property test tests/property/test_capability.py
already covers.
"""

from __future__ import annotations

import string
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.coding.writer import CodeWriteAuthorizer
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.policy import PolicyContext
from jarvis.domain.registry import CapabilityRegistry

CONTEXTS = st.builds(
    PolicyContext,
    physical_confirmation_available=st.booleans(),
    remote_confirmation_available=st.booleans(),
)

_PROTECTED_PATTERNS = ("test_*.py", "*_test.py", "tests/*")

FILE_STEMS = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10)


def _authorizer() -> CodeWriteAuthorizer:
    return CodeWriteAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


@given(CONTEXTS, FILE_STEMS)
def test_test_prefixed_path_is_never_written_under_any_circumstance(
    context: PolicyContext, stem: str
) -> None:
    """No PolicyContext, including full physical confirmation, can grant a test_*.py write."""
    decision = _authorizer().authorize_write(Path(f"test_{stem}.py"), _PROTECTED_PATTERNS, context)

    assert decision.granted is False


@given(CONTEXTS, FILE_STEMS)
def test_test_suffixed_path_is_never_written_under_any_circumstance(
    context: PolicyContext, stem: str
) -> None:
    """No PolicyContext, including full physical confirmation, can grant a *_test.py write."""
    decision = _authorizer().authorize_write(Path(f"{stem}_test.py"), _PROTECTED_PATTERNS, context)

    assert decision.granted is False


@given(CONTEXTS, FILE_STEMS)
def test_tests_directory_path_is_never_written_under_any_circumstance(
    context: PolicyContext, stem: str
) -> None:
    """No PolicyContext, including full physical confirmation, can grant a tests/* write."""
    decision = _authorizer().authorize_write(Path(f"tests/{stem}.py"), _PROTECTED_PATTERNS, context)

    assert decision.granted is False


@given(CONTEXTS, FILE_STEMS)
def test_ordinary_paths_float_at_code_writes_own_confirm_floor(
    context: PolicyContext, stem: str
) -> None:
    """Ordinary (non-protected) paths are gated by CODE_WRITE's own CONFIRM floor, not denied.

    Granted whenever *some* confirmation channel is available, matching
    Tier.CONFIRM's own evaluate() rule -- not a special restriction
    ADR-0056 adds beyond what an ordinary local write already required.
    """
    decision = _authorizer().authorize_write(Path(f"src/{stem}.py"), _PROTECTED_PATTERNS, context)

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted


@given(CONTEXTS, FILE_STEMS)
def test_empty_protected_patterns_never_denies_by_itself(context: PolicyContext, stem: str) -> None:
    """No configured protected_patterns at all means nothing is ever classified as protected."""
    decision = _authorizer().authorize_write(Path(f"test_{stem}.py"), (), context)

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted
