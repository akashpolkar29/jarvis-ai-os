# M3 — Terminal synthetic input: investigation and proposal

**Status: proposal, not a decision.** Design investigation only, per
the user's explicit scope for this pass — no synthetic keyboard/mouse
input is implemented here, and no ADR is written yet. This document
exists so a future work package (or the user, deciding whether to
authorize one) has real, live-checked findings to work from rather
than re-deriving them.

## The real gap this addresses

M3's own live-verification pass (`docs/threat-model/v0.md`'s "Live
desktop-control verification" section) found that `terminal.run`'s
real flow cannot type into a real terminal at all: VTE (the terminal
widget `gnome-terminal-server` uses) exposes AT-SPI2's `Text`
interface but not `EditableText`, and `AtspiDesktopWindowAdapter.
type_text()`'s only mechanism is finding a focused `EditableText` node
and calling `insert_text` on it. A terminal was never going to expose
that interface — it isn't a conventional text-entry widget, and no
amount of AT-SPI2-only engineering closes this gap. Real synthetic
keyboard input is required.

## What was actually checked, live, on the real development machine

### `libei` directly: present as a C library, absent as anything Python can call

`libei1`/`libeis1` (the client/server halves of the `libei` protocol)
are genuinely installed — confirmed via `dpkg -l`, version `1.2.1-1`,
matching Ubuntu 24.04's own repos. This is more than WP-43's spike
found (it only checked the GI binding). But checked further this pass:
`dpkg -L libei1` lists exactly one file beyond docs —
`/usr/lib/x86_64-linux-gnu/libei.so.1.2.1`, a plain shared library with
**no GObject-Introspection typelib at all** (`find` for `Ei-1.0.typelib`/
`Eis-1.0.typelib` anywhere on the filesystem: nothing). No Python
package exists either — `apt-cache search`/`pip index` for anything
libei-shaped: nothing. This is a firmer finding than "the binding is
missing": **there is no binding to install** on this distribution.
Using `libei` from Python would mean hand-writing `ctypes`/`cffi` FFI
bindings against the raw C ABI — a real, nontrivial engineering task
with its own correctness surface (memory layout, callback marshaling,
the library's own async event-loop integration expectations), not a
missing-package problem a future work package can just fix by
installing something.

### The `RemoteDesktop` portal: present, and offers a path that needs no `libei` at all

Live-introspected on this machine (`gdbus introspect --session --dest
org.freedesktop.portal.Desktop --object-path
/org/freedesktop/portal/desktop`), confirmed real and version 2:

```
interface org.freedesktop.portal.RemoteDesktop {
  methods:
    CreateSession(in a{sv} options, out o handle);
    SelectDevices(in o session_handle, in a{sv} options, out o handle);
    Start(in o session_handle, in s parent_window, in a{sv} options, out o handle);
    NotifyKeyboardKeycode(in o session_handle, in a{sv} options, in i keycode, in u state);
    NotifyKeyboardKeysym(in o session_handle, in a{sv} options, in i keysym, in u state);
    ConnectToEIS(in o session_handle, in a{sv} options, out h fd);
    ... (pointer/touch methods, not relevant to Terminal)
  properties:
    readonly u AvailableDeviceTypes = 7;
    readonly u version = 2;
};
```

The important, real finding: **`NotifyKeyboardKeycode`/
`NotifyKeyboardKeysym` are plain D-Bus method calls** — the original
v1 RemoteDesktop API, still fully functional standalone. `ConnectToEIS`
(which hands back a file descriptor for the newer, lower-overhead
binary EIS-socket protocol) is a *separate*, optional, higher-
throughput path, not a prerequisite for the D-Bus methods. This means
**synthetic keyboard input is reachable with zero `libei` dependency**,
using exactly the D-Bus mechanics this codebase already has a real,
working client for (`jeepney`, the same library `adapters/media_player.py`
already uses for MPRIS).

`NotifyKeyboardKeysym` is the right method of the two for typing
arbitrary command text: keysyms are keyboard-layout-independent
(unlike raw keycodes, which are scancode-shaped and layout-dependent),
and most Unicode characters are expressible via keysyms (the X11
keysym space defines a `0x1000000 + codepoint` convention for
characters without a dedicated named keysym). Real, honestly-flagged
implementation detail this finding surfaces, not resolved here: typing
a string means iterating its characters, mapping each to a keysym, and
firing a press/release event pair per character in order — a real,
moderately fiddly translation layer, not a single API call.

The `InputCapture` portal was checked and ruled out as the wrong tool:
it exists to *capture* real input events at the local device level and
forward them elsewhere (the Barrier/Synergy-style seamless-multi-
machine-input use case) — the opposite direction from what Terminal
needs (*injecting* synthetic input locally). `RemoteDesktop` is the
correct, purpose-built portal here.

### The permission model: one real dialog, then a stored token — not one dialog per command

Researched directly (not assumed): `RemoteDesktop`'s `SelectDevices`
accepts a `persist_mode` option (`0` = don't persist, `1` = persist
while the app is running, `2` = persist until explicitly revoked).
Confirmed this machine's portal is version 2, which is exactly the
version that added this. With `persist_mode: 2`, `Start()`'s response
includes a `restore_token`; passing that same token to a future
`SelectDevices()` call skips the interactive dialog entirely — Sources:
[RemoteDesktop portal docs](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html),
[xdg-desktop-portal RemoteDesktop.xml](https://github.com/flatpak/xdg-desktop-portal/blob/main/data/org.freedesktop.portal.RemoteDesktop.xml).
The token is invalidated after one use — each real session's response
carries the *next* token to store, a real, easy-to-get-wrong detail
worth calling out now rather than discovering it mid-implementation.

**This is not a UX problem to route around — it's a real, good fit for
this project's own architecture, worth stating plainly:**

- The *first* real `terminal.run` invocation triggers one genuine,
  OS-drawn permission dialog — arguably a *stronger* trust signal than
  JARVIS's own GTK4 confirmation dialog (ADR-0035), since it's the
  desktop environment's own trusted portal UI, not an app-drawn window
  a compromised process could in principle mimic.
- The returned `restore_token` is exactly `SecretPort`-shaped (ADR-0042)
  — a `SECRET`-classified value, stored only in the system keyring,
  never logged, referenced not copied — matching this project's
  existing secret-handling discipline with no new mechanism needed.
- **This does not weaken `terminal.run`'s `MANUAL_ONLY` guarantee
  (ADR-0046).** The portal's persisted grant answers a coarser
  question — "may this app ever synthesize input at all" — the same
  shape as a Flatpak app's one-time portal grant. JARVIS's own
  `AuthorizationOrchestrator`/`evaluate()` gate is a separate, finer-
  grained layer answering "is *this specific* invocation authorized,"
  and continues firing on every single call regardless of portal-level
  persistence — the two layers are complementary, not in tension, the
  same relationship a real keyboard's mere existence has to
  `MANUAL_ONLY`'s own requirement that a human press a real key on it
  every time.

### A new, real safety consideration this mechanism introduces

AT-SPI2's `EditableText.insert_text` targets a specific accessible
*node* directly, regardless of what the compositor currently has
focused — a bug in `DesktopWindowPort.focus()` could leave the wrong
window on screen, but text would still land in the *node* `type_text`
was given. Portal-based synthetic input is different: `NotifyKeyboard
Keysym` sends events to **whatever the compositor currently has
focused**, full stop — there is no way to target a specific window
through this API. This means **`DesktopWindowPort.focus()`'s own
reliability becomes a load-bearing safety property it currently isn't**:
if `focus()` succeeds without actually raising the intended sandboxed
terminal (a race, a compositor quirk, a focus-stealing-prevention
policy silently ignoring the request), synthetic keystrokes carrying a
real shell command could land in whatever the user was actually
looking at instead. Any real implementation of this proposal needs a
real, verified check that focus genuinely landed on the intended
window *before* sending a single keystroke — not assumed from `focus()`
returning without an exception, which is all the current contract
guarantees.

## Recommendation

Use the `RemoteDesktop` portal's direct D-Bus methods
(`NotifyKeyboardKeysym`), not raw `libei` FFI bindings and not
`ConnectToEIS`. Reasons, in order of weight:

1. No new dependency to bind — `jeepney` already exists in this
   codebase for exactly this shape of call.
2. `libei` FFI bindings are real, nontrivial, ongoing-maintenance
   engineering with no path to buy that cost down (no package exists
   to adopt instead of writing it).
3. The permission model is real, understood, and fits this project's
   existing `SecretPort`/`MANUAL_ONLY` architecture with no new
   mechanism — not a UX cost to accept, a good fit to use.

## Integration sketch (not a commitment — for the eventual ADR/WP to weigh)

- A new port, plausibly `ports/synthetic_input.py`
  (`SyntheticInputPort`), rather than extending `DesktopWindowPort`
  directly — this is a materially more powerful, differently-scoped
  capability (real keyboard events reaching whatever has real
  compositor focus, system-wide) than AT-SPI2's node-scoped
  `insert_text`, and deserves its own seam rather than quietly
  becoming a second implementation strategy inside `type_text()`.
- `application/desktop/terminal.py`'s own flow gains a real
  focus-verification step (see above) before the first keystroke,
  not just a bare call to `DesktopWindowPort.focus()`.
- `SecretPort` (ADR-0042) stores the `restore_token`; the adapter reads
  and rewrites it around each real session, handling first-use
  (`persist_mode` not yet granted) and steady-state (token present,
  replay it) as genuinely different code paths.
- `SandboxPort` is unaffected — portal calls are plain session-bus
  D-Bus, no raw display-socket access needed the way `_display_bind_
  paths()` (this pass's own fix) required for *displaying* the
  sandboxed terminal. Synthetic input injection and GUI display remain
  two separate concerns with two separate real mechanisms.

## Does this need a new ADR? Yes — likely more than one

This is a new, more powerful capability class than anything built so
far: the first mechanism in this project that can inject real keyboard
events reaching whatever the compositor has focused, system-wide, not
scoped to a specific accessible node or a specific sandboxed process.
That is a genuine security-relevant architectural decision, not an
implementation detail — per this project's own hard rule, it needs a
real ADR (or ADRs) before any code lands, not just this proposal.
What such an ADR would need to cover, listed here so the decision is
well-scoped when someone picks it up — **none of this is decided,
this is the question list, not the answers**:

- Whether `SyntheticInputPort` is its own port (this proposal's lean)
  or folded into `DesktopWindowPort` some other way, and why.
- The exact `focus()`-verification mechanism required before any real
  keystroke is sent, and what happens if it can't be verified (refuse
  to type? retry? how many times before giving up?).
- Whether `terminal.run`'s own `MANUAL_ONLY` tier needs any adjustment
  given the portal's own real permission dialog now exists as a
  second, OS-level gate — this proposal's own read is "no, the two
  stay independent," but that's exactly the kind of claim an ADR
  should state and justify explicitly, not inherit from a design doc.
- Real `restore_token` lifecycle: what happens on first-ever use (no
  token yet — portal dialog fires for real), on a stored token that
  the portal has since invalidated out-of-band (the user revoked it
  through their own desktop settings), and whether a failed replay
  should silently fall back to a fresh interactive grant or surface an
  explicit error.
- Whether this mechanism, once built for Terminal, should ever be
  reused for the Claude/ChatGPT desktop apps' own `type_text` (this
  proposal's own lean: **no**, or at least not without a fresh,
  explicit decision — those apps' AT-SPI2 `EditableText` path, where
  it works at all, is node-scoped and therefore structurally safer
  than compositor-wide injection; reusing the more powerful, less-
  targeted mechanism there without a real reason would be a step
  backward, not an improvement, and this proposal does not recommend
  it).

## Explicitly out of scope for this document

No code was written. No `RemoteDesktop.Start()`/`NotifyKeyboardKeysym`
call was ever made for real during this investigation — doing so would
have popped a real permission dialog on the user's live screen during
an unattended pass, exactly the kind of uninvited real-desktop action
this project's own rules exist to avoid. Every finding above comes
from read-only introspection (`gdbus introspect`), package metadata
(`dpkg`/`apt-cache`/`pip index`), and published portal documentation —
none of it required exercising the dangerous call.
