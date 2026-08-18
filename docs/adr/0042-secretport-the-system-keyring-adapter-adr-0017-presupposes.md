# ADR-0042: SecretPort -- the system-keyring adapter ADR-0017 presupposes

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-32 implementation finding (adapters/reasoning/family_a, family_b need a real credential to authenticate to a cloud provider)

## Context

ADR-0017 ("Secrets live only in the system keyring, referenced never stored") already states: *"Any code that needs a secret's actual value must go through the keyring adapter at the point of use, which is a deliberate extra hop."* It names "the keyring adapter" as though it already exists. It does not: there is no `SecretPort` (or equivalent) anywhere in `src/jarvis/ports/`, and no keyring-backed implementation anywhere in `src/jarvis/adapters/` -- confirmed by grep across the whole tree before writing this ADR. Nothing in WP-30's domain types, ADR-0038 through ADR-0041, or `docs/architecture/m2-reasoning-layer.md`'s deliverable #1 ("`ReasoningPort` + `ProviderProfile` + adapters... + shared contract test suite") specifies how those adapters actually obtain the CREDENTIAL-classified API key they need to authenticate to a real cloud provider. This went unnoticed until WP-32 needed to write the first piece of code in this repository that genuinely requires one.

This is exactly the gap CLAUDE.md's hard rule anticipates ("If something in this file or the docs seems wrong once you're implementing, stop, explain the problem, propose a fix as a new ADR, and wait for approval before proceeding") -- flagged to the user during WP-32, who chose to close it with a new port now rather than deferring it.

A real Secret Service (`org.freedesktop.secrets`, provided by `gnome-keyring-daemon` on this machine) is reachable on the session D-Bus in this repo's real development environment, confirmed live: `OpenSession` -> `CreateItem`/`SearchItems` -> `GetSecrets` round-tripped a real value end-to-end before any adapter code was written. `jeepney` is already a project dependency (used by `adapters/media_player.py` for MPRIS), and is the D-Bus library of choice per `docs/ROADMAP.md`'s persistence/D-Bus-library-choice framing -- no new third-party dependency is needed.

## Decision

Add `jarvis.ports.secret.SecretPort`, a single-method `Protocol`:

```python
def get_secret(self, reference: str) -> str: ...
```

Only a read exists, matching `FileSystemPort`'s "only what the real caller needs" minimalism (ADR-precedent, see that port's own docstring) -- `reference` identifies an already-provisioned secret (e.g. an API key a human stored via a normal secrets tool or a future `jarvis secret set` CLI, itself out of scope here); `SecretPort` does not add a `set_secret`/write path in this pass, since nothing in M2 needs to write one. `SecretNotFoundError` is defined on the port module, raised when no secret matches `reference`, mirroring `NoMediaPlayerRunningError`'s "defined on the port so any future adapter raises the same, technology-independent type" reasoning.

`jarvis.adapters.secret.SecretServiceAdapter` implements it for real against the freedesktop Secret Service D-Bus API, matching `MprisMediaPlayerAdapter`'s established shape exactly: the real wire mechanics (`OpenSession`, `SearchItems`, `GetSecrets`) live in one small, constructor-injectable function; a real, default implementation talks to the live session bus; pure logic (matching found items, decoding the secret value, raising `SecretNotFoundError`) is factored out separately so it can be unit-tested with a fake reply, no bus required. Items are looked up across all collections via `Service.SearchItems({"reference": reference})` (not scoped to one named collection), matching how `reference` is meant to be an opaque, caller-chosen handle, not a collection path. A locked collection is not unlocked automatically -- `SearchItems` returning the item only in its `locked` half surfaces as `SecretNotFoundError` (a false negative practically indistinguishable from "no such secret" until a real caller reports it), rather than building the full `Prompt`-object unlock flow, which no real M2 caller needs yet on a normal, already-unlocked desktop session (the same class of narrowing `MprisMediaPlayerAdapter`'s own docstring makes for its single-player-only discovery).

## Consequences

`adapters/reasoning/family_a.py` and `family_b.py` (WP-32, same change) take a `SecretPort` and a reference string at construction, and resolve the real credential value only at the point of use (matching ADR-0017's "deliberate extra hop" framing) -- never storing it as a field, never logging it, never letting it cross into `domain`/`application`/`ports`. `adapters/local.py` needs no credential and does not depend on this port at all.

This closes the literal gap ADR-0017 already presupposed rather than opening a new one: no port previously existed for "the keyring adapter" ADR-0017's own Consequences section refers to. `SecretPort` is reusable by any future capability needing a real secret (not scoped to M2 reasoning specifically), the same way `FileSystemPort` is reusable beyond the one capability that motivated it.

**Deliberately not done here**: a full `Prompt`-based unlock flow for a locked default collection, and any secret-write path. Both are real gaps if a locked-keyring or provision-a-new-secret scenario becomes load-bearing later; tracked as follow-up, not built speculatively against a scenario M2 does not need.
