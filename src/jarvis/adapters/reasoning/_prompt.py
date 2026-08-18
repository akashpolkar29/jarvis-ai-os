"""Shared prompt construction for jarvis.adapters.reasoning.*.

Not a port and not part of any public API -- factored out purely so
``family_a.py``/``family_b.py``/``local.py`` don't each duplicate the
same prior-attempts-to-context folding logic. Pure and I/O-free,
directly unit-tested, matching ``_unwrap_reply``'s/``_find_secret_value``'s
role in the D-Bus adapters: the one piece of real logic here that CAN
be tested without a network call, kept separate from the parts that
can't.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt


def build_prompt(task: str, prior_attempts: tuple[Attempt, ...]) -> str:
    """Fold ``task`` and every prior attempt's outcome into one prompt string.

    A first attempt (``prior_attempts`` empty) is just ``task``,
    unchanged. Each later attempt appends its candidate's own content,
    verdict, and evidence descriptions, in order -- this is ADR-0022's
    self-repair feedback mechanism made concrete: what a real provider
    actually reads to learn what was already tried and why it failed.
    """
    if not prior_attempts:
        return task
    lines = [task, "", "Prior attempts at this task, in order:"]
    for index, attempt in enumerate(prior_attempts, start=1):
        lines.append(
            f"\nAttempt {index} (by {attempt.candidate.author}, verdict: {attempt.verdict.value}):"
        )
        lines.append(attempt.candidate.content)
        for evidence in attempt.evidence:
            lines.append(f"  - {evidence.description}")
    return "\n".join(lines)
