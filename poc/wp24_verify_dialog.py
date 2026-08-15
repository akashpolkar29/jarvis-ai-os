"""WP-24 manual verification: the real GTK4 physical confirmation dialog.

Unlike WP-19's poc/ scripts, this does not stand outside the
architecture -- jarvis.ui.confirm.dialog.show_confirmation_dialog is
the real WP-24 implementation, called here directly, not reimplemented.
This script exists only because that function is deliberately outside
the automated test suite (it needs a real display and a real human at
the keyboard -- see that module's docstring), so its correctness has
to be proven by someone actually watching it happen.

Runs three scenarios, each shown as its own dialog with instructions
in the prompt text itself:

  1. Approve: click "Approve" -> expects True.
  2. Deny: click "Deny" -> expects False.
  3. Timeout: do nothing for 5 seconds -> expects False.

Reports PASS/FAIL per scenario and an overall summary at the end.

Run with: uv run poc/wp24_verify_dialog.py
(from the project root, using the project's own environment -- this
needs the real jarvis package and the real pygobject/GTK4 install, not
a standalone PEP 723 script environment.)
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and a bare
# main() are the point, not library hygiene.
from __future__ import annotations

from jarvis.ui.confirm.dialog import show_confirmation_dialog

TIMEOUT_SCENARIO_TIMEOUT_S = 5.0
INTERACTIVE_TIMEOUT_S = 30.0


def _run_scenario(name: str, prompt: str, timeout_s: float, expected: bool) -> bool:
    print(f"\n--- {name} ---")
    print(f"Prompt shown in dialog: {prompt!r}")
    print(f"Expecting: {expected}")
    result = show_confirmation_dialog(prompt, timeout_s)
    passed = result == expected
    verdict = "PASS" if passed else "FAIL"
    print(f"Dialog returned: {result} -> {verdict} (expected {expected})")
    return passed


def main() -> None:
    print("WP-24 manual verification: real GTK4 physical confirmation dialog.")
    print("Three dialogs will appear, one at a time. Follow each dialog's own instructions.\n")

    results = {
        "1. Approve (click Approve)": _run_scenario(
            "Scenario 1: Approve",
            "TEST 1 of 3 -- please click Approve now.",
            INTERACTIVE_TIMEOUT_S,
            expected=True,
        ),
        "2. Deny (click Deny)": _run_scenario(
            "Scenario 2: Deny",
            "TEST 2 of 3 -- please click Deny now.",
            INTERACTIVE_TIMEOUT_S,
            expected=False,
        ),
        f"3. Timeout (do nothing for {TIMEOUT_SCENARIO_TIMEOUT_S:.0f}s)": _run_scenario(
            "Scenario 3: Timeout",
            f"TEST 3 of 3 -- do nothing. This dialog auto-denies in "
            f"{TIMEOUT_SCENARIO_TIMEOUT_S:.0f}s.",
            TIMEOUT_SCENARIO_TIMEOUT_S,
            expected=False,
        ),
    }

    print("\n=== Summary ===")
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'} -- {name}")

    if all(results.values()):
        print("\nAll scenarios passed.")
    else:
        print("\nAt least one scenario failed -- see above.")


if __name__ == "__main__":
    main()
