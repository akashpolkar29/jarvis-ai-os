"""Plugin API: the stable surface third-party capability plugins build against.

Plugins are how new features enter JARVIS — the kernel itself knows only
about capabilities, never about specific agents or integrations. This
subpackage is the contract a plugin author imports against, and it is
deliberately kept minimal and stable.

Constraints:

* May depend on ``jarvis.domain`` only (import-linter contract
  "C7 plugin_api depends only on domain"). A plugin author must never
  need to reach into ``jarvis.application``, ``jarvis.adapters``,
  ``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli``.

**Real content, added 2026-09-05 (10-phase combined pass, Phase 8)**:
before this pass, this module was a docstring only -- the exact
vocabulary a plugin author needs to *describe* a new capability
(build a ``CapabilityDescriptor``, construct correctly-provenanced
``Tainted`` argument values, and understand the ``Decision`` a real
authorization call returns) had no single, stable place to import from
other than reaching into ``jarvis.domain`` submodules directly, which
this package's own docstring already said a plugin author should never
need to do. The re-exports below are a deliberately narrow subset of
``jarvis.domain``'s own full surface: reasoning-layer-specific types
(``Attempt``, ``Candidate``, ``Verdict``, audio/transcript/wake-word
types) are not a capability-authoring concern and are left out.

**What this does NOT yet solve, stated plainly, matching
``docs/plugin-guide/README.md``'s own long-standing, honest
disclaimer**: there is still no dynamic plugin loading from disk.
Wiring a new ``CapabilityDescriptor`` into the real, running registry
(``kernel/capabilities.py::build_default_registry()``) still requires
editing a file inside this source tree -- this module gives a plugin
author the domain vocabulary to *describe* a capability without ever
importing ``application``/``adapters``/``kernel``, proven for real by
``docs/plugin-guide/example_plugin.py`` and its own meta-test
(``tests/meta/test_plugin_api_example.py``), not a claim that
third-party, out-of-tree plugin loading now exists -- it does not.
"""

from jarvis.domain import (
    CapabilityAlreadyRegistered,
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    CapabilityNotRegistered,
    CapabilityRegistry,
    Classification,
    Decision,
    DecisionReason,
    Effect,
    JarvisError,
    PolicyContext,
    Provenance,
    Tainted,
    TaintViolation,
    Tier,
    Trust,
    evaluate,
    minimum_tier_for,
)

__all__ = [
    "CapabilityAlreadyRegistered",
    "CapabilityDescriptor",
    "CapabilityId",
    "CapabilityInvocation",
    "CapabilityNotRegistered",
    "CapabilityRegistry",
    "Classification",
    "Decision",
    "DecisionReason",
    "Effect",
    "JarvisError",
    "PolicyContext",
    "Provenance",
    "TaintViolation",
    "Tainted",
    "Tier",
    "Trust",
    "evaluate",
    "minimum_tier_for",
]
