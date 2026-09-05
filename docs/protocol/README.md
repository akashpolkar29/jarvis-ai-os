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
`jarvis --version` prints the real, installed package version
(`importlib.metadata.version("jarvis")`) and exits -- not a
subcommand, not a capability, no audit record, the same real design
choice `doctor` makes (see `docs/architecture/jarvis-doctor.md`).

## Subcommands

**Updated 2026-09-05 — this table previously listed only the original
5 M0 subcommands; it now covers all 33 real, current ones.** Each
capability's own real effect/tier classification is documented at its
own registration site in `kernel/capabilities.py`, not repeated here —
this table exists to answer "what does this subcommand actually call,"
not to duplicate the policy engine's own reasoning.

| Subcommand | Capability authorized | Extra arguments |
| --- | --- | --- |
| `ping` | `ping` | none |
| `audit-history` | `audit.history` | `--limit N`, `--capability-id ID` (both optional) |
| `play` | `music.play` | none |
| `pause` | `music.pause` | none |
| `next` | `music.next` | none |
| `previous` | `music.previous` | none |
| `read <path>` | `fs.read_file` | `path` |
| `list-dir <path>` | `fs.list_dir` | `path` |
| `move-file <source> <destination>` | `fs.move_file` | `source`, `destination` |
| `delete-file <path>` | `fs.delete_file` | `path` |
| `memory write <text>` | `memory.write` (dynamic effect — see `ADR-0049`) | `text` |
| `memory retrieve <query>` | `memory.retrieve` | `query`, `--limit` |
| `memory forget <identifier>` | `memory.forget` | `identifier` |
| `memory pin <identifier>` | `memory.pin` | `identifier` |
| `memory backup <destination>` | `memory.backup` | `destination` |
| `memory restore <source>` | `memory.restore` | `source` |
| `memory wipe` | `memory.wipe` | none |
| `send-email <to...>` | `communications.send_email` (dynamic effect — see `ADR-0057`/`ADR-0059`) | one or more recipients, `--subject`, `--body`, `--imap-host`, `--smtp-host`, `--username`, `--password-reference` |
| `create-calendar-event` | `communications.create_calendar_event` (dynamic effect) | `--summary`, `--start`, `--end`, `--attendee` (repeatable), `--caldav-url`, `--username`, `--password-reference` |
| `code <task> <repo-path>` | `coding.run_task` | `task`, `repo-path` |
| `draft <task>` | `job_assistance.draft` (dynamic effect) | `task` |
| `open-brave-url <url>` | `desktop.brave_open_url` | `url` |
| `open-vscode-file <path>` | `desktop.vscode_open_file` | `path` |
| `send-claude-text <text>` | `desktop.claude_app_send_text` | `text` |
| `send-chatgpt-text <text>` | `desktop.chatgpt_app_send_text` | `text` |
| `list-docker-containers` | `docker.list_containers` | none |
| `stop-docker-container <container>` | `docker.stop_container` | `container` |
| `git-status <repo-dir>` | `git.status` | `repo-dir` |
| `git-create-branch <repo-dir> <branch-name>` | `git.create_branch` | `repo-dir`, `branch-name` |
| `git-commit <repo-dir> <message>` | `git.commit` | `repo-dir`, `message` |
| `git-push <repo-dir> <remote> <branch>` | `git.push` | `repo-dir`, `remote`, `branch` |
| `git-force-push <repo-dir> <remote> <branch>` | `git.force_push` | `repo-dir`, `remote`, `branch` |
| `listen` | (runs the voice loop continuously; no single capability) | `--verbose` |
| `doctor` | *(no capability -- not authorized, no audit record; see `docs/architecture/jarvis-doctor.md`)* | none |

**Two real, deliberate naming inconsistencies, not yet resolved** (see
`docs/architecture/plugin-architecture-and-cli-ux-audit-phase8.md` for
the full finding): `memory` is the only capability family using a
nested subcommand group (`memory write`/`retrieve`/...) rather than a
flat, hyphenated top-level command like every other family; `read`
(the original M0 command) doesn't include its own noun the way its
later siblings `list-dir`/`move-file`/`delete-file` do. Both are
historical accretion, not a deliberate design choice, and neither has
been renamed — a rename would be a real, user-facing breaking change.

`send-email`/`create-calendar-event` have no default adapter
configuration (real per-deployment IMAP/SMTP/CalDAV settings, not this
project's decision) — the four/three flags above are required, with
no default, every invocation.

`listen` does not take `--physical-confirmation-available`/
`--remote-confirmation-available` — it asks a real, per-utterance
question through a real GTK4 confirmation dialog instead of modeling a
fixed, upfront confirmation state.

Every other subcommand shares three flags:

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

Every real authorization call — `authorize_by_id()` for a static
capability, or `authorize()` directly for a dynamic-effect one like
`memory.write`/`send-email`/`draft` — appends exactly one record to
the chain at `--chain-path`, granted or denied, whether or not the
subsequent real-world action (if any) succeeds. One documented
exception: `read`/`list-dir`/`move-file`/`delete-file` against a path
outside the allowed root is rejected *before* authorization ever runs
and produces **no** audit record at all — see Gap 4 in
`docs/threat-model/v0.md`.

Audited argument content is digest-only, per
`docs/adr/0027-audit-log-never-stores-argument-values-only-digests.md`
— only a sha256 digest of an argument value is ever persisted, never
the value itself. `Provenance` metadata (trust, classification,
sources) is not covered by this and is persisted in full — see
Gap 1 (resolved) in `docs/threat-model/v0.md` for the exact scope and
consequences, including that a pre-work-package-18 `--chain-path` file
can no longer be loaded.
