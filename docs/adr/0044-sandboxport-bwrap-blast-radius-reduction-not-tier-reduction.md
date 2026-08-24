# ADR-0044: SandboxPort via bwrap -- blast-radius reduction, not tier reduction

## Status

Accepted

## Date

2026-08-24

## Source

`docs/architecture/m3-desktop-control.md` deliverable #2 (foundational), WP-43 feasibility spike, WP-45 implementation.

## Context

M3's design doc already named `bwrap` as the sandboxing mechanism and stated the blast-radius-reduction principle in prose. Per this project's hard rule (CLAUDE.md: "never silently change the architecture... propose a fix as a new ADR"), that decision needs a real ADR before `SandboxPort` is implemented, not just design-doc prose.

Confirmed live on the real development machine during WP-43/45 (not assumed from documentation):

- `bubblewrap 0.9.0` is installed (`/usr/bin/bwrap`).
- A real `bwrap --unshare-all` invocation, given only `--ro-bind /usr /usr --ro-bind /etc /etc` plus symlinked `/bin`/`/lib`/`/lib64`, a `--tmpfs /tmp`, and no network namespace sharing, genuinely denies outbound network (`socket.create_connection` to `8.8.8.8:53` raised `OSError: [Errno 101] Network is unreachable`) and genuinely denies filesystem access outside the bound paths (`open("/home/akash-polkar/.bashrc")` raised `FileNotFoundError` -- the path does not exist inside the sandbox's mount namespace at all, not merely a permission error).
- A path explicitly bound with `--bind <host-dir> /work` is genuinely writable from inside the sandbox and the write is genuinely visible on the host afterward.

This confirms `bwrap` does real, kernel-enforced containment (Linux user/mount/network namespaces) on this machine, not merely a documented flag. It requires no new system dependency beyond installing the `bubblewrap` package (already present here; CI needs `apt-get install bubblewrap` added alongside its existing PyGObject system-dependency install step).

The separate, real design question this ADR exists to settle: does running a capability inside a sandbox change what authorization tier it requires? M0's own precedent (ADR-0012: voice/speaker verification is a convenience filter, never an authorization boundary, because it can be defeated by replay/cloning) already establishes that a weaker-but-real signal never substitutes for a stronger structural requirement. A sandbox is exactly this kind of signal: real defense-in-depth, but not proof the underlying action stopped being dangerous. `bwrap` sandboxes are not proof against every escape (unprivileged user namespaces have a real, if narrow, kernel-CVE history), and even a perfect sandbox still lets a deliberately-granted mount (e.g. a real project directory bound in for Terminal/Docker/Git work) be destroyed by whatever runs inside it.

## Decision

Add `jarvis.ports.sandbox.SandboxPort`, a one-method `Protocol`:

```python
def run(
    self,
    command: tuple[str, ...],
    *,
    bind_paths: tuple[Path, ...] = (),
    allow_network: bool = False,
) -> CommandResult: ...
```

Reusing `CommandResult` from `jarvis.adapters.validation._command` (exit code, stdout, stderr) rather than inventing a second shape for the same concept -- the same reuse `adapters/workspace.py` and the validation adapters already share.

`jarvis.adapters.sandbox.BwrapSandboxAdapter` implements it for real via a `bwrap` subprocess: no network namespace sharing and no filesystem bind beyond `bind_paths` (plus the read-only `/usr`/`/etc`/`/bin`/`/lib`/`/lib64` scaffolding needed to exec anything at all) by default; `allow_network=True` is the one explicit escape hatch, for a future capability that genuinely needs it (none of M3's own capabilities set it).

**Blast-radius reduction, not tier reduction, stated as a hard rule**: `SandboxPort` never appears in `minimum_tier_for()` or anywhere in `domain/capability.py`'s tier calculus. A capability that floors `DESTRUCTIVE`/`IRREVERSIBLE`/`MANUAL_ONLY` floors there identically whether or not its implementation happens to route through `SandboxPort` -- the sandbox is chosen by the capability's own adapter as an implementation detail of *how* it runs a command, never as an input to *whether* it's authorized to. `AuthorizationOrchestrator`/`evaluate()` (domain/policy.py) are completely unaware `SandboxPort` exists; this is enforced structurally (no import of `jarvis.ports.sandbox` anywhere under `jarvis.domain`, already guaranteed by ADR-0029/C2's domain-purity contract) rather than by convention alone.

## Consequences

Every M3 capability whose real command execution is genuinely open-ended (Terminal, per ADR-0046) must route through `SandboxPort`; capabilities whose command is already a fixed, non-shell-interpolated argv (Docker, Git) do not need it, since the containment they need is "don't accept arbitrary text," which typed capability arguments already provide -- wrapping an already-bounded `docker`/`git` subprocess call in `bwrap` too would add complexity without closing a real gap those calls don't already have.

**Explicitly declined**: retrofitting `SandboxPort` onto M2's already-shipped, already-flagged-unsandboxed validators (`RuntimeCheckValidator`, `PytestValidator`, `UserScriptValidator` -- see `docs/threat-model/v0.md`'s "Milestone 2 additions"). `SandboxPort` is built here as general-purpose, reusable infrastructure that a future work package *could* retrofit onto those validators, but doing so is not part of M3's own scope (per `m3-desktop-control.md`'s "Relationship to M2" section, already decided before this ADR). Tracked as a real, open follow-up, not silently dropped.

**Not decided here, real gap**: numeric resource limits (CPU/memory/pid caps) beyond filesystem and network isolation. `bwrap` alone does not enforce these (cgroup limits would need to be layered on separately, e.g. via `systemd-run --scope` or a cgroup v2 delegation, neither of which was verified live during this pass). A sandboxed command can still exhaust host CPU/memory/disk even though it cannot reach the network or the host filesystem outside its bound paths. Flagged honestly as a real, unaddressed gap rather than assumed covered by "sandboxing."
