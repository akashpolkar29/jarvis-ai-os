"""A real, minimal, working example plugin -- proves jarvis.plugin_api is real and sufficient.

**What this file proves (10-phase combined pass, Phase 8, 2026-09-05)**:
before this pass, ``jarvis.plugin_api`` was a docstring with no real
content, and this repo's own plugin guide (``README.md``, same
directory) honestly stated it "has no real content yet." This file is
the first real capability description built *only* against
``jarvis.plugin_api`` -- no ``jarvis.application``, ``jarvis.adapters``,
``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli`` import anywhere
below. ``tests/meta/test_plugin_api_example.py`` mechanically checks
this file's own real imports (an AST scan, not a read-and-trust), and
separately proves the descriptor this file builds authorizes correctly
end to end through a real, freshly-built ``CapabilityRegistry`` and
``AuthorizationOrchestrator`` -- the same mechanical-proof discipline
``tests/meta/test_speaker_id_isolation.py`` already established for a
different guarantee.

**What this does NOT prove, stated plainly**: this capability is never
registered in ``kernel/capabilities.py``'s real
``build_default_registry()`` -- it is illustrative only, not a shipped
feature. Wiring a new capability into the real, running kernel today
still means editing a file inside this source tree (this repo has no
dynamic, out-of-tree plugin loading) -- exactly what
``docs/plugin-guide/README.md`` already says, unchanged by this file.

**The capability itself**: ``example.word_count`` counts words in a
caller-supplied string. Chosen deliberately trivial and side-effect-free
so the *plugin-authoring* pattern is what's on display, not a real
feature. ``Effect.READ_LOCAL`` (floors ``Tier.ALLOW``) is the honest
choice, mirroring ``memory.retrieve``'s own "the bare act of querying"
reasoning (`kernel/memory.py`'s own docstring) -- this is a pure
computation over a caller-supplied value, not a write, not code
execution, and not extracting separately-stored content the way
``fs.read_file``'s ``EGRESS_LOCAL`` does.
"""

from __future__ import annotations

from jarvis.plugin_api import CapabilityDescriptor, CapabilityId, Effect

EXAMPLE_WORD_COUNT_CAPABILITY_ID = CapabilityId("example.word_count")


def build_example_word_count_descriptor() -> CapabilityDescriptor:
    """Return the real CapabilityDescriptor for `example.word_count`.

    A plugin author calls this (or the equivalent inline construction)
    and passes the result to a real `CapabilityRegistry.register()`
    call -- the one step this file cannot itself demonstrate, since
    registering into the *real, running* registry happens in
    `kernel/capabilities.py`, inside this source tree (see this
    module's own docstring for why that boundary still exists today).
    """
    return CapabilityDescriptor(
        id=EXAMPLE_WORD_COUNT_CAPABILITY_ID,
        effects=Effect.READ_LOCAL,
        description="Count the words in a caller-supplied string. A real, minimal example plugin.",
    )


def count_words(text: str) -> int:
    """The real, pure handler a granted `example.word_count` invocation would call.

    No I/O, no adapter, no port -- deliberately as simple as a real
    capability's own "do the thing" logic can be, so this file's
    entire point (the plugin-authoring surface, not the feature) stays
    the focus.
    """
    return len(text.split())
