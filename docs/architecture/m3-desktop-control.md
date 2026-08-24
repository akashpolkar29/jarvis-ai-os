# JARVIS — M3: Desktop Control

**Status: real design, written 2026-08-21, not a placeholder.** M3 has
no recovered original-design-conversation fragments the way M0/M1/M2
did — nothing analogous was ever found in this repository or its
history (checked exhaustively: full git log of this file, repo-wide
grep for every app/mechanism name, before this pass started). This
document is genuinely new design work, produced against real repo
state as it exists after M2 (`v0.3.0`), not a reconciliation of
recovered material. Scope decisions in this document were made in
conversation with Akash directly, not invented unilaterally — three
genuine ambiguities (Terminal's mechanism, M2-retrofit scope, M3/M5
overlap) were surfaced and resolved with his explicit direction before
any of the rest of this document was drafted; that resolution is
recorded inline at each relevant section, not hidden.

## Objective

Desktop control: portal + libei, X11 fallback, AT-SPI2. Out-of-process
plugin host + `bwrap` sandboxing. Eight real applications: Brave, VS
Code, Spotify, Terminal, Docker, Git, the Claude desktop app, the
ChatGPT desktop app.

## Entry gate

M0, M1. (M2 is not a hard dependency — see "Relationship to M2"
below — but is complete as of this writing, `v0.3.0`.)

## Exit gate

`DesktopControlPortContract` green on both Wayland and X11; moving
plugins out-of-process requires zero plugin changes; every
`DESTRUCTIVE`/`IRREVERSIBLE` desktop-control capability is
demonstrably gated `MANUAL_ONLY` through the real
`AuthorizationOrchestrator`, not a new or parallel authorization path.

## Complexity

XL, 25–35 ideal-days (unchanged from the original placeholder
estimate — nothing in this design pass found reason to revise it).

## Known risks

Highest-uncertainty milestone in the project so far — portal behavior
varies by compositor, the libei Python binding situation is young.
This is not a new concern this pass invented: it was already named in
the placeholder this document replaces, and M2's own experience (WP-28's
skipped reasoning-provider PoC, felt as a real gap later — see
`docs/threat-model/v0.md`'s "Live verification of the reasoning
adapters") is the direct reason WP-43 below is a dedicated feasibility
spike *before* any port signature is committed to, rather than a port
designed first and validated later.

## Relationship to M2

M2 has no dependency on M3, and M3 does not call into M2's reasoning
layer. The real dependency direction, confirmed against actual code:
capabilities are *consumed by* reasoning output (a `Candidate`'s
content could, in a future dispatcher extension, name a capability to
invoke), never the reverse — `ReasoningPort`, `ValidationPort`,
`Dispatcher`, and everything in `application/reasoning/` are
unmodified by this document and do not need to be. The one real,
explicit exception, decided in conversation before this document was
drafted: M2 already shipped three unsandboxed validators
(`RuntimeCheckValidator`, `PytestValidator`, `UserScriptValidator`,
flagged in `docs/threat-model/v0.md`'s "candidate execution is not
sandboxed" gap) that this milestone's sandboxing work *could* retrofit.
**Decided: it does not.** M3 builds `SandboxPort` as reusable,
general-purpose infrastructure; retrofitting M2's validators onto it
is named here as a real, tracked, explicit follow-up (see "Deferred,
not forgotten" below), not one of this milestone's own work packages.
Keeping M3 scoped to desktop control, not quietly expanding into "M2
hardening," was the deciding reasoning.

## Non-goals

**The Claude desktop app and ChatGPT desktop app are in scope for
ordinary application control only: open the app, bring it to front,
type into its input box on explicit user command.** They are
**not** in scope, in this milestone or any future one without a fresh,
explicit decision, as a reasoning-engine substitute. This document
does not design, and no future work package under this milestone may
build, anything that scripts either app to extract AI responses at
scale, drive multi-turn automated conversations, or otherwise use a
consumer chat subscription as an unofficial replacement for M2's real,
metered `ReasoningPort` adapters. This exact pattern was proposed and
explicitly declined during M2's own live-verification consolidation
pass, for two independent reasons that apply with equal force here:
it would be a fundamentally different kind of integration (browser/app
automation, not the HTTP client `ReasoningPort` is built around) not a
small extension of anything this milestone builds, and it is very
likely a Terms-of-Service violation for whoever's account performs
it — a risk to a real account this project should never impose
unilaterally. Any future session tempted to connect "M3 already
controls the Claude/ChatGPT apps" to "therefore M2 could just drive
them instead of paying for API access" should stop and re-read this
paragraph rather than re-deriving the question from scratch.

**Terminal control is a deliberate, narrow exception to this
project's "no shell" principle, not a precedent for a general command-
execution capability.** See "Terminal" below for the full reasoning
and the specific mitigations (sandboxed launch, `MANUAL_ONLY` on every
single invocation, never a standing grant) that make this exception
survivable. No other capability in this document, or any future one,
should read "Terminal has shell-like access" as license to relax
`Effect`'s typed-capability discipline anywhere else.

**Brave and VS Code get ordinary application control only in this
milestone — not the deep, CDP/LSP-driven automation `docs/ROADMAP.md`'s
M5 row already names.** See "Relationship to M5" below.

## Relationship to M5

`docs/ROADMAP.md`'s M5 row states: *"Browser via CDP. Coding
capabilities via LSP + git."* Checked directly against this
milestone's original app-scope decision (Brave, VS Code, CDP proposed
for Brave): both Brave and VS Code, read literally, would duplicate
M5's already-documented scope, not just VS Code as first suspected —
"Browser via CDP" is an exact phrase match against what this document
was first asked to design for Brave.

**Decided (in conversation, before drafting): a shallow/deep split.**
M3 gets *ordinary* application control for both — the same bounded
shape as the Claude/ChatGPT non-goal above: launch or focus the app,
navigate to a URL (Brave) or open a file (VS Code). M5 keeps the
*deep*, autonomous-agent-driven work: real CDP-based page inspection
and JavaScript execution for Brave, real LSP-server communication for
VS Code's "coding capabilities" — neither of which this milestone's
adapters touch at all. This split resolves cleanly at the *mechanism*
level, not just the scope-ownership level, once checked against real
tooling on this machine: `brave-browser <url>` and `code <path>` are
real, already-installed CLI commands (confirmed present:
`/usr/bin/brave-browser`, `/snap/bin/code`) that both browsers/editors
already implement as single-instance-activation entry points — opening
a URL or a file in an already-running instance reuses the existing
window via the application's own IPC, with **no CDP or LSP dependency
at all** for this milestone's bounded scope. `WorkspacePort`'s own
precedent (a real `git apply` subprocess call, ADR-0043) already
established that "shell out to a well-known CLI with a fixed,
non-shell-injectable argument list" is an accepted pattern in this
codebase; this reuses it, not the deep protocols M5 will need.

## Scope: deliverables

Nine deliverables: eight apps plus the sandboxing mechanism, ordered
by real dependency, not app-list order.

### Foundational

1. **`DesktopWindowPort`** — the one abstract boundary between "some
   real, running desktop application's window" and every UI-automation
   capability this milestone builds (Brave, VS Code, Terminal, Claude
   app, ChatGPT app — five of the eight apps genuinely need this;
   Spotify, Docker, Git do not). A single port, one adapter, internally
   branching on Wayland-portal-plus-libei versus X11-plus-AT-SPI2
   rather than exposing that branch to callers — matching how every
   other port in this repo hides its real technology choice behind
   one seam (`SttPort` doesn't expose "which model," `MediaPlayerPort`
   doesn't expose "which transport"). Real methods, informed by
   WP-43's PoC findings, not committed to before that spike runs:
   *find/launch a window by application id, focus it, inject text into
   whatever currently has input focus, and — best-effort, not
   guaranteed, since it depends on a specific app's own AT-SPI2
   support — read back visible text.* `read_visible_text` exists on
   the port because Terminal's own output-capture need is real, not
   because every app that uses this port gets a capability that calls
   it: **restriction is enforced at the capability-registration level
   (which capabilities exist for which app), not by refusing to build
   a generically useful port method** — the same "capabilities not
   agents" reasoning that already governs this whole kernel. Content
   read back through this port is tagged `Trust.UNTRUSTED_EXTERNAL`
   uniformly (ADR-0011: this is exactly the class of content — a web
   page, a terminal's own command output, an accessibility tree
   populated by an application this process does not control — that
   ADR already names), regardless of which app it came from.

2. **`SandboxPort`** — real command containment via `bwrap`
   (confirmed present and working on this machine: `bubblewrap 0.9.0`),
   the mechanism this milestone's own placeholder objective already
   named before this design pass started, not something invented
   fresh here. One method: run a command inside a real, unprivileged,
   restricted-filesystem, network-isolated sandbox, returning its
   exit code and captured output — the same `CommandResult` shape
   `adapters/validation/_command.py` already established for M2's
   validators, reused rather than invented a second time. **Sandboxing
   is a blast-radius reduction measure, not a tier-reduction
   mechanism**: a capability that would floor `DESTRUCTIVE`/
   `IRREVERSIBLE`/`MANUAL_ONLY` without a sandbox floors there *with*
   one too. This follows directly from this project's own established
   pattern of never letting a weaker signal override a stronger
   requirement (ADR-0012: voice verification never substitutes for
   physical presence) — a sandbox is real defense-in-depth, not proof
   the underlying action stopped being dangerous; sandbox escapes are
   a real, historically-demonstrated failure mode, and even a perfect
   sandbox can still destroy whatever was deliberately exposed inside
   it (a mounted project directory, for one).

### Application-specific

3. **Spotify — extend, not build.** M1's `MediaPlayerPort`/
   `MprisMediaPlayerAdapter` already controls "whichever media player
   is currently running on the session bus via MPRIS," and that
   module's own docstring already names Spotify explicitly as one of
   the players this covers. Confirmed, not assumed: no new port, no
   new adapter, no new capability *mechanism* — this milestone's only
   real work is registering `music.play`/`pause`/`next`/`previous`
   (already real, already capability-gated) under this milestone's own
   "desktop control" umbrella for documentation purposes, and deciding
   whether volume control or track search (real MPRIS methods
   `MprisMediaPlayerAdapter` does not currently expose) are worth
   adding. **Deliberately not decided here**: whether that extension
   is worth building in this milestone or is speculative scope beyond
   what any real use has asked for yet — flagged as a real, open
   question for WP-48, not pre-answered.

4. **Brave — ordinary control**: launch or focus the application,
   navigate to a URL, via `brave-browser <url>` and `DesktopWindowPort`.
   No CDP dependency (see "Relationship to M5"). Any content read back
   from a Brave window (via `DesktopWindowPort.read_visible_text`, if
   a future capability ever needs it) is `Trust.UNTRUSTED_EXTERNAL`
   per ADR-0011 — a real web page is exactly what that ADR's own
   context section names as the canonical example.

5. **VS Code — ordinary control**: launch or focus the application,
   open a specific file, via `code <path>` and `DesktopWindowPort`. No
   LSP dependency (see "Relationship to M5").

6. **Claude desktop app / ChatGPT desktop app — ordinary control
   only**, per the Non-goals section above: open, focus, type into the
   currently-focused input box on explicit user command, via
   `DesktopWindowPort`. No capability that reads output is ever
   registered for either app — the restriction lives in the capability
   registry, not the port.

7. **Terminal — real UI automation, `MANUAL_ONLY` on every single
   invocation, never a standing grant.** Decided in conversation,
   explicitly as a conscious exception to "no shell" (see Non-goals):
   this milestone's own stated mechanism (libei/AT-SPI2 keystroke
   injection) applied to a terminal emulator is functionally
   equivalent to shell execution, and no attempt is made here to
   pretend otherwise by disguising it as a bounded, typed capability
   the way Git/Docker's operations are. The mitigation is real, not
   cosmetic: **the terminal JARVIS controls must be one it launches
   itself, inside a `SandboxPort`-wrapped `bwrap` invocation — never
   keystroke injection into an arbitrary, already-running terminal
   window the user happens to have open**, since a pre-existing
   terminal's own process tree is outside any containment JARVIS can
   retroactively apply. Output capture (reading back what a command
   printed) is explicitly best-effort, not guaranteed: it depends on
   the specific terminal emulator actually exposing its text buffer
   via AT-SPI2, which is genuinely unconfirmed until WP-43's spike (or
   WP-52's own implementation) checks a real terminal emulator's real
   accessibility support on a real compositor. If no terminal emulator
   on this system exposes usable AT-SPI2 output, that is a real
   finding to report when WP-52 happens, not a gap to paper over now.

8. **Docker — typed, bounded capabilities**, matching `music.*`'s own
   shape, not a general "run any docker command" capability: container
   lifecycle (`docker.run_container`, `docker.stop_container`) and
   image builds (`docker.build_image`), each with fixed, explicit
   arguments (an image reference, a Dockerfile path, a tag — never a
   free-text command string), mapped to one specific, non-shell-
   interpolated `docker` CLI invocation per capability, the same
   subprocess-with-a-fixed-argv pattern `WorkspacePort`'s real `git
   apply` call and M2's validator adapters already use. A read-only
   `docker.list_containers` is the one capability this milestone
   proposes at `READ_LOCAL`/`ALLOW`; everything else that creates,
   runs, or builds floors `DESTRUCTIVE`/`MANUAL_ONLY` (Docker can
   consume host disk/CPU/network unboundedly and, depending on mount
   flags, reach host files directly — this is not a hypothetical risk
   docked down because Docker itself provides some containment; a
   `docker run` capability decides its own tier the same way every
   other capability does, independent of what runs *inside* the
   container it starts). Docker's own containment is not treated as a
   substitute for `SandboxPort` around the *capability call* — the
   `docker` CLI invocation itself is already a bounded, typed
   subprocess call, not free text, so it does not need `bwrap`
   wrapping the way Terminal's genuinely open-ended text injection
   does.

9. **Git — typed, bounded capabilities**: `git.status` (read-only,
   `ALLOW`), `git.create_branch` (`WRITE_LOCAL`/`CONFIRM`, cheap and
   reversible), `git.commit` (`WRITE_LOCAL`/`CONFIRM` — a local commit
   is reversible via `git reset`/`--amend` as long as it is never
   shared), `git.push` (`WRITE_LOCAL`/`CONFIRM` for an ordinary
   fast-forward push to a branch the user already owns). **A
   force-push is its own separate capability, `git.force_push`, not a
   boolean flag on `git.push`** — `DESTRUCTIVE`/`IRREVERSIBLE`/
   `MANUAL_ONLY`, since it can discard a remote's history in a way
   nothing else in this list can undo. This is a real, deliberate
   design principle worth stating plainly: a dangerous variant of an
   otherwise-safe operation gets its own capability id, so the
   capability registry itself makes the real risk visible, rather than
   hiding a `--force`-shaped argument inside a safer-looking call
   where a caller (or a future reasoning-provider-driven candidate)
   could set it without the registry ever having to notice. Real
   mechanism: subprocess `git` CLI calls with fixed argument lists,
   the same shape `WorkspacePort`'s existing `git apply` call already
   uses — a new `GitPort`, not an extension of `WorkspacePort` itself,
   since `WorkspacePort`'s own scope (ADR-0043) is deliberately
   narrowed to "apply a patch for M2 validation," a real but different
   concern from general-purpose git porcelain operations on an
   arbitrary repository.

## Acceptance criteria

The placeholder this document replaces had exactly one exit-gate
sentence and nothing else — no acceptance-criteria list existed to
check this against, and none is invented to round out a number that
was never there. These are new, this pass's own:

1. `DesktopWindowPort` has at least one real, contract-tested adapter
   that finds, focuses, and types into a real application window on
   this machine's real compositor (Wayland, confirmed via
   `XDG_SESSION_TYPE`) — proven by WP-43's spike before WP-44 commits
   to a port signature, not assumed from documentation.
2. `SandboxPort`'s `bwrap` adapter demonstrably denies filesystem
   access outside an explicitly granted path and denies network access
   by default — proven by a real, executed test attempting exactly
   those two things and observing real denial, not merely documented
   as a `bwrap` flag.
3. Every capability this milestone registers whose `Effect` includes
   `DESTRUCTIVE` or `IRREVERSIBLE` is proven, by a real test through
   the real `AuthorizationOrchestrator`, to require `MANUAL_ONLY` —
   including `docker.run_container`, `docker.build_image`,
   `git.force_push`, and every Terminal invocation without exception.
4. Terminal's sandboxed-launch requirement is structurally true, not
   merely documented: no code path in this milestone's Terminal
   capability can inject text into a terminal emulator window that
   `SandboxPort` did not itself launch.
5. No capability registered for the Claude desktop app or ChatGPT
   desktop app calls `DesktopWindowPort.read_visible_text` anywhere in
   `kernel/capabilities.py`'s real registration — checkable by the same
   class of AST/grep meta-test this project already uses for ADR-0012's
   speaker-verification isolation (`tests/meta/test_speaker_id_isolation.py`)
   and ADR-0021's vendor-name grep.
6. `DesktopControlPortContract` (the exit gate's own name) is green on
   both Wayland and X11 — this milestone's own exit gate, taken
   directly, not reworded.
7. Moving the plugin host out-of-process requires zero changes to any
   plugin already written against `jarvis.plugin_api` by this point —
   this milestone's own exit gate, taken directly.

**Incomplete, stated plainly rather than padded**: this list does not
yet cover Spotify's own acceptance bar (deliberately, since deliverable
#3 above defers the decision of what, if anything, gets built beyond
what M1 already ships), Brave/VS Code's exact "already running vs.
fresh launch" behavior on this specific machine (genuinely unconfirmed
until WP-49/WP-50 run for real), or a numeric bound on `bwrap`
resource limits (CPU/memory caps) beyond filesystem/network isolation,
since no real requirement for those was named in this planning pass.
These are real gaps in this list, not silently rounded up to complete.

## Package/class layout proposal

Fit against real `src/jarvis/` structure as it exists post-M2, reusing
existing seams rather than duplicating them:

```
domain/
    desktop.py           - WindowHandle (or equivalent), kept minimal;
                            reuses Classification/Trust/Provenance as-is,
                            no new provenance vocabulary needed
ports/
    desktop_window.py     - DesktopWindowPort
    sandbox.py             - SandboxPort
    git.py                  - GitPort
adapters/
    desktop_window.py     - one real adapter, Wayland-portal/libei vs.
                             X11/AT-SPI2 branching internal to it
    sandbox.py              - BwrapSandboxAdapter
    git.py                   - GitAdapter (subprocess, mirrors
                                adapters/workspace.py's git-apply
                                precedent exactly)
    docker.py                - DockerAdapter (subprocess)
application/desktop/
    (real orchestration for multi-step use cases this milestone's
    capabilities need beyond a single port call — e.g. "launch a
    sandboxed terminal, then inject text, then read output" — mirroring
    why application/reasoning/ exists as a real subpackage rather than
    kernel/ directly calling ports, the same reasoning WP-30 applied:
    kernel/music.py's single authorize-then-call-one-port-method shape
    is not rich enough for Terminal's real multi-step flow)
kernel/
    capabilities.py        - extended, not replaced: nine new
                             CapabilityId constants registered in the
                             same build_default_registry(), per
                             ADR-0039's own precedent for where new
                             capabilities get registered
    desktop.py               - composition root, mirrors kernel/music.py's
                                authorize_and_run_* pattern for the
                                simple capabilities (Spotify, Brave, VS
                                Code, Claude/ChatGPT apps, Docker, Git);
                                Terminal's real multi-step flow likely
                                calls into application/desktop/ rather
                                than inlining everything here, mirroring
                                how kernel/voice_loop.py is thicker than
                                kernel/music.py because its own flow is
                                genuinely more complex
```

No collision found with anything M2 built: `WorkspacePort`,
`CandidatePresentationPort`, `SecretPort`, `OutcomeSinkPort` all stay
exactly as M2 left them, none reused or extended by this milestone
(`WorkspacePort`'s narrow scope is deliberately not widened — see
deliverable #9's Git reasoning above).

## Worked example

*"Open a terminal and run the test suite."* Resolved: `terminal.run`
capability, `Effect.DESTRUCTIVE | Effect.EXECUTE`, floors
`MANUAL_ONLY` unconditionally (criterion #3). `AuthorizationOrchestrator`
evaluates the real `Decision` through the existing choke point,
identical in shape to every other capability in this repo — no second
authorization path for desktop control, matching ADR-0039's precedent
for M2's own cloud-egress calls. If granted (a real physical
confirmation via `Gtk4PhysicalConfirmationAdapter`, reused unmodified
— see "Confirmation boundary" below): `application/desktop/`
orchestrates `SandboxPort.run("bash", sandboxed=True)` to launch a
contained terminal emulator, `DesktopWindowPort.focus()` +
`type_text("pytest\n")` to run the suite inside it, and — best-effort
— `read_visible_text()` afterward, tagged `Trust.UNTRUSTED_EXTERNAL`
per ADR-0011 regardless of how trustworthy the command itself seemed,
since the *output* is content this process did not generate and must
not implicitly trust. If denied: nothing is launched at all — the
sandboxed terminal never exists, matching every other capability's
"never touched if denied" guarantee (`kernel/music.py`'s own framing,
reused identically).

## Confirmation boundary

`ConfirmationPort`/`ManualConfirmationAdapter` and
`PhysicalConfirmationPort`/`Gtk4PhysicalConfirmationAdapter` are reused
completely unmodified by this milestone. No new confirmation surface
is designed or needed: `MANUAL_ONLY` desktop-control capabilities
(Terminal, `docker.run_container`, `docker.build_image`,
`git.force_push`) are satisfied by the exact same real GTK4 dialog and
genuine-`Gdk.Event` check ADR-0035 already built and manually verified
for M1's voice path. ADR-0012/ADR-0013's boundary (voice/speaker
verification never satisfies more than `CONFIRM`; only physical
interaction satisfies `MANUAL_ONLY`) is not reopened anywhere in this
document — nothing here constructs a `PolicyContext` from
`SpeakerIdPort`/desktop-automation-observed signals, and
`tests/meta/test_speaker_id_isolation.py`'s existing structural check
already covers the whole `src/jarvis` tree, this milestone's new code
included, with no changes needed to that test itself.

## "Always legible"

M1's `TtsPort` is reused as-is for any desktop-control action worth
announcing — no new voice mechanism is designed here, matching
`docs/ROADMAP.md`'s own constraint. No visible on-screen surface exists
yet (M5's Console UI is not built); this milestone does not invent one
early. If a future desktop-control action needs a legible surface
before M5 exists, the precedent is ADR-0040's own move for M2's
unverifiable-task regime: a port-shaped boundary
(`CandidatePresentationPort`) so a real UI can be swapped in later
without the underlying logic changing — the same pattern would apply
here if a real need arises, not a new one invented from scratch. No
such need was identified in this planning pass; none is built
speculatively.

## Deferred, not forgotten

- Retrofitting `SandboxPort` onto M2's `RuntimeCheckValidator`/
  `PytestValidator`/`UserScriptValidator` (see "Relationship to M2"). A
  real, tracked follow-up, not one of this milestone's work packages.
- Spotify volume control / track search (see deliverable #3) — real
  MPRIS capability, not decided whether it is worth building.
- The `Prompt`-based unlock flow for a locked Secret Service collection
  (ADR-0042's own deferral) and any secret-write path — unrelated to
  this milestone directly, but still real, still open, restated here
  only because desktop control is the first milestone since M2 to
  touch `SecretPort`-adjacent territory again (Docker/Git credentials,
  if a future work package needs registry auth or a private remote —
  **not decided in this pass, explicitly out of the nine deliverables
  above**, since no real requirement for it was named).
