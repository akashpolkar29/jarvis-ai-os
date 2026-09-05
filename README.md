# JARVIS AI OS

Privacy-first, plugin-based agent kernel for Linux.

**Status:** pre-alpha. Milestones 0 through 6 are code-complete;
milestones 4, 5, and 6 are tagged (`v0.4.0`, `v0.5.0`, `v0.6.0`,
tagged out of strict milestone-sequential order — milestone 3's own
tag remains a deliberately separate, later action). Milestone 3
(desktop control) is code-complete but not yet tagged. See
`docs/ROADMAP.md` and `CLAUDE.md`'s own "Current Status" section for
the exact, current state of each milestone, including what's real,
what's live-verified, and what real gaps remain open.

What works today: a capability-based policy engine enforcing a
four-tier authorization ladder (`ALLOW`/`CONFIRM`/`MANUAL_ONLY`/`DENY`),
a hash-chained and persisted audit log, a capability registry with 38
real, statically-registered capabilities (plus several dynamic-effect
ones whose tier depends on argument content), and a working `jarvis`
CLI covering voice interaction, multi-provider reasoning, desktop
control (Brave, VS Code, the Claude/ChatGPT desktop apps, Docker, Git),
memory/retrieval with backup/restore/wipe, browser automation, a
sandboxed coding agent, email/calendar (IMAP/SMTP/CalDAV), and
job-application research/drafting (research and drafting only — no
auto-apply, a structural boundary, not a policy-tier gate). See
`docs/protocol/README.md` for the real, current CLI surface,
`docs/plugin-guide/`, and `docs/threat-model/v0.md` for exactly what's
real, what's verified, and what isn't.

## Try it

```sh
uv sync --all-groups
uv run jarvis ping --chain-path /tmp/audit_chain.json
uv run jarvis read ~/some-file.txt --chain-path /tmp/audit_chain.json
uv run jarvis pause --physical-confirmation-available --chain-path /tmp/audit_chain.json
uv run jarvis audit-history --chain-path /tmp/audit_chain.json
uv run jarvis --help
```

Every invocation authorizes (and, if granted, runs) exactly one
capability, then appends a record to the audit chain at
`--chain-path`. See `docs/protocol/README.md` for the full CLI
interface, and `docs/threat-model/v0.md` before assuming more
protection than currently exists — in particular, confirmation flags
are currently self-reported with no real presence detection behind
them (a real `Gtk4PhysicalConfirmationAdapter` backs `jarvis listen`
specifically; every other subcommand's flags are still a direct,
unverified CLI argument).

## Architecture

JARVIS follows Clean Architecture / ports-and-adapters, with the
dependency rule pointing strictly inward:

```
domain -> ports -> application -> adapters -> kernel -> ipc / cli
```

- **`domain`** is pure and stdlib-only: capabilities, effects, policy
  tiers, provenance, and the `Tainted[T]` wrapper. No I/O, no async, no
  wall clock.
- **`ports`** are `Protocol`s describing roles (a clock, an id
  generator, a reasoning provider, storage, audio) without naming a
  vendor.
- **`application`** holds use cases, including the policy engine: the
  single choke point that evaluates a capability's declared effects
  against the active tier. There is no command blocklist anywhere else
  in the system.
- **`adapters`** implement ports against real, named technologies.
- **`kernel`** is the composition root that wires adapters, ports, and
  use cases together into real, invocable capabilities.
- **`ipc`** / **`cli`** are the outermost rings: transport and
  command-line entry point. `jarvis.ipc` has no real content yet —
  every CLI invocation boots the kernel directly, in-process; see
  `docs/protocol/README.md`.

Everything the kernel knows about is a capability, not an agent — new
features are meant to be plugins built against `jarvis.plugin_api`,
which depends on `domain` only and now has real content: the narrow
subset of domain vocabulary (`CapabilityDescriptor`, `Effect`, `Tier`,
`Tainted`, `Provenance`, etc.) a plugin author needs to *describe* a
new capability. A real, minimal, working example lives at
`docs/plugin-guide/example_plugin.py`. **What plugin support does not
yet include**: dynamic, out-of-tree plugin loading. Wiring a described
capability into the real, running registry
(`kernel/capabilities.py::build_default_registry()`) still means
editing a file inside this source tree — see `docs/plugin-guide/README.md`
for exactly how, worked from the capabilities that already exist.

See `docs/architecture/` for the full, approved design and `docs/adr/`
for the individual decisions behind it.

## Documentation

- **[`docs/protocol/README.md`](docs/protocol/README.md)** — the
  actual, current CLI interface: every real subcommand, the capability
  it authorizes, its extra arguments, flags, exit codes, and what gets
  audited.
- **[`docs/plugin-guide/README.md`](docs/plugin-guide/README.md)** —
  how to add a new capability today, worked from real, existing ones.
- **[`docs/threat-model/v0.md`](docs/threat-model/v0.md)** — what is
  and isn't actually defended against right now. Read this before
  trusting the system with anything that matters. It is a long,
  running, dated log of every real finding across every milestone, not
  a short summary — search it for a specific capability or concern
  rather than reading start to finish.
- **[`docs/ROADMAP.md`](docs/ROADMAP.md)** — the real, current roadmap
  and milestone status.
- **[`CLAUDE.md`](CLAUDE.md)** — this project's own working agreement
  and the single most current, detailed account of what's built, what
  was verified live, and what real gaps remain open at each milestone.

## Privacy model

Every value in the system carries provenance: a trust level
(`USER_DIRECT` / `SYSTEM` / `UNTRUSTED_EXTERNAL`) and a classification
(`PUBLIC` / `PERSONAL` / `SENSITIVE` / `SECRET`). `SECRET` data — API
keys, passwords, tokens — is never sent to a cloud provider and never
enters model context, no exceptions. `SENSITIVE` data may be sent to a
cloud provider only behind an explicit `CONFIRM`. Where classification
is uncertain, the system fails closed. Secrets live only in the system
keyring. Audio is never persisted to disk. Voice/speaker verification is
a convenience filter, never an authorization boundary — physical access
to the machine is the real auth boundary, mechanically enforced (see
`tests/meta/test_speaker_id_isolation.py`), not merely a stated
principle.

**Two real, known license-compatibility findings, not yet resolved**:
`piper-tts` (the real text-to-speech engine, imported directly
in-process) is GPL-3.0-or-later; `icalendar-searcher` (a real,
exercised transitive dependency of the CalDAV calendar adapter) is
AGPL-3.0-or-later. Both raise real questions for this MIT-licensed
project that have not yet been decided — see
`docs/architecture/secrets-license-sbom-audit-phase9.md` for the full
finding. A real, current CycloneDX SBOM is available at
`docs/architecture/sbom.cyclonedx.json` (`scripts/generate_sbom.sh`
regenerates it on demand).

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency and
workspace management, and requires Python >= 3.12.

```sh
uv sync --all-groups
uv run pre-commit install
```

## Quality gates

Every work package must pass all of the following before it is
considered done:

| Gate | Command |
| --- | --- |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types | `uv run mypy --strict src tests` |
| Architecture boundaries | `uv run lint-imports` |
| Tests | `uv run pytest` |
| Domain coverage | `uv run coverage report --include="src/jarvis/domain/*" --fail-under=100` |
| Policy engine coverage | `uv run coverage report --include="src/jarvis/application/policy/*" --fail-under=100` |
| Reasoning layer coverage | `uv run coverage report --include="src/jarvis/application/reasoning/*" --fail-under=100` |
| API reference builds | `uv run sphinx-build -b html docs/api docs/api/_build` |

Coverage is gated per-package rather than globally so that an untested
policy engine or reasoning layer can't hide behind well-tested glue
code elsewhere. See `.github/workflows/ci.yml` for the exact, current
gate set (it also starts real, local, credential-free IMAP/SMTP/CalDAV
test servers for the integration suite).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit
conventions, and the process for proposing an architecture change.

## License

MIT — see [LICENSE](LICENSE). See "Privacy model" above for two real,
unresolved dependency-license findings.
