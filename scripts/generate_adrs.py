"""Generate the numbered ADRs under docs/adr/ from a single source list.

Regenerable and reviewable as one script, rather than as dozens of
individually hand-maintained markdown files that would drift from a
common template. Re-run this script (``uv run python
scripts/generate_adrs.py``) any time an entry in ``RAW_DECISIONS``
changes; it overwrites the generated files in place.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = REPO_ROOT / "docs" / "adr"
DECISION_DATE = "2026-07-31"
SOURCE = "CLAUDE.md architecture summary, Milestone 0"


@dataclass(frozen=True)
class Adr:
    """One architecture decision record, ready to render as markdown."""

    number: int
    title: str
    context: str
    decision: str
    consequences: str
    status: str = "Accepted"


def slugify(title: str) -> str:
    """Turn a title into a filename-safe slug."""
    lowered = title.lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def render(adr: Adr) -> str:
    """Render one Adr as markdown matching the docs/adr/template.md structure."""
    return (
        f"# ADR-{adr.number:04d}: {adr.title}\n\n"
        f"## Status\n\n{adr.status}\n\n"
        f"## Date\n\n{DECISION_DATE}\n\n"
        f"## Source\n\n{SOURCE}\n\n"
        f"## Context\n\n{adr.context}\n\n"
        f"## Decision\n\n{adr.decision}\n\n"
        f"## Consequences\n\n{adr.consequences}\n"
    )


def write_all(adrs: list[Adr], destination: Path) -> list[Path]:
    """Render and write every Adr under `destination`, returning the paths written."""
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for adr in adrs:
        path = destination / f"{adr.number:04d}-{slugify(adr.title)}.md"
        path.write_text(render(adr), encoding="utf-8")
        written.append(path)
        logger.info("wrote %s", path)
    return written


# (title, context, decision, consequences) - number is assigned by position.
RAW_DECISIONS: list[tuple[str, str, str, str]] = [
    (
        "Ports-and-adapters layered architecture",
        "JARVIS mixes untrusted external input, credentials, and destructive "
        "local actions in one process; without an enforced boundary, business "
        "rules end up entangled with whichever library or vendor SDK happened "
        "to be convenient at the time, making privacy and safety guarantees "
        "unverifiable by inspection.",
        "Adopt Clean Architecture / ports-and-adapters with a strict inward "
        "dependency rule: domain -> ports -> application -> adapters -> "
        "kernel -> ipc/cli. Each ring may depend only on rings before it in "
        "that list; import-linter contracts enforce this at CI time, not "
        "just in review.",
        "Business rules (capabilities, effects, policy, provenance) can be "
        "reasoned about and tested without a running adapter, database, or "
        "network. The cost is boilerplate: every new integration needs a "
        "port defined before an adapter can implement it, and the layering "
        "must be re-verified (via import-linter) every time a new package "
        "is added.",
    ),
    (
        "Capabilities, not agents, as the kernel's unit of extension",
        'A system that grows by adding named "agents" (an email agent, a '
        "calendar agent) tends to accrete integration-specific logic into "
        "the kernel itself, and each new agent becomes another place that "
        "needs its own security review.",
        "The kernel knows only about capabilities - declared units of "
        "effect-bearing behavior - never about specific agents or "
        "integrations. New functionality is added as a plugin behind "
        "jarvis.plugin_api; nothing in domain, application, or ports names "
        "a specific integration.",
        "The kernel's trusted computing base stays fixed in size as "
        "functionality grows; a plugin vulnerability is contained to what "
        "its declared capabilities allow. The cost is that every capability "
        "must be modeled generically enough to fit the effect/tier "
        "vocabulary, which is more design work up front than a bespoke "
        "integration.",
    ),
    (
        "No shell: capabilities declare typed effects instead of commands",
        'A generic "run this shell command" capability is the single most '
        "dangerous primitive an LLM-driven agent can be given - it "
        "collapses every possible action into one unauditable string, and "
        'any blocklist of "dangerous" commands is provably incomplete.',
        "Agents are never given shell access. Every capability instead "
        "declares its effects using a fixed, typed vocabulary (READ_LOCAL, "
        "WRITE_LOCAL, DESTRUCTIVE, IRREVERSIBLE, CREDENTIAL, "
        "EGRESS_SENSITIVE, etc.), and the policy engine evaluates those "
        "declared effects - never the literal action being taken.",
        "Every capability's worst-case behavior is knowable statically from "
        "its declared effects, before it ever runs. The limitation is "
        "expressiveness: a capability that doesn't fit the existing effect "
        "vocabulary needs the vocabulary extended (via ADR), not worked "
        "around with a custom flag.",
    ),
    (
        "A fixed, typed effect taxonomy",
        "Without a closed, shared vocabulary of effects, each capability "
        'author would invent their own notion of "risky," making it '
        "impossible for one policy engine to reason about all of them "
        "consistently.",
        "Effects are drawn from a single closed enumeration - READ_LOCAL, "
        "WRITE_LOCAL, DESTRUCTIVE, IRREVERSIBLE, CREDENTIAL, "
        "EGRESS_SENSITIVE (extended over time via ADR, never ad hoc) - and "
        "every capability declares the full set of effects it can produce.",
        "The policy engine can be exhaustive and simple. Extending the "
        "taxonomy is a deliberate, reviewed act (a new ADR), not a side "
        "effect of adding a capability, which is friction by design.",
    ),
    (
        "A single policy engine as the sole authorization choke point",
        "If authorization checks are scattered across capability "
        "implementations, a single missed check anywhere in the codebase is "
        "a security hole, and no amount of code review can guarantee there "
        "isn't one.",
        "Exactly one policy engine (application/policy) evaluates a "
        "capability's declared effects, the tier, and the provenance of the "
        "data involved, at exactly one point in the call path before any "
        "capability executes.",
        "A security review of authorization logic means reading one module, "
        "not auditing every capability implementation. The cost is a small "
        'amount of indirection: capabilities cannot "just check something '
        'quickly" themselves - every check goes through the engine.',
    ),
    (
        "Four-tier policy model: ALLOW / CONFIRM / MANUAL_ONLY / DENY",
        'A binary allow/deny model can\'t express "this is fine unattended" '
        'vs "this needs the user to look at it" vs "this needs the user\'s '
        'hands on the keyboard," which are three meaningfully different '
        "postures for an autonomous agent.",
        "The policy engine resolves every capability invocation to exactly "
        "one of four tiers: ALLOW (proceeds unattended), CONFIRM (needs an "
        "acknowledgment), MANUAL_ONLY (needs the user to physically perform "
        "or explicitly authorize the step), or DENY.",
        "UI and audit logic can be written once against four well-defined "
        "outcomes. Adding a fifth tier later is a breaking change to every "
        "piece of code that pattern-matches on this enum, so the tier set "
        "itself is not expected to grow casually.",
    ),
    (
        "No command blocklists, ever",
        "Blocklists (banned commands, banned strings) are a well-known "
        "losing pattern in security: the attacker (or an "
        "adversarially-prompted model) only needs to find one encoding the "
        "blocklist author didn't think of.",
        'The system never implements a blocklist of "dangerous" commands '
        "or strings as a security control. All authorization is "
        "effect-based, evaluated by the policy engine described in the "
        "effect-taxonomy and policy-engine ADRs.",
        'There is no list to keep "complete" and no false sense of '
        "security from one. Anyone tempted to add a quick blocklist as a "
        "stopgap must instead model the risk as a capability effect - "
        "slower, but the only version of this control that has held up "
        "over time.",
    ),
    (
        "Provenance trust dimension: USER_DIRECT / SYSTEM / UNTRUSTED_EXTERNAL",
        "Not all input to the system is equally trustworthy - a value typed "
        "directly by the user, a value produced by JARVIS's own internals, "
        "and a value scraped from a web page or received in an email all "
        "carry different risk, but a naive implementation treats them as "
        "interchangeable strings once they're in memory.",
        "Every value that crosses a boundary is tagged with a trust level - "
        "USER_DIRECT, SYSTEM, or UNTRUSTED_EXTERNAL - as part of its "
        "provenance, tracked through the domain model rather than inferred "
        "ad hoc at each use site.",
        "Downstream logic (especially the policy engine) can make "
        "trust-sensitive decisions without re-deriving where a value came "
        "from. The cost is that every boundary-crossing adapter must "
        "correctly assign a trust level at the point of ingestion - an "
        "omission there is a silent trust-downgrade bug.",
    ),
    (
        "Provenance classification dimension: PUBLIC / PERSONAL / SENSITIVE / SECRET",
        "Trust (where a value came from) and sensitivity (what it would "
        "cost to leak) are different axes - a SECRET can be USER_DIRECT (a "
        "password the user just typed) and an UNTRUSTED_EXTERNAL value can "
        "still be PUBLIC (a public web page).",
        "Every value additionally carries a classification - PUBLIC, "
        "PERSONAL, SENSITIVE, or SECRET - independent of its trust level, "
        "together forming its full provenance.",
        "The privacy policy (see the cloud-routing ADRs) can be expressed "
        "purely in terms of classification, decoupled from trust. This "
        "doubles the tagging burden at every ingestion point relative to a "
        "single-axis model, which is accepted as the cost of getting "
        "privacy routing right.",
    ),
    (
        "Tainted[T] wrapper for provenance-carrying values",
        "Provenance metadata that lives in a side table or convention (e.g. "
        '"trust the caller to check") gets silently dropped the moment a '
        "value is copied, transformed, or passed through a function that "
        "wasn't written with it in mind.",
        "Every value with tracked provenance is represented as a generic "
        "Tainted[T] wrapper carrying both the payload and its provenance, "
        "so provenance travels with the value through the type system "
        "rather than through discipline.",
        "mypy --strict can catch a function that silently unwraps or "
        "discards provenance where it shouldn't. The cost is wrapper "
        "ceremony throughout the domain and application layers - every "
        "function boundary that touches external data must thread "
        "Tainted[T] through instead of the bare type.",
    ),
    (
        "Untrusted external content auto-escalates the required tier",
        "Content originating outside the user's direct control - a web "
        "page, an email body, a README fetched from the internet - can "
        "contain instructions aimed at the agent itself (prompt injection), "
        "and treating it as equivalent to a direct user instruction is the "
        "single most common way such systems get compromised.",
        "Any value whose trust level is UNTRUSTED_EXTERNAL automatically "
        "raises the minimum policy tier required for any capability "
        "invocation it influences, regardless of what that capability would "
        "otherwise require.",
        "A prompt-injection payload embedded in fetched content cannot, by "
        "itself, unlock a MANUAL_ONLY-tier action at ALLOW. The cost is "
        "more CONFIRM/MANUAL_ONLY friction whenever the agent is working "
        "with fetched external content, even when the content turns out to "
        "be benign.",
    ),
    (
        "Voice/speaker verification is a convenience filter, not an authorization boundary",
        "Speaker verification is defeated by replay attacks and, "
        "increasingly, by cheap voice cloning; treating a verified "
        "voiceprint as proof of identity for authorization purposes would "
        "be relying on a control known to be breakable.",
        "Voice and speaker verification may be used to personalize "
        "behavior or reduce friction, but are never sufficient, alone, to "
        "satisfy any policy tier above CONFIRM. They carry no authorization "
        "weight in the policy engine.",
        "A cloned or replayed voice cannot escalate a MANUAL_ONLY action to "
        "proceed. The cost is that legitimate voice-only workflows are "
        "capped at CONFIRM-tier actions; anything more sensitive needs a "
        "different authorization channel.",
    ),
    (
        "Physical interaction with the machine is the real authorization boundary",
        "Given that voice cannot serve as an authorization boundary, the "
        'system needs some notion of "the user is actually here and '
        'actually intends this" for MANUAL_ONLY-tier actions.',
        "MANUAL_ONLY tier is satisfied only by physical interaction with "
        "the machine itself (e.g. an on-device confirmation, not a remote "
        "or voice channel) - this is the one authorization signal the "
        "design treats as trustworthy.",
        "Remote-only or voice-only deployments cannot fully exercise "
        "MANUAL_ONLY-tier capabilities, which is an intentional limitation "
        "rather than a gap to be closed later. Physical presence detection "
        "itself is out of scope for Milestone 0 and will need its own ADR "
        "when implemented.",
    ),
    (
        "SECRET data is DENY to any cloud provider, unconditionally",
        "API keys, passwords, and tokens are catastrophic if they leak, and "
        'any "except in this case" exception to a cloud-egress rule for '
        "SECRET data becomes the case an attacker (or a confused prompt) "
        "targets.",
        "Data classified SECRET is DENY for egress to any cloud reasoning "
        "provider, with no exception path, no override, and no code path "
        "that places it into a model's context window.",
        'Some workflows (e.g. "help me debug this API call") must be '
        "restructured so the secret itself never enters the payload sent "
        "to a reasoning provider, even redacted. This is treated as an "
        "acceptable UX cost given what SECRET data represents.",
    ),
    (
        "SENSITIVE data requires explicit CONFIRM before reaching a cloud provider",
        "Personal information and third-party confidential data are not as "
        "catastrophic as secrets if leaked, but still carry real cost, and "
        "silently routing them to a cloud API on the agent's own initiative "
        "removes the user's ability to make that call.",
        "Data classified SENSITIVE may be sent to a cloud reasoning "
        "provider, but only behind an explicit CONFIRM-tier user "
        "acknowledgment at the point of egress; it is never sent by "
        "default.",
        "Every code path that could route SENSITIVE data off-device must be "
        "instrumented to trigger a CONFIRM rather than silently proceeding "
        "- this is a real integration burden on every adapter, not just a "
        "documentation note.",
    ),
    (
        "Uncertain classification fails closed to the highest present",
        "When a task mixes inputs of different classifications, or an "
        "adapter can't determine an input's classification with "
        "confidence, defaulting to the lowest (most permissive) "
        "classification is a silent privacy leak waiting to happen.",
        "Whenever a task's overall classification is uncertain or its "
        "inputs are mixed, the task inherits the highest classification "
        "present among them - never a lower, more permissive default.",
        "The system is conservative by construction: some PUBLIC-only "
        "tasks that happen to touch one misclassified or ambiguous input "
        "will be treated more restrictively than strictly necessary. This "
        "is accepted; the alternative failure mode (leaking SECRET/"
        "SENSITIVE data because of an optimistic default) is categorically "
        "worse.",
    ),
    (
        "Secrets live only in the system keyring, referenced never stored",
        "Secrets that end up as plain values anywhere in the system "
        "(source, config, database rows, log lines) create a second place "
        "that needs to be secured as tightly as the keyring itself, and "
        "history shows secondary copies are the ones that leak.",
        "Secrets are stored only in the system keyring. Everywhere else in "
        "the system - domain objects, the database, the audit log, source "
        "code - a secret is represented by a reference/handle, never by "
        "its value.",
        "Any code that needs a secret's actual value must go through the "
        "keyring adapter at the point of use, which is a deliberate extra "
        "hop. In exchange, a full dump of the database or audit log never "
        "yields a usable secret.",
    ),
    (
        "Audio is never persisted to disk",
        "Recorded audio of a user's voice is uniquely sensitive (it's both "
        "PII and a biometric), and any code path that writes it to disk "
        '"just for debugging" tends to leave debug artifacts lying around '
        "in production.",
        "Audio data is never written to disk under normal operation. The "
        "only exception is an explicit, temporary, clearly-labeled debug "
        "mode that must be deliberately enabled - it is never the default "
        "and never silently persists across a session.",
        "Debugging audio-related issues without the debug mode enabled "
        "means debugging blind on that dimension, by design. Anyone "
        "enabling the debug mode is explicitly opting into a temporary "
        "reduction in the audio privacy guarantee, and it should be "
        "logged.",
    ),
    (
        "Destructive/irreversible/credential actions always require MANUAL_ONLY",
        "Even a well-calibrated policy engine could, through some "
        "combination of misconfiguration or clever framing, resolve a "
        "genuinely destructive action to CONFIRM instead of the stricter "
        "tier it deserves.",
        "Any capability whose declared effects include DESTRUCTIVE, "
        "IRREVERSIBLE, or CREDENTIAL is hard-pinned to MANUAL_ONLY tier - "
        "this floor is not something tier-resolution logic can compute its "
        "way around, and it is never satisfiable by voice alone (per the "
        "voice-is-not-authorization ADR).",
        "There is one more layer of protection against a policy-engine bug "
        "turning a destructive action loose unattended. The cost is that "
        "these actions are always maximally inconvenient by design - there "
        'is no "trusted enough" path around this floor.',
    ),
    (
        "Multi-provider reasoning behind a ReasoningPort abstraction",
        "Depending on a single reasoning provider is both a single point "
        "of failure and a way of silently coupling the entire codebase's "
        "business logic to one vendor's API shape.",
        "All reasoning providers (ChatGPT, Claude, and others) are "
        "accessed exclusively through a single ReasoningPort Protocol; the "
        "application layer calls the port, never a provider SDK directly.",
        "Adding or swapping a provider is an adapter-level change, not a "
        "domain or application change. The cost is that the "
        "ReasoningPort's interface must stay a lowest-common-denominator "
        "abstraction general enough for every provider behind it.",
    ),
    (
        "No vendor names in domain, application, or ports",
        'Vendor-specific naming ("the ChatGPT handler," "an '
        'Anthropic-specific retry") leaks implementation detail into '
        "layers that are supposed to be implementation-agnostic, and makes "
        "it obvious, on sight, when someone has bypassed the port "
        "abstraction.",
        'The strings "openai", "anthropic", "chatgpt", "claude", '
        'and "gpt" (and future vendor names) may never appear in '
        "src/jarvis/domain, application, or ports. This is enforced by "
        "static grep as well as review.",
        "A reviewer or a simple grep can catch an abstraction leak "
        "immediately. The cost is occasional awkward generic naming "
        '("provider A" style comments) when discussing provider-specific '
        "quirks that do belong in a code comment at the adapter layer.",
    ),
    (
        "Escalation ladder: deterministic fixes, then self-repair, before a second provider",
        "Consulting a second, more expensive reasoning provider every time "
        "something fails is slow and costly, and often unnecessary when "
        "the failure is something a deterministic tool (a linter, a "
        "formatter, a type checker) could have fixed directly.",
        "When a candidate fails validation, the system first attempts "
        "cheap deterministic fixes (auto-formatting, straightforward lint "
        "auto-fixes), then attempts self-repair with the same provider "
        "that produced the candidate, and only escalates to a second "
        "provider if both of those fail.",
        "Most transient failures are resolved without ever invoking a "
        "second, more expensive provider call. The cost is a small amount "
        "of added latency for genuinely hard failures, which must climb "
        "the full ladder before getting a second opinion.",
    ),
    (
        "Select, never merge: the arbiter picks one candidate unmodified",
        "Splicing together pieces of two different candidate "
        "implementations (e.g. one model's function body with another's "
        "error handling) produces code that neither model actually "
        "reasoned about as a whole, and combines two sets of untested "
        "assumptions into something new and untested.",
        "When multiple reasoning providers produce candidate "
        "implementations, the arbiter selects exactly one candidate to "
        "use, completely unmodified. It never merges, splices, or "
        "otherwise combines pieces of multiple candidates.",
        "Whatever ships has been reasoned about, in full, by at least one "
        "model and validated as a whole. The cost is that a good idea in a "
        "rejected candidate is simply lost for that round, rather than "
        "cherry-picked in.",
    ),
    (
        "A reviewing model must produce a failing test, not a verdict",
        'Asking a second model "does this look right?" produces an '
        "opinion that is easy to rubber-stamp, hard to verify, and doesn't "
        "compose with the project's actual test suite.",
        "When a reasoning provider is used to review another provider's "
        "candidate, its output must be a concrete, executable failing test "
        "case demonstrating the problem - never a prose verdict, score, or "
        "opinion with no way to confirm it's grounded in the actual code.",
        "A review either produces a real, addable regression test or it "
        "produces nothing actionable - there's no middle ground where an "
        'unfounded "this looks wrong" opinion blocks a candidate. The '
        "cost is that subtle stylistic or design concerns that don't "
        "manifest as a failing test go unflagged by this mechanism.",
    ),
    (
        "A provider's own tests carry zero weight scoring its own candidate",
        "A model grading its own candidate against tests it also wrote can "
        "trivially write tests that its candidate happens to pass, which "
        "would make the validation step circular and worthless as a "
        "check.",
        "When scoring a candidate, any test authored by the same provider "
        "that produced that candidate carries zero weight in that "
        "candidate's score - only tests from the existing suite, from a "
        "different provider, or from the human author actually count.",
        "A provider cannot game its own evaluation by writing lenient "
        "self-tests. The cost is that a genuinely good test written by a "
        "provider about its own candidate needs to be independently "
        "proposed (e.g. adopted into the permanent suite by a human) "
        "before it counts for anything.",
    ),
    (
        "Hash-chained, tamper-evident audit log",
        "An audit log that can be edited after the fact without detection "
        "is not useful evidence in an incident review - anyone with write "
        "access to the log (including a compromised process) could "
        "rewrite history.",
        "Every capability invocation is recorded in an audit log where "
        "each entry includes a hash of the previous entry, forming a "
        "tamper-evident chain - any edit or deletion of a past entry is "
        "detectable by hash mismatch.",
        "Incident review can trust the audit log's integrity without a "
        "separate, harder-to-maintain signing infrastructure. The cost is "
        "that legitimate log rotation/archival must preserve the chain (or "
        "explicitly start a new one), not silently truncate it.",
    ),
    (
        "Audit log never stores argument values, only digests",
        "An audit log that stores full argument values becomes, by "
        "construction, a second copy of every secret and every piece of "
        "sensitive data that ever flowed through the system - defeating "
        "the keyring and classification controls elsewhere.",
        "The audit log records only digests (hashes) of capability "
        "invocation arguments, never the argument values themselves.",
        "A full compromise of the audit log does not leak the sensitive "
        "data it references. The cost is that the audit log alone cannot "
        'reconstruct "what exactly was the value" for a forensic replay '
        "- that requires cross-referencing with whatever system produced "
        "the value, if it still exists.",
    ),
    (
        "Audit log header/payload split for redactable payloads",
        "If audit entries are single opaque blobs, redacting anything "
        "after the fact (e.g. in response to a data deletion request) "
        "breaks the hash chain and destroys tamper-evidence for every "
        "entry after it.",
        "Audit entries are split into a header (included in the hash "
        "chain, never redacted) and a payload (referenced by the header, "
        "redactable independently without breaking the chain).",
        "A payload can later be redacted (e.g. for a right-to-erasure "
        "request) while the chain of headers remains intact and "
        "verifiable. The cost is a more complex two-part storage format "
        "than a single flat log entry.",
    ),
    (
        "domain/ is stdlib-only, with no I/O and no async",
        "If the domain model can perform I/O or await anything, its "
        "behavior becomes dependent on the environment it runs in, and "
        "testing it requires mocking that environment rather than just "
        "calling pure functions.",
        "Everything under src/jarvis/domain imports the standard library "
        "only, performs no I/O, and defines no async functions. "
        "import-linter's C2 contract and an AST-based meta-test both "
        "enforce this at CI time.",
        "The domain model can be tested with plain synchronous unit tests "
        "and no fixtures beyond input data. The cost is that anything "
        "domain code needs from the outside world (the time, a fresh id, "
        "a file's contents) must be passed in by the caller rather than "
        "fetched directly.",
    ),
    (
        "No direct wall-clock or randomness access in src/: inject ClockPort/IdPort",
        "Code that calls datetime.now(), time.time(), or uuid.uuid4() "
        "directly is non-deterministic and untestable without "
        "monkeypatching, and a hash-chained audit log with untraceable "
        "timestamps loses much of its forensic value.",
        "No file under src/ calls datetime.now()/utcnow(), "
        "time.time()/monotonic(), or uuid.uuid1()/uuid4() directly. "
        "Anything needing the current time or a fresh identifier takes a "
        "ClockPort or IdPort dependency instead. This is enforced twice: a "
        "ruff banned-api rule for direct imports, and an AST-based "
        "meta-test that also catches bare `import time; time.time()`-style "
        "attribute calls ruff's rule can't see.",
        "Tests can inject a fixed clock/id source and get fully "
        "deterministic, reproducible output - including reproducible "
        "audit log entries. The cost is an extra constructor parameter (or "
        "two) threaded through anything that currently reaches for the "
        "wall clock casually.",
    ),
    (
        "uv workspace with plugins/* as independent workspace members",
        "Plugins are meant to be independently developed, versioned, and "
        "reviewed capability packages, not just modules living inside the "
        "main jarvis package - but without a real packaging boundary, "
        "that independence is just a convention.",
        "The project is a uv workspace with plugins/* configured as "
        "workspace members from Milestone 0 onward, even though no plugins "
        "exist yet, so that the packaging boundary is established before "
        "the first plugin needs to fit into it.",
        "A future plugin can be added as a genuinely separate package with "
        "its own pyproject.toml and dependencies, resolved consistently "
        "with the rest of the workspace by uv. The cost is an empty "
        "workspace glob sitting in pyproject.toml for as long as no "
        "plugins exist, which is intentional scaffolding rather than dead "
        "configuration.",
    ),
    (
        "Coverage is gated per-package, not globally",
        "A single global coverage threshold lets a well-tested, low-risk "
        "module (e.g. a CLI argument parser) mathematically compensate for "
        "an under-tested, high-risk module (e.g. the policy engine) - the "
        "aggregate number can look fine while the part that matters most "
        "is barely covered.",
        "Coverage gates are configured per-package in CI - starting with "
        "src/jarvis/domain and src/jarvis/application/policy - rather than "
        "as one repository-wide threshold, so each security-relevant "
        "package must earn its own coverage number.",
        "The policy engine's test coverage can never hide behind a "
        "well-tested but low-stakes package elsewhere in the tree. The "
        "cost is more CI configuration (one coverage report invocation per "
        "gated package) than a single global --fail-under line.",
    ),
]


def build_decisions() -> list[Adr]:
    """Assign sequential ADR numbers to RAW_DECISIONS, in order."""
    return [
        Adr(
            number=number,
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
        )
        for number, (title, context, decision, consequences) in enumerate(RAW_DECISIONS, start=1)
    ]


def main() -> None:
    """Regenerate every ADR file under docs/adr/."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    write_all(build_decisions(), ADR_DIR)


if __name__ == "__main__":
    main()
