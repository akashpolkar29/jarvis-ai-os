# Dynamic/out-of-tree plugin loading scoping notes — investigated, not decided

**Status: research only. No decision made, nothing built.** No code
was written for this document — no port, no adapter, no application
module, no capability, no ADR, no loader. Mirrors `m7-scoping-notes.md`'s
own precedent exactly. Written 2026-09-07.

## The one finding that matters more than the options below

**Dynamic plugin loading, in the ordinary sense every option below
means by it — importing a third party's Python code into this same
process — is fundamentally in tension with the capability system
being a reliable security boundary, not merely a new risk surface to
manage.** This is stated first, prominently, for the same reason the
job-search ToS finding was: the options that follow are real and
worth having, but none of them, by itself, closes this specific gap.

The reasoning, checked directly against the real code, not assumed:

- `CapabilityRegistry.register()` (`domain/registry.py`) checks
  exactly one thing — that the id isn't already taken
  (`CapabilityAlreadyRegistered`). It has no mechanism, and by its own
  design *cannot* have one, to check whether a `CapabilityDescriptor`'s
  declared `Effect` set honestly describes what the capability's real
  composition function actually does. A descriptor is inert data; the
  real behavior lives in a separate Python callable the registry never
  inspects. Every in-tree capability's honesty today comes from a
  human reviewing the pull request that added it — a real, working
  control, but one that is structurally a *code-review* property, not
  a *registry* property. `docs/plugin-guide/README.md`'s own text
  already states the taxonomy is "closed, extended only via a new ADR,
  never ad hoc" — that discipline holds only as long as a human is
  actually reading the diff.
- The single most dangerous shape this enables: a plugin registers a
  `Tier.ALLOW` capability whose real Effect is destructive.
  `domain/policy.py::evaluate()` hardcodes `granted=True` for
  `Tier.ALLOW` unconditionally — no confirmation is ever consulted.
  An out-of-tree plugin that mislabels its own capability this way
  (deliberately or through an honest author's own mistake) would
  execute completely silently, with no user-visible gate at all,
  exactly the failure mode this project's entire tier system exists to
  prevent for in-tree capabilities.
- **The deeper problem, which no registration-time check can fix**:
  once arbitrary third-party Python code is imported into this same
  process (which is what every ordinary Python plugin mechanism — entry
  points, a scanned directory, `importlib.import_module` on an
  explicit name — actually does), that code runs with the *same
  process privileges JARVIS itself has*, starting at import time,
  before it ever registers a single capability. Python has no
  in-process privilege separation: a plugin module's own top-level code
  (or any function it exposes, called from anywhere, not just through
  the capability system) can read arbitrary files, open network
  sockets, or read environment variables/secrets exactly as freely as
  any other code running in that interpreter. Declaring an honest,
  correctly-classified `CapabilityDescriptor` says nothing about what
  the *rest* of that plugin's own code does — the capability system
  governs one declared entry point, not the process. This is not a gap
  in any of the three loading mechanisms named below; it is a property
  of same-process Python plugin loading itself, and none of them
  change it.

**What this does and doesn't rule out**: it does not mean dynamic
plugin loading can never be built — it means that building it as "make
`jarvis.plugin_api` importable and load whatever registers against it"
is a materially different, larger security commitment than the
existing, reviewed, in-tree capability model, and should not be
presented as a smaller step than it actually is.

## Option 1 — entry-points-based discovery

**Shape**: a pip-installed plugin package declares itself under a
real, standard entry-point group (e.g. `[project.entry-points.
"jarvis.plugins"]` in its own `pyproject.toml`, the same mechanism
`pytest`/`flake8`/many real Python tools already use for their own
plugin ecosystems). At startup, a new loader enumerates
`importlib.metadata.entry_points(group="jarvis.plugins")`, imports
each, and expects each to expose whatever real registration shape is
decided (e.g. a `CapabilityDescriptor` plus a composition function).

**Real tradeoffs**: the most "batteries included" option — real
versioning, real dependency management via the plugin's own
`pyproject.toml`, a familiar pattern for any Python developer. Also
the *widest* real attack surface of the three: any package installed
into the same Python environment that happens to declare that entry
point group loads automatically, with no per-plugin, per-machine
opt-in step beyond `pip install`ing it — including transitively, if a
plugin is itself a dependency of something else installed for an
unrelated reason.

## Option 2 — a configured plugin directory scanned at startup

**Shape**: a real, fixed path (e.g. `~/.config/jarvis/plugins/`) is
scanned for `.py` files at startup, each loaded via
`importlib.util.spec_from_file_location`. No packaging or
distribution mechanism needed — a plugin author drops a file in a
folder.

**Real tradeoffs**: simpler to implement than Option 1, no dependency
on Python packaging metadata. Real, added risk specific to this shape:
a directory is a much easier accidental or malicious drop target than
a `pip install` step (a downloaded file, an extracted archive, or a
compromised sync tool could place a file there without the user ever
running an explicit install command) — the "install" step Option 1 at
least requires (however weak a gate) doesn't exist here at all.

## Option 3 — explicit opt-in registration by name

**Shape**: a real, user-edited config (e.g.
`~/.config/jarvis/plugins.toml`) lists the exact, importable module
path of every plugin to load (`"my_jarvis_plugin.capabilities"`), one
line per plugin, typed or pasted in by the user themselves. Nothing is
auto-discovered — a plugin must already be installed and importable
via ordinary Python mechanisms (`pip install` or otherwise on
`sys.path`), and JARVIS never scans a directory or an entry-point
registry on its own.

**Real tradeoffs**: the strongest "nothing loads without explicit,
individual, per-plugin opt-in" property of the three — a user must
name each plugin themselves, which at minimum makes "what plugins are
loaded" fully legible from one config file, and forecloses the
"transitively installed, auto-discovered" risk Option 1 has and the
"dropped file" risk Option 2 has. Does not, on its own, solve the
same-process-code-execution problem named above — an explicitly-named
plugin is still arbitrary Python code running in the same process once
loaded. Real, added friction: no automatic discovery means a plugin
author must document the exact importable path for a user to type,
slightly worse first-run ergonomics than Options 1/2.

## Real, additional mitigations investigated, independent of which loading mechanism is chosen

- **A structural tier floor for any dynamically-loaded capability**:
  regardless of what `Effect` a plugin's own `CapabilityDescriptor`
  claims, the loader could unconditionally force a minimum tier (e.g.
  never below `Tier.CONFIRM`) for anything it loads — a real,
  enforceable rule checked at load time (comparing "did this
  descriptor come from `build_default_registry()`'s own in-tree call
  sites, or from the dynamic loader" — a real, checkable distinction
  since the loader would be the one place dynamically-loaded
  descriptors ever enter the registry). This closes the specific
  "silent `Tier.ALLOW` plugin" failure mode named above, without
  requiring any deeper sandboxing. **Does not** address the
  same-process code-execution problem — a forced `Tier.CONFIRM` floor
  governs the capability's own *declared* action; it does nothing
  about what else that plugin's own code does outside the capability
  system.
- **Sandboxing plugin code execution itself, not just its declared
  capability's tier**: this project already has a real, working
  precedent for exactly this shape of containment —
  `ports/sandbox.py`/`adapters/sandbox.py`'s real
  `BwrapSandboxAdapter`, used today to contain the coding agent's own
  real, potentially-adversarial file writes (ADR-0044). An analogous
  design would run plugin code in a genuinely separate, sandboxed
  process (network/filesystem isolation, `bwrap`) rather than
  importing it into the main JARVIS process at all, communicating over
  some real IPC boundary rather than a plain Python function call.
  This is the only option investigated here that actually closes the
  same-process problem — and it is also, honestly, no longer "add a
  loader" in scope: it is closer to a new, distinct architectural
  layer (a real plugin RPC boundary), a materially larger undertaking
  than any of Options 1-3 above, not attempted or designed further in
  this document.
- **A real, out-of-scope alternative worth naming**: requiring
  plugin code review before first load (a real human reads the
  plugin's source once, the same review in-tree capabilities already
  get, before the user opts in) would restore the actual control that
  makes in-tree capabilities trustworthy today — but this is a process
  commitment, not a technical mechanism any of Options 1-3 provide on
  their own, and doesn't scale the same way an automated loader
  implies "plugins" should.

## Summary

| Option | Real attack-surface shape | Requires a new architectural layer? |
| --- | --- | --- |
| 1. Entry points | Widest — transitive, automatic | No |
| 2. Scanned directory | Wide — no install step at all | No |
| 3. Explicit opt-in by name | Narrowest of the three loading mechanisms | No |
| Tier floor for dynamic descriptors | Closes one specific failure mode (silent `ALLOW`) | No |
| Process-level sandboxing | Closes the actual same-process problem | Yes — a real, separate undertaking |

No recommendation is made here; this is options-on-the-table work for
the user's own decision, exactly like `m7-scoping-notes.md`'s own
precedent. The one finding stated at the top is not an option among
these — it is a real constraint any final decision needs to be made
with, not around.
