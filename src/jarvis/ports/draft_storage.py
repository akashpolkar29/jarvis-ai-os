"""The draft storage port: the seam between a drafted document and a real file (WP-82, pending).

Skeleton module, deliberately empty of real logic -- see
``src/jarvis/application/job_assistance/__init__.py``'s own docstring
for why the structural meta-test lands before any real capability code
does. ``DraftStoragePort`` (one method, ``save(filename_hint, content)
-> Path``) is built for real in WP-82, per
``docs/architecture/m6b-job-assistance.md``'s own specified shape.
"""

from __future__ import annotations
