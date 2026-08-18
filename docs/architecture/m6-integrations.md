# JARVIS — M6+: Integrations

Placeholder — objective and gates only, per this project's rolling-wave
planning. Full architecture-level design is written when this
milestone actually starts, not before (see docs/ROADMAP.md).

## Objective

Email, calendar, research, job assistance (research + drafting only,
no auto-apply), Docker, ROS2.

## Entry gate

M5.

## Exit gate

Per-plugin conformance to the M0 capability/policy/audit model.

## Complexity

Not specified in any surviving planning material.

## Known risks

Not specified in any surviving planning material.

## Not yet decided

No ports, adapters, package layout, work-package breakdown, or ADRs
exist for this milestone. Any of those referenced in earlier planning
conversations predate this repo's real ADR numbering and are not
carried forward here — TBD, decided when this milestone starts.

M6's eventual design must also satisfy the standing "always legible"
principle in `docs/ROADMAP.md`: every action M6's integrations take
should be legible to Akash in real time, spoken and shown. That means
reusing M1's TTS and M5's Console UI once they're available to build
against — not inventing new voice or display mechanisms specific to
M6. This is a constraint M6's future design must satisfy, not a
decision about what M6's specific ports, adapters, or UI will look
like — those remain genuinely undecided.
