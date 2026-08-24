# ADR-0047: SyntheticInputPort -- the RemoteDesktop portal, scoped to Terminal only

## Status

Accepted

**Acceptance note (2026-08-24):** the user accepted this ADR's synthetic-input capability with one added, load-bearing condition -- the sandboxed terminal must be unmistakably marked, visually and audibly, for the duration synthetic input can fire, giving a real, in-the-moment chance to notice and abort a misdirected keystroke given the TOCTOU race documented below is confirmed *not* closable to zero. That condition is specified in full in "The real-time indicator" section below, added at acceptance -- it was not part of the original Proposed draft. Acceptance is of the design in this document; it is not authorization to implement. Per CLAUDE.md's hard rule and the user's own explicit instruction, no code for this capability exists yet, and none should until a separate, scoped work package is opened for it.

## Date

2026-08-24

## Source

`docs/architecture/m3-terminal-synthetic-input-proposal.md` (investigation-only, no ADR); the real, structural gap that proposal responds to (`docs/threat-model/v0.md`'s "A real, structural gap: Terminal's own type_text mechanism cannot type into a real terminal" finding, live-confirmed during M3's post-WP-55 verification pass: VTE exposes AT-SPI2's `Text` interface but not `EditableText`, so `AtspiDesktopWindowAdapter.type_text()`'s only mechanism -- finding a focused `EditableText` node and calling `insert_text` -- has no node to call it on for any terminal emulator). Accepted by the user via this exact tradeoff: a real, disclosed, un-closable-to-zero focus race, accepted specifically because it is bounded and mitigated by a real-time, human-legible indicator -- per `docs/ROADMAP.md`'s "always legible" standing principle -- not because the race itself was resolved.

## Context

`terminal.run` is real, shipped, and cannot type a command into a real terminal today -- confirmed live, not assumed. The proposal document already did the exploratory legwork and reached a real, defensible recommendation: use the `RemoteDesktop` portal's `NotifyKeyboardKeysym` D-Bus method rather than raw `libei` FFI (no Python binding exists on this distribution at all -- confirmed via `dpkg -L libei1` and a filesystem-wide search for `Ei-1.0.typelib`/`Eis-1.0.typelib`, both empty) or `ConnectToEIS` (the newer, unnecessary-for-this-purpose binary-socket path). That recommendation is not re-litigated here; this ADR exists to do the parts CLAUDE.md requires before any code lands: name the real port shape, and resolve -- not merely list -- the safety-critical questions the proposal deliberately left open.

This is a genuinely new, more powerful capability class than anything M0-M3 has built: the first mechanism in this codebase that can inject real keyboard events reaching **whatever the compositor currently has focused, system-wide** -- not scoped to a specific accessible node the way `AtspiDesktopWindowAdapter.type_text()`'s `insert_text` call is. That structural difference is the entire reason this needs its own ADR rather than being folded into `DesktopWindowPort` as a second `type_text` implementation strategy, and it is the source of the one genuinely hard question below: how does JARVIS know, at the moment it fires a keystroke, that the compositor's focus is actually where JARVIS thinks it is?

### What was checked live, this pass, specifically to answer that question

Three real avenues were checked on this development machine (Wayland, GNOME Shell/Mutter) for any API that would let a client **query** current compositor keyboard focus -- as opposed to merely **setting** it, which is all `RemoteDesktop` offers:

1. **`RemoteDesktop`'s own interface, fully introspected** (`gdbus introspect --session --dest org.freedesktop.portal.Desktop --object-path /org/freedesktop/portal/desktop`): every method is a `Notify*` -- `NotifyKeyboardKeycode`, `NotifyKeyboardKeysym`, `NotifyPointerMotion`, `NotifyPointerButton`, etc. There is no getter for current focus anywhere in this interface. This is not an oversight in the portal spec -- it is the portal model working as intended: a sandboxed app is deliberately not allowed to observe what else the user is doing, the same privacy boundary that makes `InputCapture` (checked and correctly ruled out by the earlier proposal) a capture-only, not observe-arbitrary-focus, mechanism.

2. **`org.gnome.Shell.Eval`** (GNOME Shell's own JavaScript-eval D-Bus method, which -- if enabled -- could read `global.display.focus_window.get_wm_class()` directly): called live, returned `(false, '')` -- disabled on this real machine. This is GNOME's own default posture on any reasonably current release (`Eval` is an arbitrary-code-execution surface into the shell process itself, gated behind an explicit developer-mode setting). Depending on this ADR's mechanism working would mean asking the user to run their desktop in a less secure configuration purely to support this one JARVIS feature -- an obviously wrong trade, not proposed here.

3. **`wlr-foreign-toplevel-management`** (the protocol taskbars/docks on wlroots-based compositors, e.g. Sway, use to enumerate windows and see which is active): does not apply here at all -- confirmed this machine's compositor is Mutter (`loginctl` reports `Type=wayland`, GNOME Shell), and Mutter does not implement this wlroots-specific protocol.

**All three routes to a direct, authoritative "what does the compositor currently have focused" answer are closed on this platform, for the same underlying reason: Wayland's security model deliberately does not let a sandboxed client observe global focus state, because that is itself a spying primitive.** This is the real finding the rest of this ADR has to design around, not route past.

The one real, usable proxy that does exist: **AT-SPI2's own focus tracking** (`Atspi.StateType.FOCUSED`, and the corresponding `object:state-changed:focused` event). Confirmed live and working -- a full-desktop AT-SPI2 tree walk querying every node's state set found a real node reporting `FOCUSED`. This is a genuinely different signal from compositor keyboard focus, though: it is toolkit-level accessibility state (GTK/VTE/etc. report "this widget is focused" through the accessibility bus), maintained by an entirely separate code path and separate IPC bus (`org.a11y.*`, the accessibility bus) from the one synthetic keystrokes actually travel through (the portal's own session-bus D-Bus call, which the compositor itself services). There is no atomic coupling guaranteeing these two facts move together. That gap is the real subject of the Decision below.

## Decision

### `SyntheticInputPort` shape

A new, minimal port, `jarvis.ports.synthetic_input.SyntheticInputPort`, scoped strictly to portal session lifecycle and injection -- it knows nothing about `WindowHandle` or AT-SPI2, deliberately, because a portal session is not parameterized by a target window at all (it fires at whatever the compositor has focused, full stop):

```python
@runtime_checkable
class SyntheticInputPort(Protocol):
    def start_session(self, restore_token: str | None) -> SyntheticInputSession:
        """Open (or replay) a RemoteDesktop session.

        If ``restore_token`` is ``None`` or the portal rejects it as
        invalid/revoked, falls back to a fresh interactive grant
        (persist_mode=2) exactly once -- never silently retried beyond
        that. Raises SyntheticInputUnavailableError if the human denies
        the resulting dialog, or no portal is reachable at all.
        """
        ...

    def send_keysym(self, session: SyntheticInputSession, keysym: int, *, press: bool) -> None:
        """Fire one NotifyKeyboardKeysym press or release event.

        Delivered to whatever the compositor currently has keyboard
        focus -- this method has no concept of a target window and
        cannot be given one. Callers needing a specific target must
        verify focus themselves, immediately before calling this
        (see the focus-verification mechanism below); this port
        provides no such verification itself.
        """
        ...
```

`SyntheticInputSession` is a small, frozen dataclass (`session_handle: str`, `new_restore_token: str | None`) living in `jarvis.domain.desktop` alongside `WindowHandle` -- `new_restore_token` is non-`None` exactly when the portal issued a token the caller must persist (first grant, or a rotated replacement; per the portal's documented one-token-per-use invalidation, already researched in the proposal doc).

`jarvis.adapters.synthetic_input.PortalSyntheticInputAdapter` implements this for real via `jeepney` against `org.freedesktop.portal.Desktop`, matching `MprisMediaPlayerAdapter`/`SecretServiceAdapter`'s established shape: real wire mechanics factored into small, constructor-injectable functions; pure session/token logic unit-testable without a real bus.

**A real, concrete gap this surfaces, not hand-waved**: `SecretPort` (ADR-0042) is read-only today (`get_secret` only; ADR-0042's own Consequences section names the write path as deliberately not built). Persisting `SyntheticInputSession.new_restore_token` requires a real write path that does not exist. This ADR does not design that extension -- it is a small, separate, low-risk addition to an already-Accepted port (add `set_secret(reference: str, value: str) -> None`), but it is a genuine blocking dependency of this proposal, not an implementation detail to discover later. Flagged here so the eventual work package doesn't rediscover it mid-implementation.

### The focus-verification mechanism, in full detail

**The honest headline: this cannot be made airtight with any API available on this platform today. It can be narrowed to a small, bounded residual risk, and that residual risk must be disclosed and explicitly accepted by the user, not designed away as if it doesn't exist.**

Mechanism:

1. `DesktopWindowPort` gains one new method, `is_focused(self, handle: WindowHandle) -> bool` -- a real AT-SPI2 query of `handle`'s own node (or its nearest window-role ancestor) for `Atspi.StateType.FOCUSED`. This is a natural, small extension of the port's existing AT-SPI2-backed responsibility (it already holds the accessibility-bus connection and `WindowHandle`-to-node mapping `find_or_launch`/`focus` use), not part of `SyntheticInputPort` -- `SyntheticInputPort` structurally cannot do this check itself, since portal sessions carry no `WindowHandle` concept at all.

2. A new orchestration function (the eventual replacement for `run_in_sandboxed_terminal`'s `type_text` call, when typing into a terminal specifically -- not a change to `type_text`'s own contract, which stays as-is for apps whose `EditableText` path does work) interleaves verification and injection **per character**, not once at the start:

   ```
   if not desktop_window.is_visible_and_showing(handle):  # VISIBLE and SHOWING, not ICONIFIED
       raise SyntheticInputUnavailableError("indicator cannot be shown: window not visible")
   await tts.speak("Typing into sandboxed terminal now.")  # raises on failure -- not caught here

   for each character in command_text:
       keysym = map_char_to_keysym(character)
       if not desktop_window.is_focused(handle):
           abort_remaining_characters()
           raise SyntheticInputUnavailableError("focus lost mid-command")
       synthetic_input.send_keysym(session, keysym, press=True)
       synthetic_input.send_keysym(session, keysym, press=False)
   if not desktop_window.is_focused(handle):
       raise SyntheticInputUnavailableError("focus lost after last character")
   ```

   (The visual half of the indicator -- the dedicated terminal profile -- is not a step in this loop at all: it is applied once, at `sandbox.launch()` time, via `--profile=<uuid>` on the launch command itself, and is therefore already live before this function is ever called. See "The real-time indicator" below for why that is the correct place for it, not a gap in this pseudocode.)

   Per-character (not once-at-start) is the deliberate, more expensive choice: verifying once before a whole command leaves every character after the first exposed to a focus change with zero further checking, for a MANUAL_ONLY-gated action where a human has already agreed to wait for one interactive confirmation -- the extra IPC round trips this costs are not a real problem here, unlike a hypothetical latency-sensitive path.

3. **Fail-closed is structural, not a convention to remember**: `is_focused` returning `False` (or raising) at any point aborts every remaining character -- there is no retry-and-hope branch, no "assume it's probably fine" fallback. Characters already sent before the failure cannot be recalled; this is named explicitly in Consequences below, not glossed over.

4. **The race-condition window, stated concretely, not hand-waved as "small"**: between step 2's `is_focused()` call returning and its paired `send_keysym()` call being processed by the compositor, there are two separate local D-Bus round trips through two separate buses (accessibility bus for the check, session bus for the portal call) with no atomic coupling between them. Both are local, same-machine calls -- every AT-SPI2 query performed live during this and prior verification passes completed in well under 100ms for a single node/state query, so the realistic order of magnitude is low tens of milliseconds per character, not a network-latency-scale gap -- but this project has **not** literally instrumented a back-to-back verify-then-inject loop with timestamps on real hardware (doing so would mean actually firing synthetic keystrokes at a live window during an unattended pass, which this pass correctly declined to do). The number above is a reasoned estimate from adjacent, real measurements, not a benchmarked fact -- stated at that confidence level, not rounded up.

   Within that window, nothing on this platform can prevent a real focus change (a notification bubble grabbing attention, another already-running app's dialog popping up, the user's own hand moving to another window) from landing between the check and the injection of any single character. **No mitigation in this design closes that window to zero.** Verifying more often (already done, per-character) narrows how much of a multi-character command is exposed to a single unlucky race, but the per-character window itself is structurally irreducible with tools available today -- there is no portal-exposed keyboard grab or focus-lock a sandboxed client can request on this platform (Wayland's security model exists specifically to prevent one app from being able to force or lock focus onto another's window, which is exactly the primitive this design would need to close the gap and exactly what the platform correctly refuses to hand out).

### The real-time indicator -- load-bearing, not a nice-to-have

This section exists because the focus-verification mechanism above cannot close its own race to zero. The indicator is the mitigation the user accepted in exchange for that residual risk: it does not make the race smaller, it gives the one thing that can actually catch a misdirected keystroke *in the moment* -- a physically-present human's own eyes and ears -- a real, unmistakable signal to notice by. Per `docs/ROADMAP.md`'s "always legible" principle ("every action JARVIS takes... should be legible to Akash in real time -- both spoken... and visible on-screen"), stated there as a standing product expectation, not something each capability may opt out of.

**Visual: a dedicated, unmistakable terminal profile, applied at launch, live for the terminal's entire lifetime.**

`BwrapSandboxAdapter`/`run_in_sandboxed_terminal`'s existing `_TERMINAL_LAUNCH_COMMAND` (currently `("gnome-terminal",)`) gains `--profile=<jarvis-synthetic-input-profile-uuid>` whenever the terminal being launched will receive synthetic input (i.e. every `terminal.run` invocation under this ADR -- `gnome-terminal` has no other real caller in this codebase). The profile itself: a real GSettings relocatable profile (`org.gnome.Terminal.Legacy.Profile`, the same mechanism GNOME's own Preferences UI uses), created once, idempotently (checked-and-created-if-absent, never re-created on every launch), by the adapter -- a solid, saturated, low-ambiguity background color reserved exclusively for this purpose (e.g. a bright amber or red, distinct from any color a normal user profile would plausibly choose, so the signal reads as "JARVIS is controlling this window" on sight, not as a stylistic choice). This profile is never applied to, or confused with, the user's own Default profile or any terminal the user opens themselves -- creation is narrow (one new relocatable GSettings path, e.g. under `/org/gnome/terminal/legacy/profiles:/<uuid>/`) and fully reversible (`dconf reset` on that one path removes it with zero effect on anything else), matching the same "narrow and reversible, or don't do it" bar this project has already applied to real-machine changes elsewhere in this engagement.

**Why this is "for the entire duration synthetic input is firing" and not merely "sometimes marked":** per ADR-0046's own structural guarantee, this terminal is freshly launched by `sandbox.launch()` solely for this one `terminal.run` invocation and is never a long-lived, reused, idle terminal -- there is no meaningful period of this terminal's existence that occurs outside the span containing its one synthetic-input session. Marking it for its whole lifetime is a strict superset of marking it only while keystrokes are actively firing, not a weaker substitute.

**A real, disclosed deviation from a tighter "on only during injection, off otherwise" design, checked live rather than assumed:** a border or color that lights up specifically at injection-start and reverts at injection-end (the tighter design one might picture first) was investigated this pass and found not achievable via any confirmed, supported API on this stack. `org.gnome.Terminal`'s own D-Bus surface (`gdbus introspect --dest org.gnome.Terminal --object-path /org/gnome/Terminal/Factory0 --recurse`, live) exposes exactly one method, `CreateInstance` -- a launch-time call, with no property-mutation interface for a running instance's appearance. A separate, JARVIS-drawn overlay window positioned over the terminal's live screen extents was also considered, but would need either a compositor-level always-on-top/client-positioned-overlay primitive (`wlr-layer-shell` or equivalent) that this pass did not confirm Mutter implements -- and the same pattern already found twice in this document (no `wlr-foreign-toplevel-management`, no focus-query API) makes its absence the more likely outcome, not verified either way this pass -- or GTK's own always-on-top window hint, which Wayland's client-doesn't-dictate-stacking model has already removed real effect from. Rather than specify a mechanism that may not exist, this ADR specifies the one confirmed to exist (profile-at-launch) as the real requirement, and names a live-toggling indicator as a genuine, worthwhile enhancement for the implementing work package to investigate for real -- not asserted as working here.

**Audible: a spoken announcement via the existing, real `TtsPort`, immediately before the injection loop begins.**

`TtsPort.speak(text) -> AudioStream` (`jarvis.ports.tts`) is real, shipped, M1 infrastructure -- no new capability class needed for this half. The orchestration function calls `await tts.speak("Typing into sandboxed terminal now.")` (exact phrasing TBD at implementation time, not load-bearing here) and waits for it to complete before the first keystroke. **A real, honestly-named gap, parallel to the focus-verification race already disclosed above:** `TtsPort.speak()` succeeding confirms synthesis succeeded, not that the resulting audio was actually, audibly played -- the current port contract carries no playback-completion signal. Treating a successful `speak()` return as sufficient to proceed is the best available signal today, not a perfect one; closing this gap for real (a genuine playback-confirmation contract on `TtsPort`, or an adjacent port) is out of scope for this ADR and not required to accept it, but should not be silently assumed solved either.

**Hard-abort precondition -- fail closed, never fire blind, extended to the indicator itself:**

Immediately before the per-character loop begins (not merely once at `terminal.run`'s own start), both of the following must hold, checked for real, or the entire operation aborts with zero keystrokes sent:

1. The terminal window's AT-SPI2 state set includes `Atspi.StateType.VISIBLE` and `Atspi.StateType.SHOWING`, and excludes `Atspi.StateType.ICONIFIED` -- the same AT-SPI2 mechanism `is_focused()` already uses, extended to one more state check on the same node, not a new subsystem. A minimized, hidden, or otherwise not-actually-on-screen terminal cannot make its own visual marking legible to anyone, regardless of what profile it was launched with, so this is checked directly rather than inferred from the profile having been applied.
2. `tts.speak(...)`'s call completed without raising.

If either check fails, `SyntheticInputUnavailableError` is raised before `SyntheticInputPort.start_session()` is even called -- this is a stricter, earlier gate than the per-character `is_focused()` loop, because an invisible or inaudible indicator means the human's one real chance to notice a misdirected keystroke doesn't exist yet, which this ADR treats as equivalent to "focus cannot be verified" for fail-closed purposes: no signal, no keystrokes, full stop.

### Interaction with `Tier.MANUAL_ONLY` -- argued, not asserted

**Layered and independent. Portal-level authorization does not substitute for, weaken, or count toward JARVIS's own `MANUAL_ONLY` gate.** Argument:

1. **They answer different questions.** The portal's persisted grant (`persist_mode: 2`, the `restore_token` replay path) answers a coarse, one-time, per-machine question: "is this OS user willing to let JARVIS have the *ability* to inject synthetic input at all, ever." `AuthorizationOrchestrator`/`domain/policy.py`'s `MANUAL_ONLY` check answers a fine-grained, per-invocation question: "do I want *this specific command text* run *right now*." A user can rationally grant the first once while still wanting to review every individual instance of the second -- exactly the same relationship a real keyboard's mere existence on the desk has to `terminal.run`'s own requirement that a human press a real key on it every time, which ADR-0046 already establishes as the load-bearing case.

2. **Structurally, once granted, the portal dialog never fires again.** After the first `persist_mode: 2` grant, `start_session()` replays the stored token silently -- there is no per-invocation OS-drawn signal left to observe at all. Treating "a valid restore_token exists" as an ongoing proxy for "a human is physically present right now" would be precisely the mistake ADR-0012/ADR-0034 already named and rejected for voice/speaker verification: a persisted, replayable credential proves the *machine* was once authorized, not that a *human* is present *now*. `context.physical_confirmation_available` is a real-time signal (`PhysicalConfirmationPort.await_physical_confirmation`, a genuine blocking keypress/click); a stored token is not, and must never be read as if it were.

3. **This does not reopen ADR-0046.** ADR-0046's Decision #1 is explicit and was already a hard-won call: "No standing grant, no CONFIRM-tier fast path, regardless of what command text is being sent... the only honest floor is the tier requiring a human physically present to authorize this specific invocation, every time." This ADR does not touch that. `terminal.run`'s `Effect.DESTRUCTIVE | Effect.EXECUTE` declaration and its unconditional `MANUAL_ONLY` floor are unchanged by adopting `SyntheticInputPort` as the typing mechanism underneath it -- this ADR is about *how* a keystroke is delivered once a human has already approved the invocation, never about *whether* one is required.

### `restore_token` lifecycle via `SecretPort`

- **Storage**: `PortalSyntheticInputAdapter` takes a `SecretPort` at construction (mirroring `family_a`/`family_b`'s existing pattern, ADR-0042's Consequences), and internally resolves/stores under a fixed reference, e.g. `"desktop.synthetic_input.restore_token"`.
- **First use**: `secret.get_secret(...)` raises `SecretNotFoundError` -> `start_session(None)` -> real interactive portal dialog fires for real, `persist_mode: 2` requested -> resulting `new_restore_token` is written back via the write path this ADR names as a required, currently-missing extension to `SecretPort` (see above).
- **Steady state**: token found -> replayed via `SelectDevices`/`Start()` with the stored token -> no dialog -> `new_restore_token` from the response (per-use rotation, already researched in the proposal doc) overwrites the stored value every time, unconditionally -- never assumed stable across calls.
- **Revocation / invalidity** (the proposal doc's own open question, resolved here): if replay fails -- the portal's response indicates the token is no longer valid, e.g. because the user revoked it through their own desktop's permission settings out-of-band -- `start_session()` falls back to exactly one fresh interactive grant attempt (`persist_mode: 2`, no token), the same as first-use. If the human denies *that* dialog, `SyntheticInputUnavailableError` is raised and surfaced to the caller as a real, terminal failure of that invocation -- never silently retried, never treated as "try again next time without telling anyone." One automatic fallback attempt is justified because a revoked-but-not-maliciously-revoked token (e.g. the user cleared it while cleaning up unrelated portal grants) shouldn't force a human to notice and manually clear JARVIS's own stored state before it works again; anything beyond that one fallback becomes indistinguishable from silently nagging past a real "no."

### Explicit scope limit

This ADR authorizes `SyntheticInputPort` for **`terminal.run`'s typing step only**. Reusing it for the Claude/ChatGPT desktop apps' `type_text`, or any other future capability, requires a separate, explicit, future decision -- not implied by this one. This is not a formality: those apps' existing AT-SPI2 `EditableText` path (where it is reachable at all) targets a specific accessible node directly, regardless of what the compositor has focused, and therefore does not share this ADR's focus-verification race *at all* -- swapping to the strictly less-targeted, more-broadly-exposed mechanism this ADR describes would be a real regression in safety for those apps, not an improvement, absent a fresh, specific reason those apps don't currently have (per ADR-0045's own `EditableText`-or-nothing framing, unchanged by this document).

## Consequences

- `terminal.run` gains a real, working path to type commands into a real terminal for the first time -- closing the structural gap the proposal doc named. `Terminal: works, with an honest partial result` in the threat model can finally become a full success entry rather than a documented gap.
- A genuine, permanent, disclosed residual risk is accepted alongside it: a narrow (low-tens-of-milliseconds, per character, unbenchmarked-but-reasoned) window in which a real, uncontrollable focus change could cause one or more characters of an already-human-approved command to be delivered to whatever else the compositor focused instead of the sandboxed terminal. Fail-closed verification (per-character, abort-on-mismatch) minimizes how much of a command can leak through a single unlucky race; it does not, and structurally cannot, reduce that window to zero with tools available on this platform today. Any future session or reviewer re-reading this ADR should not mistake "verified" for "safe from this race" -- they are not the same claim.
- `SecretPort` (ADR-0042) needs a real write method before this can be implemented -- a small, separate, low-risk extension this ADR surfaces as a hard dependency, not an afterthought.
- `DesktopWindowPort` gains two new methods (`is_focused`, and a visibility check exposing `VISIBLE`/`SHOWING`/`ICONIFIED` state); its existing five methods and every existing adapter/test are otherwise untouched.
- The real-time indicator (dedicated terminal profile at launch, spoken announcement before injection, and the hard-abort precondition gating both) is accepted as a load-bearing, mandatory part of this design, not an optional enhancement -- a future implementation that ships the typing mechanism without it does not satisfy this ADR, regardless of how the code is structured. A dedicated, JARVIS-owned GSettings terminal profile is created on this machine the first time the capability runs -- narrow in scope (one relocatable profile path, unrelated to the user's own terminal profiles) and fully reversible (`dconf reset` on that path), consistent with this project's own bar for real-machine changes.
- A real, disclosed gap alongside the focus-verification race: `TtsPort.speak()` succeeding confirms synthesis, not confirmed audible playback -- the best available signal today, named honestly rather than assumed solved, matching how the focus race itself is disclosed rather than smoothed over.
- `SandboxPort` remains completely unaffected, per the proposal doc's own finding: portal calls are plain session-bus D-Bus, no raw display-socket access needed the way `_display_bind_paths()` required for display.
- `terminal.run`'s `Effect`/`Tier` declaration is unchanged; `MANUAL_ONLY` continues to fire on every invocation regardless of portal-grant persistence state, per the argument above.
- Explicitly forecloses, absent a fresh decision: reuse of this mechanism for Claude/ChatGPT `type_text`, or any capability where a node-scoped mechanism already works -- this ADR is not precedent for reaching for compositor-wide injection where a narrower tool exists.

**Resolved by the user, not by more design work**: whether the residual TOCTOU race described above is an acceptable risk for a real, shipped feature was a genuine judgment call about risk tolerance, not a technical question this ADR could answer on its own. The user's answer is acceptance, specifically conditioned on the real-time indicator above -- not a claim that the race itself became smaller or closable. Any future session or reviewer re-reading this ADR should take the same care the original draft asked for: "verified" (focus-checked, indicator-shown) is still not the same claim as "this race cannot happen" -- it is "a human had a real, in-the-moment chance to notice if it did."
