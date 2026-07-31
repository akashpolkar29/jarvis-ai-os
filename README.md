# JARVIS AI OS

Privacy-first, plugin-based agent kernel for Linux.

**Status:** pre-alpha, Milestone 0 (repository scaffold). Nothing here runs
yet — this work package establishes the project layout and the quality
gates every later work package must pass.

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
  against the active tier (`ALLOW` / `CONFIRM` / `MANUAL_ONLY` /
  `DENY`). There is no command blocklist anywhere else in the system.
- **`adapters`** implement ports against real, named technologies.
- **`kernel`** is the composition root that wires adapters, ports, and
  use cases together.
- **`ipc`** / **`cli`** are the outermost rings: transport and
  command-line entry point.

Everything the kernel knows about is a capability, not an agent — new
features are plugins built against `jarvis.plugin_api`, which depends on
`domain` only.

See `docs/architecture/` for the full, approved design and `docs/adr/`
for the individual decisions behind it.

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
to the machine is the real auth boundary.

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
| Domain coverage | `uv run coverage report --include="src/jarvis/domain/*"` |
| Policy engine coverage | `uv run coverage report --include="src/jarvis/application/policy/*"` |

Coverage is gated per-package rather than globally so that an untested
policy engine can't hide behind well-tested glue code elsewhere. See
`.github/workflows/ci.yml` for the exact, current thresholds.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit
conventions, and the process for proposing an architecture change.

## License

MIT — see [LICENSE](LICENSE).
