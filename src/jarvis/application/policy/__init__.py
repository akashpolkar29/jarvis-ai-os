"""Orchestrates authorization decisions.

Gathers a real ``PolicyContext`` from ports (e.g. presence signals),
constructs a ``CapabilityInvocation``, and calls the pure
``jarvis.domain.policy.evaluate()`` function -- which is the actual
decision logic -- then acts on the returned ``Decision`` (audit-logs
it, blocks, or prompts). This package contains no decision logic
itself.

This is currently an empty stub: the coverage gate for this package is
wired up in CI (``--fail-under=0`` for now) so that the reporting path
itself is exercised before this orchestration layer has any code in
it. The actual orchestration arrives in a later work package.
"""
