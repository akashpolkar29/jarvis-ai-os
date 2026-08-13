# Protocol

No JSON-RPC/IPC protocol exists yet. `jarvis.ipc` — the wire protocol
originally planned for clients (CLI, a future voice frontend, a future
GUI) to talk to a running kernel over a transport — has no real
content. `cli/main.py` boots the kernel directly, in-process, for
every invocation (see `cli/__init__.py`'s own docstring). This
document describes what actually exists today instead: the CLI's argv
interface, which is the only "protocol" JARVIS has right now.

This will need a real rewrite once `jarvis.ipc` exists; until then, it
documents the real thing rather than staying an empty placeholder for
a future that hasn't landed.

## Invocation

```sh
jarvis <subcommand> [options]
```

installed via the `jarvis` console script (`pyproject.toml`'s
`[project.scripts]`), or `python -m jarvis.cli` directly from source.

## Subcommands

| Subcommand | Capability authorized | Extra arguments |
| --- | --- | --- |
| `ping` | `ping` | none |
| `play` | `music.play` | none |
| `pause` | `music.pause` | none |
| `next` | `music.next` | none |
| `previous` | `music.previous` | none |
| `read <path>` | `fs.read_file` | `path` (positional) |

Every subcommand shares three flags:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--physical-confirmation-available` / `--no-physical-confirmation-available` | `false` | Passed to the constructed `ManualConfirmationAdapter` — see `docs/threat-model/v0.md` for what this flag actually does and doesn't guarantee. |
| `--remote-confirmation-available` / `--no-remote-confirmation-available` | `false` | As above, for remote confirmation. |
| `--chain-path PATH` | `./audit_chain.json` | Where the audit chain is loaded from and saved back to. |

## Output

On success or a normal denial, one line to stdout:

```
<subcommand>: GRANTED (tier=<TIER>, reasons=<REASONS>)
<subcommand>: DENIED (tier=<TIER>, reasons=<REASONS>)
```

`<TIER>` is one of `ALLOW`/`CONFIRM`/`MANUAL_ONLY`/`DENY`. `<REASONS>`
is the `DecisionReason` flag combination that produced the outcome
(e.g. `DecisionReason.BASE_TIER`, or
`DecisionReason.BASE_TIER|NO_REMOTE_CONFIRMATION` when a `CONFIRM`-tier
capability is denied for lack of either confirmation channel).

`read`, when granted, prints the file's content after the decision
line.

On any error — a denied path-scope check, a missing file, a rejected
D-Bus call, a tampered audit chain, anything else — one line to
stderr:

```
Error: <message>
```

## Exit codes

- **`0`** — the capability was granted.
- **`1`** — the capability was denied, **or** any of the following
  was raised: a domain-level `JarvisError` (e.g. a tampered audit
  chain), `NoMediaPlayerRunningError`, `MediaPlayerCommandFailedError`,
  `PathOutsideAllowedScopeError`, any `OSError` (a missing file, a
  directory instead of a file, a permission error), or
  `UnicodeDecodeError` (a non-UTF-8 file).

There is currently no exit code that distinguishes "denied" from "an
error occurred" — both are `1`. A caller that needs to tell them apart
today has to parse stdout/stderr.

## What gets audited

Every `authorize_by_id()` call — granted or denied — appends exactly
one record to the chain at `--chain-path`, whether or not the
subsequent real-world action (if any) succeeds. One documented
exception: `read` against a path outside the allowed root is rejected
*before* authorization ever runs and produces **no** audit record at
all — see Gap 4 in `docs/threat-model/v0.md`.

Audited argument content is digest-only, per
`docs/adr/0027-audit-log-never-stores-argument-values-only-digests.md`
— only a sha256 digest of an argument value is ever persisted, never
the value itself. `Provenance` metadata (trust, classification,
sources) is not covered by this and is persisted in full — see
Gap 1 (resolved) in `docs/threat-model/v0.md` for the exact scope and
consequences, including that a pre-work-package-18 `--chain-path` file
can no longer be loaded.
