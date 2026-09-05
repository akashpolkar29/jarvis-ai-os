#!/usr/bin/env bash
# Regenerates docs/architecture/sbom.cyclonedx.json from the real, currently-
# resolved .venv (10-phase combined pass, Phase 9). Not run automatically by
# CI or any gate -- a real, on-demand snapshot, matching this project's own
# "poc/wp61_vector_store_benchmark.py"/kernel-benchmark precedent of durable,
# reusable, manually-invoked tooling rather than a repeated CI artifact.
set -euo pipefail

cd "$(dirname "$0")/.."

uv run --with cyclonedx-bom cyclonedx-py environment .venv/bin/python3 \
    --pyproject pyproject.toml \
    --of JSON \
    --output-reproducible \
    -o docs/architecture/sbom.cyclonedx.json

echo "Wrote docs/architecture/sbom.cyclonedx.json"
