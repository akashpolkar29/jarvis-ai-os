# ADR-0045: Claude desktop app / ChatGPT desktop app -- ordinary control only

## Status

Accepted

## Date

2026-08-24

## Source

`docs/architecture/m3-desktop-control.md` "Non-goals" section (design decided in conversation before that document was drafted); promoted to a real ADR per WP-43's own ADR-list item, before any WP-51 implementation.

## Context

M3 controls the Claude desktop app and the ChatGPT desktop app as two of its eight target applications. Both are, mechanically, just another `DesktopWindowPort`-controlled application -- open it, bring it to front, type into its input box. But both also happen to be chat interfaces to a capability (a reasoning model) this project already has a real, metered, policy-gated abstraction for: `ReasoningPort` (M2, ADR-0020). That proximity creates a real temptation for a future session: since M3 already controls these two apps' windows, it would be a small step to also read back their responses (`DesktopWindowPort.read_visible_text` already exists for Terminal's sake) and treat that as a second, free `ReasoningPort`-equivalent.

This exact pattern -- scripting a consumer chat app to extract AI responses at scale, as an alternative to metered API access -- was proposed and explicitly declined once already, during M2's own live-verification consolidation pass, for two independent reasons that apply with equal force here:

1. It is a fundamentally different kind of integration (UI automation against someone's logged-in consumer session) from the HTTP-client shape `ReasoningPort`'s real adapters (`family_a`, `family_b`, `local`) are built around -- not a small extension of anything this milestone or M2 builds, a different trust and reliability model entirely.
2. It is very likely a Terms-of-Service violation for whoever's account performs it, on both platforms -- a real risk to a real account (the user's own) that this project should never impose unilaterally, and categorically different from ordinary UI automation of a locally-installed application the user already owns and controls.

`m3-desktop-control.md` already states this boundary in prose, in its own "Non-goals" section. This ADR exists because CLAUDE.md's hard rule requires a real architectural/scope decision like this to have a real ADR, not just design-doc prose -- and because a future session, encountering the already-built `DesktopWindowPort.read_visible_text` method and the already-controlled Claude/ChatGPT windows, is exactly the kind of context in which this boundary could be silently re-derived away without ever seeing why it was drawn.

## Decision

The Claude desktop app and ChatGPT desktop app are in scope, in M3 and every future milestone, for ordinary application control only: open/launch the app, bring its window to front, and type text into whatever input box currently has focus, on explicit user command -- via `DesktopWindowPort`, identical in shape to Brave/VS Code's own ordinary-control capabilities.

**No capability registered for either app may call `DesktopWindowPort.read_visible_text`.** This is enforced at the capability-registration level (`kernel/capabilities.py`), matching this kernel's existing "capabilities not agents" discipline (ADR-0002): the port itself stays generically useful (Terminal's own output-capture need is real and legitimate), but which capabilities are *registered* to call which port methods, for which app, is where the restriction actually lives. `tests/meta/test_no_response_scraping.py` (WP-51) enforces this structurally, the same class of AST/grep meta-test `tests/meta/test_speaker_id_isolation.py` already uses for ADR-0012's speaker-verification isolation and `tests/meta/test_source_invariants.py` already uses for ADR-0021's vendor-name grep -- not a code-review convention, a test that fails the build if violated.

No capability for either app may authenticate, log in, accept a ToS prompt, manage API keys, or otherwise persist new state to the underlying account. "Ordinary control" is scoped exactly to what a sighted human clicking the dock icon and typing into the visible chat box would do -- nothing that reads the app's response, drives a multi-turn conversation automatically, or treats the app as a programmable endpoint.

## Consequences

M2's `ReasoningPort` remains the only sanctioned path from this codebase to a reasoning model. Any future work that wants cheaper or higher-limit model access must extend `ReasoningPort` with a real adapter (a third cloud-provider family, a different pricing tier of an existing one) -- never route around it through desktop-app automation, regardless of how convenient the already-built `DesktopWindowPort` machinery makes that look.

This forecloses, deliberately: automated response reading from either app, multi-turn scripted conversations with either app, and any characterization of Claude-app/ChatGPT-app control as "a reasoning capability" anywhere in `domain`/`application`/`ports` (which ADR-0021's vendor-name grep already keeps vendor-free regardless).

If a future session has a genuine, reconsidered reason to revisit this boundary, it requires a fresh ADR explicitly superseding this one, with the account-risk and ToS considerations above addressed head-on -- not a quiet capability addition that technically satisfies the letter of "ordinary control" while defeating its purpose.
