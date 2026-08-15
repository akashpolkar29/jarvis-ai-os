# ADR-0035: A genuine physical-keypress ConfirmationPort closes threat-model Finding 2

## Status

Accepted

## Date

2026-08-15

## Source

Work package WP-24 implementation (PhysicalConfirmationPort + Gtk4PhysicalConfirmationAdapter)

## Context

M0's threat model (docs/threat-model/v0.md, Finding 2) ended with an honest admission: CONFIRM and MANUAL_ONLY provided identical real-world protection, because the only `ConfirmationPort` adapter that existed (`ManualConfirmationAdapter`) just echoed back a constructor-supplied boolean. Anyone who could run the process could claim physical presence and have it accepted at face value. Once voice input exists at all, this stops being a theoretical gap: a spoken command, a recording, or a voice clone could satisfy MANUAL_ONLY exactly as well as a CLI flag already could.

## Decision

`PhysicalConfirmationPort.await_physical_confirmation(prompt: str, timeout_s: float) -> bool` is a new, separate port from `ConfirmationPort` -- not a new `ConfirmationPort` adapter -- because the two answer genuinely different questions. `ConfirmationPort.get_context()` is a cheap, synchronous "what confirmation channels are available right now" query that `PolicyContext` is built from. `PhysicalConfirmationPort` is an async, blocking, per-action question: "does a real human, right now, physically approve *this specific* request." `ManualConfirmationAdapter`/`ConfirmationPort` remain completely untouched and stay in use alongside this port, per the M1 doc's own recommendation (open question 3) -- true by construction, not by choice made under pressure, since nothing about adding a second port required touching the first.

`Gtk4PhysicalConfirmationAdapter` implements the new port by showing a real GTK4 window (`jarvis.ui.confirm.dialog`, the first real UI code in this project, kept to zero knowledge of any other `jarvis` package by import-linter contract C5 "ui privilege") with Approve/Deny buttons. A click only counts as approval if it is backed by a genuine `Gdk.Event` carrying a real input device (`_is_genuine_physical_event`) -- a signal fired with no such event, exactly what an in-process `button.emit("clicked")`/`button.activate()` call would produce, is silently ignored, never treated as a decision. This defends against software-only confirmation forgery; it is not claimed to defend against an attacker who already has root or `/dev/uinput` access, a strictly stronger capability than voice or network access, matching this project's own threat model's existing caveat about MANUAL_ONLY.

Manual, end-to-end verification (`poc/wp24_verify_dialog.py`, run by Akash directly, not simulated) caught two real defects the design alone did not surface:

1. `Gtk.get_current_event()` -- the module-level function the first implementation used to recover the triggering event inside `GtkButton`'s "clicked" handler -- does not exist in this project's actual GTK4 4.14 / PyGObject 3.56 install. The architecture doc's assumption about the API was wrong; the real, working mechanism is `Gtk.GestureClick`, attached per-button, read via `EventController.get_current_event()`.
2. With that crash fixed, a genuine physical click on Approve still returned `False`. `GtkButton` runs its own internal click gesture on the same widget, and the added `Gtk.GestureClick` was losing GTK4's gesture-sequence-claim arbitration to it -- `"pressed"` fired but `"released"` never did, on either button, ever, so the genuineness check was never actually being exercised at all. This was serious specifically because it was silent: "Deny" and "Timeout" scenarios were coincidentally "passing" only because both already expect `False`, which a permanently-broken detector produces regardless of what is actually clicked -- exactly the systemic false-negative failure mode a less thorough verification pass could have missed. Fixed with an explicit `gesture.set_state(Gtk.EventSequenceState.CLAIMED)` in the "pressed" handler.

## Consequences

MANUAL_ONLY now requires a physical keypress/click that voice alone cannot produce, closing Finding 2 for real. `tests/unit/test_confirmation_dialog.py` proves the event-genuineness predicate rejects both a missing event and a device-less one -- the mechanical form of "a simulated or injected keypress event is rejected," per the M1 doc's own threat-model addition (section 5). The real dialog path itself remains outside the automated suite by design (it needs a real display and a real human), proven instead by the manual verification above, which is recorded here specifically because it changed the implementation, not just confirmed it.
