# M5 ADR review summary

**This is a reading aid, not a new design document.** One paragraph per
ADR (0055–0056), in plain language, for a final read-through before
deciding whether to accept anything. Everything below is pulled from
each ADR's own text — no new judgment, no new decisions, nothing added
that the ADR itself doesn't already say. Read the real ADRs before
accepting any of them; this is a map, not a replacement.

**Updated 2026-09-01**: both are now **Accepted** — by the user's own
direct instruction in conversation, given only after WP-70, WP-73, and
WP-71 were actually built and each one's own required real tests
proven passing (see each ADR's own "Accepted 2026-09-01" note for
specifics). Unlike M4's ADRs, accepted on design review alone before
any code existed, these two were accepted after the code did — the
user's own explicit, stated condition for accepting them at all.

**Read this before the two ADRs below, not instead of it**: unlike
every prior milestone's own ADRs, these two were drafted from working
assumptions that were reasoned remotely — by the user's own AI
assistant, away from the machine — rather than confirmed by the user
directly in conversation. `m5-browser-coding.md`'s own header explains
this in full. That makes this specific review pass more necessary than
usual, not a formality to skim past.

---

## ADR-0055 — The coding loop wraps M2's dispatcher instead of changing it

**What it decides**: rather than teaching the existing escalation
system (the part of this project that already tries cheap fixes first,
then a repair attempt, then a second opinion, before giving up) any new
tricks, this adds a separate, smaller piece of new code on top of it.
That new piece is the thing that actually says "apply this patch, run
the tests, and if they fail, try the escalation system again" — the
escalation system itself doesn't change at all, and doesn't know
anything new is wrapping it. The reasoning: the existing system is
already locked down and heavily tested, with a deliberately fixed,
three-step ceiling on how many times it will try — changing that ceiling
to fit a coding task's needs would be a real, structural change
affecting every single thing that already relies on it, not a small
tweak just for this new use case.

**Its own stated limits**: it doesn't decide exactly how many times the
new wrapper is allowed to retry before giving up, or what happens when
it runs out of retries with nothing working — real, separate design
work left for whoever actually builds this. It also doesn't answer a
deeper question this same milestone's own research already raised: is
"one attempt = one patch, retried a few times" actually enough for a
real coding agent, or does it eventually need something that can read
and edit a file several times *within* a single attempt, which would be
a bigger, different change this ADR does not make and does not rule
out making later.

**Amended 2026-09-01, a real mistake found and corrected**: this ADR
originally said the new wrapper itself would be the thing writing each
file change, checking permission first every time. Checking the actual
existing code line by line turned up that this isn't true — the *old*
system this wrapper sits on top of already writes a candidate's change
to disk itself, internally, for every single attempt it makes, before
the new wrapper ever gets a look at the result. There was never going
to be a moment for the new wrapper to check permission first, because
by the time it can see anything, the old system has already written
several attempts' worth of changes, unchecked. The real fix: never let
that old system write to the real project at all. Give it a disposable
throwaway copy of the project instead, using the same real, contained
sandbox mechanism already built for this project's earlier desktop-app
work. The new wrapper only writes to the real project itself, once,
after checking permission, once it already knows which one attempt
actually worked. One real, practical consequence: the throwaway-copy
piece (originally planned as a nice-to-have polish step, done last)
now has to be built first — the wrapper can't safely exist without it.

---

## ADR-0056 — A new kind of file-write permission, and an absolute no for test files

**What it decides**: two new things. First, an ordinary permission
level for a coding agent writing to a regular file — same everyday
"ask first" gate any other local file write already gets. Second, and
separately, an absolute, no-exceptions block on writing to anything
that looks like a test file (by default: files starting with `test_`,
files ending in `_test.py`, or anything inside a `tests` folder — the
same real pattern this project's own test files already follow, checked
directly rather than guessed). "No exceptions" means exactly that — not
even if a person is standing right there approving it, the same
absolute-no this project already uses for a couple of other especially
risky things.

A real technical wrinkle came up while writing this down, worth
knowing about: the original instruction asked for one single permission
level that somehow means both "ask first" *and* "absolute no" depending
on which file is being written — but this project's permission system
doesn't actually support one thing meaning two different strictness
levels at once. The fix applied here, matching how this exact problem
was already solved once before for a different feature: use *two*
separate permission levels instead of one, and add a small, automatic
check that looks at which file is about to be written and picks the
right one. The end result behaves exactly as originally asked — ordinary
files get the ordinary gate, test files get the absolute block — just
built the only way this project's own system can actually express that.

**Its own stated limits**: it only decides the rule for a single file at
a time — the real, practical question of "what if a patch changes ten
files and only one of them is a protected test file" is answered here
(reject the whole patch, don't apply it partially), but exactly how the
code figures out which files a given patch touches in the first place
is left as real, separate work. And, like every permission rule in this
project, it can only ever be as good as the information it's given —
nothing here can independently verify a file really is or isn't a test
file beyond checking its name against the configured pattern.

**Amended 2026-09-01, real gap closed, not just noted this time**: the
original version of this ADR only *named* "what if a project uses a
different test-naming convention" as an undesigned gap — worse than
that on a second look: the default patterns are Python-specific, and
most real target projects won't be Python at all, meaning the "test
files get the absolute block" promise above would have silently done
nothing for a Go, JavaScript, or Ruby project, with no one aware. The
real fix, built now: before writing to any project, this checks for a
handful of real, well-known signals of what testing convention that
project actually uses (a pytest config file, a Go module file, an
RSpec config file, a `package.json` naming a known JS test tool) and
uses the matching real patterns automatically. If none of those real
signals are found, it now refuses to authorize any write at all until
a person explicitly says what the patterns should be — never silently
falls back to the Python defaults on a project they don't fit. A
second, separate real gap closed the same day: whatever eventually
figures out which files a patch touches must resolve real file paths
first (so a sneaky `../`-style path or a symlink can't dodge the check)
and must treat a patch *creating* a new protected-looking file exactly
the same as one editing an existing one — creating a new "test" file
was never meant to be a loophole.

---

## Reading order, if it helps

0055 (the coding loop's own shape) → 0056 (the new permission levels
that loop's file writes need). 0056 does not depend on 0055's own
retry-budget details, only on the fact that *some* real orchestration
calls `WorkspacePort.apply_patch` for a coding-agent-authored patch —
0055 is where that orchestration's own real shape is decided.

**One more time, not smoothed over**: both of these were drafted from
remotely-reasoned working assumptions, not from a conversation with the
user. Read the real ADRs, and `m5-browser-coding.md`'s own header, before
accepting either one.
