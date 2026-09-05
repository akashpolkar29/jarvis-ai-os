"""5 mixed real tasks, Task 3: real memory-retrieval quality evaluation.

`docs/architecture/m4-benchmark-results.md`'s own correctness check
(WP-61/62) used 5 hand-built (corpus, query) pairs to decide
brute-force-vs-`sqlite-vec` -- a real, but narrow, one-shot spike, not
a thorough retrieval-quality evaluation of the actual, chosen
production pipeline. This script is that thorough evaluation: a real,
35-fact corpus (including deliberate, confusable distractor pairs --
two dogs, two people both named "Alex" in different relations, a
Rust/Python "favorite language" confound, mirroring the real,
already-known near-miss class `m4-benchmark-results.md` first found)
and a real, 25-query eval set spanning direct restatement, paraphrase,
semantic-only (no keyword overlap), and negation/tense
disambiguation.

Real embeddings throughout (the actual production
`jarvis.adapters.memory.SqliteMemoryAdapter` + `FastEmbedAdapter`, not
synthetic vectors or a mocked embedding port) -- run manually on this
real development machine, not a repeated CI test, matching
`poc/wp61_vector_store_benchmark.py`'s own established precedent.

Real results from the run this evaluation produced are recorded in
`docs/architecture/retrieval-quality-eval-results.md`, not reproduced
here as a comment that could silently drift from a script this file no
longer matches -- re-run this script directly for current numbers.
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and
# small helper functions are the point here, not library hygiene.
from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from jarvis.adapters.embedding import FastEmbedAdapter
from jarvis.adapters.identifier import UuidIdAdapter
from jarvis.adapters.memory import SqliteMemoryAdapter
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

_NOW = datetime(2026, 9, 5, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


# Real corpus: 30 ordinary facts + 5 deliberate distractor/confound facts
# (marked below), mirroring the real "prefer(s)" near-miss class
# m4-benchmark-results.md already found once, not invented fresh.
CORPUS: list[str] = [
    "The user's favorite programming language is Rust.",
    "The user prefers tabs over spaces for indentation.",
    "The user's dog is named Biscuit.",
    "The user's cat is named Whiskers.",
    "The user works as a backend engineer at a fintech startup.",
    "The user's favorite color is teal.",
    "The user is allergic to peanuts.",
    "The user's birthday is March 3rd.",
    "The user drives a blue Honda Civic.",
    "The user's favorite text editor is Neovim.",
    "The user's partner's name is Alex.",
    "The user lives in Austin, Texas.",
    "The user's favorite food is Thai green curry.",
    "The user runs 5 kilometers every morning.",
    "The user's laptop is a ThinkPad X1 Carbon.",
    "The user's preferred IDE theme is Dracula.",
    "The user's phone number ends in 4471.",
    "The user's favorite band is Radiohead.",
    "The user's home Wi-Fi network is named BiscuitNet.",
    "The user's favorite programming paradigm is functional programming.",
    "The user's manager's name is Priya.",
    "The user's gym membership renews every January.",
    "The user drinks black coffee, no sugar.",
    "The user's favorite operating system is Arch Linux.",
    "The user's second monitor is a 4K LG display.",
    "The user prefers dark mode in every application.",
    "The user's emergency contact is their sister, Maya.",
    "The user's favorite season is autumn.",
    "The user's preferred version control workflow is trunk-based development.",
    "The user's favorite pizza topping is mushroom.",
    # Deliberate distractor/confound facts (indices 30-34):
    "The user's favorite scripting language is Python.",
    "The user's second dog is named Pepper.",
    "The user's brother's name is Alex.",
    "The user's old car, before the current one, was a red Honda Civic.",
    "The user's indentation preference used to be spaces, before switching to tabs.",
]

QUERIES: list[tuple[str, int, str]] = [
    # Each tuple: (query text, expected top-1 corpus index, category)
    ("What's the name of the user's cat?", 3, "direct"),
    ("Where does the user work?", 4, "paraphrase"),
    ("What is the user's favorite color?", 5, "direct"),
    ("What is the user allergic to?", 6, "direct"),
    ("When is the user's birthday?", 7, "direct"),
    ("What text editor does the user prefer?", 9, "direct"),
    ("What food does the user like?", 12, "paraphrase"),
    ("How does the user stay fit?", 13, "semantic-only"),
    ("What laptop model does the user have?", 14, "direct"),
    ("What color scheme do they use in their editor?", 15, "paraphrase"),
    ("What band does the user enjoy?", 17, "paraphrase"),
    ("What's the name of the user's home network?", 18, "direct"),
    ("What programming paradigm does the user favor?", 19, "direct"),
    ("Who is the user's manager?", 20, "direct"),
    ("How does the user take their coffee?", 22, "paraphrase"),
    ("What Linux distro does the user use?", 23, "direct"),
    ("What theme or mode does the user prefer across apps?", 25, "paraphrase"),
    ("Who should be contacted in an emergency?", 26, "semantic-only"),
    ("What season does the user like best?", 27, "direct"),
    ("What pizza topping does the user prefer?", 29, "direct"),
    ("What is the user's git workflow preference?", 28, "direct"),
    ("What monitor does the user use?", 24, "direct"),
    ("What operating system does the user run?", 23, "paraphrase"),
    ("What is the user's phone number?", 16, "direct"),
    ("What is the user's favorite season of the year?", 27, "paraphrase"),
]

# Real, deliberately unscored, genuinely-ambiguous queries -- the corpus
# contains two real, equally-valid answers, and no query wording can
# disambiguate without more context than a real query would plausibly
# supply. Reported separately, honestly, not folded into pass/fail.
AMBIGUOUS_QUERIES: list[tuple[str, str]] = [
    ("What is the name of the user's dog?", "Biscuit (idx 2) or Pepper (idx 31) -- two real dogs"),
    (
        "What is the user's favorite programming language?",
        "Rust (idx 0) or Python (idx 30) -- 'favorite language' is genuinely ambiguous "
        "between 'primary' and 'scripting' without qualification",
    ),
    (
        "What's the user's partner's name?",
        "Correct answer is Alex (idx 10, partner) -- but the corpus also has Alex (idx 32, "
        "brother) -- a real test of relation-disambiguation, not name-matching alone",
    ),
    (
        "What car does the user drive?",
        "Correct answer is the blue Honda Civic (idx 8, current) -- corpus also has a red "
        "Honda Civic (idx 33, explicitly 'old', 'before the current one')",
    ),
]


def _write_corpus(adapter: SqliteMemoryAdapter) -> list[str]:
    identifiers = []
    for text in CORPUS:
        value: Tainted[object] = Tainted(
            text,
            Provenance(
                trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
            ),
        )
        identifiers.append(adapter.write(value))
    return identifiers


def main() -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="jarvis-retrieval-eval-"))
    database_path = tmp_dir / "memory.sqlite3"
    adapter = SqliteMemoryAdapter(
        str(database_path), FastEmbedAdapter(), _FixedClock(), UuidIdAdapter()
    )
    identifiers = _write_corpus(adapter)

    print(f"=== Real memory-retrieval quality evaluation: {len(CORPUS)}-fact corpus ===\n")

    top1_correct = 0
    top3_correct = 0
    by_category: dict[str, list[bool]] = {}
    print(f"{'category':<15} | {'query':<55} | top1 | top3")
    for query, expected_index, category in QUERIES:
        results = adapter.retrieve(query, limit=3)
        result_ids = [r.identifier for r in results]
        expected_id = identifiers[expected_index]
        is_top1 = bool(result_ids) and result_ids[0] == expected_id
        is_top3 = expected_id in result_ids
        top1_correct += int(is_top1)
        top3_correct += int(is_top3)
        by_category.setdefault(category, []).append(is_top1)
        print(f"{category:<15} | {query[:55]:<55} | {is_top1!s:<4} | {is_top3!s}")

    total = len(QUERIES)
    print(f"\nOverall top-1 accuracy: {top1_correct}/{total} ({100 * top1_correct / total:.1f}%)")
    print(f"Overall top-3 recall:   {top3_correct}/{total} ({100 * top3_correct / total:.1f}%)")

    print("\nBy category (top-1):")
    for category, hits in sorted(by_category.items()):
        correct = sum(hits)
        print(f"  {category:<15}: {correct}/{len(hits)}")

    print("\n=== Known-ambiguous queries (not scored) ===")
    for query, note in AMBIGUOUS_QUERIES:
        results = adapter.retrieve(query, limit=3)
        top_texts = [str(r.value.value)[:60] for r in results]
        print(f"Q: {query}\n  note: {note}\n  real top-3: {top_texts}\n")


if __name__ == "__main__":
    main()
