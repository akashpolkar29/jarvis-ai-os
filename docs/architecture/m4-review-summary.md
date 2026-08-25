# M4 ADR review summary

**This is a reading aid, not a new design document.** One paragraph
per ADR (0048–0053), in plain language, for a final read-through
before deciding whether to accept anything. Everything below is
pulled from each ADR's own text — no new judgment, no new decisions,
nothing added that the ADR itself doesn't already say. Read the real
ADRs before accepting any of them; this is a map, not a replacement.

All six are currently **Proposed**. None are Accepted. No code exists
for any of them.

---

## ADR-0048 — MemoryWritePort and RetrievalPort (the port shapes)

**What it decides**: two new, separate ports — one for writing to
memory, one for reading from it — rather than a single combined port.
Writing and reading get kept apart because they have different
authorization stories (later ADRs). `RetrievalPort` returns records
with their real, original classification still attached; it doesn't
filter anything itself — that's left to whoever consumes what it
returns (ADR-0050).

**Its own stated limits**: it doesn't decide what the real vector
store underneath these ports actually is (left to a benchmark, later
work). It explicitly leaves open whether the bare act of *querying*
memory should require more than the lowest authorization tier — the
document doesn't rule that out, it just doesn't decide it here.

---

## ADR-0049 — SECRET values are a hard DENY to memory write

**What it decides**: a value marked SECRET (API keys, passwords,
tokens — the same category that's already an absolute no-go for
cloud providers) can never be written to memory, full stop — not even
with the user standing there approving it. This is done by adding a
new, dedicated flag on the write action itself (not by reusing the
existing "don't send this to the cloud" flag, since a local memory
write isn't the same thing as a cloud upload, and reusing that flag
would be a misleading label). The ADR also requires a second,
mechanical safeguard: an automated check that no other code anywhere
in the project can quietly write to the memory store by a different
path that skips this rule.

**Its own stated limits**: it only governs the moment something is
written — it says nothing about a value that was written correctly at
the time but might deserve stricter treatment later. It also says
plainly that this whole guarantee depends on the classification it's
given being correct in the first place — it can't independently verify
that a value it's told is safe genuinely is.

---

## ADR-0050 — Retrieval re-checks a recalled value's own sensitivity

**What it decides**: if something sensitive was memorized, recalling
it later doesn't give it a free pass — using a recalled value has to
clear the same approval bar a live version of that same value would
need. This isn't enforced by new code in the core authorization
system; it's enforced by requiring that a recalled value's real
sensitivity always travels with it into whatever uses it next, plus a
real, automated check that nothing quietly strips that information
off. Separately, this ADR also says a SECRET-marked record should
never come back from a memory search at all — if one somehow does
(meaning ADR-0049's own protection failed somewhere), that's treated
as a real, detectable problem worth raising loudly, not something
quietly filtered out and forgotten.

**Its own stated limits**: it can require and test that *this
milestone's own* code carries sensitivity information forward
correctly, but it can't guarantee every future piece of code that ever
reads from memory will keep doing so — that's a trust placed in future
work, named openly rather than assumed away. It also doesn't say what
should actually happen operationally if that "real, detectable
problem" alarm ever goes off (a warning to the user? just a log
entry?) — left for whoever builds this.

---

## ADR-0051 — Memories expire after 90 days by default, unless pinned

**What it decides**: nothing is kept forever by default. Every
memorized item automatically expires 90 days after it's written,
unless someone explicitly marks it to be kept longer ("pinned"), in
which case it's kept indefinitely until unpinned. This is a deliberate
middle ground — not keeping everything forever (a real privacy
concern in itself), and not silently forgetting things based on how
recently they were used (which the ADR argues would just be confusing
and erode trust in what the assistant remembers). The 90-day count
starts from when the memory was written, computed the same
project-standard way every other timestamp in this codebase already
is (never a bare "current time" call). This is the first time this
project has ever needed to genuinely delete something on a schedule.

**Its own stated limits**: whether 90 days is actually the right
number in practice is explicitly left open — it's a starting point,
not a researched, final answer. It also doesn't build any way for the
user to explicitly say "forget this specific thing" outside of the
normal expiry schedule — that's named as a real, separate, plausible
future addition, not something this ADR builds.

---

## ADR-0052 — No real-time on-screen/audible signal when memory is recalled

**What it decides**: recalling something from memory doesn't get a
dedicated, dramatic "notice me" signal the way a couple of this
project's other actions do. The reasoning: that kind of signal exists
elsewhere specifically to give a person a chance to stop something
before it becomes permanent and unfixable. A memory recall isn't like
that — if it recalls something wrong, the user hears it in the
conversation and can correct it right there, the same way you'd
correct a friend who misremembered something. This ADR is explicit
that this is a deliberate line being drawn, not a shortcut — legibility
doesn't have to mean "a special alert for every single thing."

**Its own stated limits**: this ADR only covers *recalling* a memory,
not *creating* one — it explicitly says a memory write feels more
consequential and might deserve different treatment, and just as
explicitly declines to answer that here, leaving it for a separate
decision. (That separate decision is ADR-0053, drafted afterward.) It
also doesn't treat its own answer as permanent — if it turns out in
practice that people are genuinely confused by silent recall, this is
explicitly left open to revisiting.

---

## ADR-0053 — No dedicated signal when memory is written, either — but for a different reason

**What it decides**: writing a new memory also doesn't get a
dedicated real-time signal — but this is reasoned separately from
ADR-0052's recall answer, not copied from it, because writing and
recalling aren't actually the same kind of action. The real reasoning
here: unlike the one existing action in this project that does get a
dedicated signal (which is irreversible the instant it happens), a
memory write is undoable — it expires on its own or can be manually
un-kept (ADR-0051). And separately, this project already has an
ordinary way of telling the user what just happened after an action —
memory write can be added to that existing pattern the same small way
every other action already was, rather than needing a whole new
mechanism built for it.

**Its own stated limits**: this reasoning only holds for a memory
write that goes through the normal, existing flow — if some future
version of this feature ever let something write to memory through a
completely different path, this ADR says plainly that its own logic
wouldn't automatically carry over to that case. Like ADR-0052, it
doesn't treat itself as permanent either — open to revisiting if real
use shows people need more than what's here.

---

## Reading order, if it helps

0048 (the two ports) → 0049 (SECRET write-time DENY) → 0050 (retrieval
re-checks sensitivity, plus what happens if a SECRET record shows up
anyway) → 0051 (retention/expiry) → 0052 (no signal on recall) → 0053
(no signal on write, separately reasoned). Each later ADR assumes the
ones before it; none of them assume anything from `m4-scoping-notes.md`
that isn't also restated in the ADR itself.
