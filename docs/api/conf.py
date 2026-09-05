"""Sphinx configuration for JARVIS's real, generated API reference.

Generates real reference pages from the real docstrings already
present across src/jarvis/{domain,application,ports,adapters,kernel}
-- this surfaces what already exists, it does not add new prose. A
local, buildable HTML output under docs/api/_build/ is sufficient
(per this pass's own instruction) -- nothing here is hosted
externally.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

project = "JARVIS AI OS"
copyright = "2026, Akash Polkar"  # noqa: A001 -- Sphinx's own required config variable name
author = "Akash Polkar"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
# Real dataclasses across this codebase document their fields via a Google-
# style "Attributes:" docstring section (this project's own established
# convention, ruff's pydocstyle convention="google"). With the default
# napoleon_use_ivar=False, Napoleon renders that section as its own
# `.. attribute::` directive, which registers the same object autodoc's own
# real dataclass-field introspection already registers -- a genuine
# "duplicate object description" for every documented field, not a content
# problem. napoleon_use_ivar=True renders Attributes as a plain :ivar: field
# list instead, so only autodoc's real introspection registers the object.
napoleon_use_ivar = True

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_mock_imports = [
    "gi",
    "greenlet",
]

# Real, stdlib-only modules `domain`/`application`/`ports` never import GLib/GTK
# (enforced by lint-imports's own C6 contract) -- the mock list above only
# covers the real, optional desktop-adapter dependency so a documentation
# build never requires a real display/GTK4 runtime to succeed.

# Every one of domain/ports/application re-exports its own public names in
# its package __init__.py (e.g. `jarvis.domain.Segment` re-exporting
# `jarvis.domain.audio.Segment`) -- a deliberate, real convention, not an
# accident. autodoc_typehints then finds two equally-valid targets for the
# same name and cannot pick one, which is a structural artifact of that
# convention, not a missing/stale docstring -- confirmed by checking that no
# other warning class appears in a real build (see docs/threat-model/v0.md's
# own Phase 3 note). Suppressed rather than chased one by one.
suppress_warnings = ["ref.python"]

templates_path: list[str] = []
exclude_patterns: list[str] = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path: list[str] = []
