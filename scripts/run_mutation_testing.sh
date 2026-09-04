#!/bin/bash
# Real mutation-testing driver for the policy/authorization core (overnight
# Track 2, 2026-09-04). Runs cosmic-ray against domain/policy.py,
# domain/capability.py, and every application/*/classification.py module,
# reporting each module's real mutation score.
#
# Output files are keyed by each module's own dotted package path, not its
# bare basename -- four of the six target modules are all literally named
# classification.py, and an earlier basename-keyed version of this script
# silently overwrote three of the four sessions before their per-mutant
# diffs could be inspected (see docs/threat-model/v0.md's own Track 2 note).
#
# Each module is run to completion, one at a time, in isolation -- do not
# run any other pytest/coverage command against a module this script is
# currently executing against. cosmic-ray's own per-mutant apply/revert
# cycle is not safe under concurrent file access to the same module; a
# racing external read/write can leave a real mutation applied to the
# working tree even after the run reports done (see docs/threat-model/v0.md
# for the real, directly-caught instance of this).
set -uo pipefail
cd "$(dirname "$0")/.."

TEST_CMD="uv run pytest -o addopts='' --no-cov -x -q tests/property tests/unit/test_policy.py tests/unit/test_capability.py tests/unit/application tests/unit/test_communications_kernel.py tests/unit/test_files.py tests/unit/test_coding_kernel.py tests/unit/test_job_assistance_kernel.py tests/unit/test_memory.py"

MODULES=(
  "src/jarvis/domain/policy.py"
  "src/jarvis/domain/capability.py"
  "src/jarvis/application/communications/classification.py"
  "src/jarvis/application/memory/classification.py"
  "src/jarvis/application/coding/classification.py"
  "src/jarvis/application/job_assistance/classification.py"
)

OUT_DIR="${MUTATION_OUT_DIR:-/tmp/cr-mutation-run}"
mkdir -p "$OUT_DIR"

for module in "${MODULES[@]}"; do
  # dotted, collision-free key: src/jarvis/application/coding/classification.py
  # -> application.coding.classification
  key=$(echo "$module" | sed -e 's#^src/jarvis/##' -e 's#\.py$##' -e 's#/#.#g')
  toml="$OUT_DIR/$key.toml"
  sqlite="$OUT_DIR/$key.sqlite"
  rm -f "$sqlite"
  cat > "$toml" <<EOF
[cosmic-ray]
module-path = "$module"
timeout = 15.0
excluded-modules = []
test-command = "$TEST_CMD"

[cosmic-ray.distributor]
name = "local"
EOF
  echo "=== INIT $key ==="
  uv run cosmic-ray init "$toml" "$sqlite"
  echo "=== EXEC $key ==="
  uv run cosmic-ray exec "$toml" "$sqlite"
  echo "=== REPORT $key ==="
  uv run cr-report "$sqlite" | tail -5
  echo "=== DONE $key ==="
done

echo "ALL MODULES COMPLETE"
