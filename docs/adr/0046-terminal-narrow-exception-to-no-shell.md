# ADR-0046: Terminal control is a narrow, deliberate exception to "no shell"

## Status

Accepted

## Date

2026-08-24

## Source

`docs/architecture/m3-desktop-control.md` deliverable #7 and "Non-goals" section (design decided in conversation before that document was drafted); promoted to a real ADR before WP-52 implementation, per CLAUDE.md's hard rule.

## Context

ADR-0003 ("No shell: capabilities declare typed effects instead of commands") and ADR-0007 ("No command blocklists, ever") together establish this kernel's foundational discipline: a capability is a fixed, typed, pre-approved operation, never a channel for arbitrary text a caller (human or model) supplies to be interpreted as a command. Every capability built through M0/M1/M2 -- `music.*`, `fs.read_file`, every M2 validator's subprocess call -- honors this: the *command* is fixed at the adapter level; only *arguments* (a file path, a patch) are caller-supplied, and those arguments are typed, not shell-interpreted text.

M3's Terminal deliverable cannot honor this the same way. "Control a terminal emulator" means injecting keystrokes (via `DesktopWindowPort.type_text`) into a real terminal's input, which the terminal then interprets as a shell command line -- functionally equivalent to shell execution, regardless of what typed wrapper JARVIS puts around the call. Disguising this as a bounded, typed capability the way Git/Docker's operations are (a fixed docker/git argv, caller supplies only typed arguments) would be dishonest: there is no way to "type text into a terminal" that isn't, in effect, "run whatever shell command that text spells out."

This is a real, load-bearing tension with ADR-0003/ADR-0007, not a minor implementation detail -- it needs its own ADR precisely because it is the one place in this codebase's real capability set where the "no shell" principle is knowingly not honored in the usual way, and a future session encountering `terminal.run`'s implementation without this ADR could reasonably conclude the "no shell" principle has quietly eroded, or use `terminal.run` as precedent to justify a second free-text-command capability elsewhere.

Confirmed live during WP-43's spike: `gnome-terminal` (`/usr/bin/gnome-terminal`) is installed as a native, non-snap binary on this development machine -- distinct from Brave and VS Code, both confirmed to be snap-confined (`snap list` shows `brave`/`code` as snap packages; a live AT-SPI2 `GetItems` call against Brave's accessible tree was denied by the snap D-Bus proxy during the same spike, independent of any AppArmor policy on Brave itself). A native terminal emulator avoids that specific denial class for JARVIS's own control of it, though whether `gnome-terminal` (or any terminal emulator) exposes a usable AT-SPI2 text buffer for real output capture remains genuinely unconfirmed until WP-52's own implementation checks it directly -- not assumed here.

## Decision

`terminal.run` is accepted as a real, narrow, explicitly-flagged exception to ADR-0003/ADR-0007, bounded by three structural mitigations, all mandatory, none merely documented:

1. **`Effect.DESTRUCTIVE | Effect.EXECUTE`, unconditionally `Tier.MANUAL_ONLY`, on every single invocation.** No standing grant, no `CONFIRM`-tier fast path, regardless of what command text is being sent -- since JARVIS cannot classify the risk of free-text shell input in advance (that is precisely what a command blocklist would attempt, and ADR-0007 already forecloses that approach), the only honest floor is the tier requiring a human physically present to authorize *this specific* invocation, every time.
2. **The terminal JARVIS controls must be one it launches itself, inside a `SandboxPort`-wrapped `bwrap` invocation (ADR-0044) -- never keystroke injection into an arbitrary, already-running terminal window the user happens to have open.** A pre-existing terminal's process tree, working directory, and shell state are outside any containment JARVIS can retroactively apply; only a freshly-launched, sandboxed terminal has bounded blast radius from the moment it exists. This is checked structurally, not merely documented: no code path in `terminal.run`'s implementation may reach `DesktopWindowPort.type_text` against a window handle that did not originate from that same invocation's own `SandboxPort.run()` call.
3. **Output capture is explicitly best-effort, never a security boundary.** `DesktopWindowPort.read_visible_text`'s result, if any, is tagged `Trust.UNTRUSTED_EXTERNAL` per ADR-0011 unconditionally -- terminal output is exactly the class of content (this process did not generate it and must not implicitly trust it) ADR-0011 already names, regardless of how trustworthy the original command seemed.

No other capability in M3, or any future milestone, may cite `terminal.run` as precedent for relaxing `Effect`'s typed-capability discipline elsewhere. This is a narrow exception scoped to the one place a general-purpose terminal genuinely cannot be made typed without stopping being a terminal, not a reusable pattern.

## Consequences

`terminal.run` is the single highest-risk capability this milestone registers -- the acceptance criteria in `m3-desktop-control.md` already single it out (#3, #4) for exactly this reason. Its `MANUAL_ONLY` floor means it is unusable by JARVIS without a human physically present and willing to authorize each invocation; this is intentional friction, not an oversight to be smoothed over in a later milestone.

This does not, and must not, become a precedent: a future capability wanting "run this one particular thing" should almost always be a typed capability with a fixed argv (Docker/Git's own shape), not a `terminal.run`-style free-text channel. If a future session is tempted to add a second free-text-command capability by pointing at `terminal.run`'s existence, that is exactly the drift this ADR exists to name and block -- re-read this document rather than re-deriving the exception from scratch.
