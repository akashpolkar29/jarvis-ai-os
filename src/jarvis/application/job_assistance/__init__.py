"""M6b job assistance: research and drafting only, no auto-apply (ADR-0058).

Skeleton package, created first, deliberately empty of real capability
logic -- this project's own established discipline (WP-58 before M4's
other work, WP-70 before WP-71 for M5) puts the safety-critical piece
first: ``tests/meta/test_job_assistance_no_submission.py`` is written
and proven (passes against this skeleton, catches a deliberate
violation) before any real drafting/research code lands here. See
``docs/adr/0058-m6b-no-auto-apply-is-a-structural-boundary-not-a-policy-tier-gate.md``
(Accepted) and ``docs/architecture/m6b-job-assistance.md`` for the
real design this package fills in, one real work package at a time.
"""

from __future__ import annotations
