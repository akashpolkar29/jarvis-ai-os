# Contributing

## Workflow

Work proceeds one work package at a time. `docs/architecture/roadmap.md`
does not exist yet (see `docs/architecture/README.md`) — sequencing
and scope currently come directly from whoever is directing the work,
not from a roadmap file. If `roadmap.md` is ever supplied, this section
should reference it for real. Each work package moves through
Analysis -> Plan -> Implement -> Verify -> Review, as described in
`CLAUDE.md`. Don't start a work package before the previous one has been
reviewed, and don't fold a future work package's scope into the current
one, even opportunistically.

## Branches and commits

- Branch names: `wp/NN-slug`, e.g. `wp/01-repo-scaffold`.
- Commit messages follow [Conventional
  Commits](https://www.conventionalcommits.org/).
- Pull requests are squash-merged into `main`, one commit per work
  package.
- Git tags are cut at milestone completion only, never mid-milestone.

## Before opening a pull request

Install the pre-commit hooks once:

```sh
uv run pre-commit install
```

All quality gates listed in `README.md` must pass locally. `mypy` and
`pytest` are intentionally not part of the pre-commit hook (they're slow
enough that a hook gets bypassed) — CI runs them on every push and
that's where they're actually enforced.

## Changing the architecture

`docs/architecture/` and `docs/adr/` are the approved, frozen source of
truth. If implementation reveals that the approved design is wrong:

1. Stop implementing against the old design.
2. Write a new ADR under `docs/adr/` (copy `docs/adr/template.md`)
   proposing the change, with real Context / Decision / Consequences
   sections.
3. Wait for the ADR to be reviewed and accepted before writing code
   against it.

Never change the architecture silently to make an implementation
problem go away.

## Determinism

Code under `src/` must not read the wall clock or generate random
identifiers directly (`datetime.now()`, `time.time()`,
`time.monotonic()`, `uuid.uuid4()`, etc. are all banned). Inject a
`ClockPort` / `IdPort` instead, so behavior is reproducible in tests and
in the audit log.

## Secrets

Secrets (API keys, tokens, passwords) are never committed to source,
never written to the database, and never appear in the audit log — even
as part of a logged argument. They live only in the system keyring and
are referenced, not stored, everywhere else. If you find a secret in a
diff, treat it as compromised and rotate it; don't just remove it from
the file.
