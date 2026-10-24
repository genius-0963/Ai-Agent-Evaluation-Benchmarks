#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo " Running AI Agent Evaluation Benchmark Smoke Test "
echo "=================================================="

# Ensure script is executable from project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

VENV_BIN=".venv/bin"
if [[ -f "${VENV_BIN}/agentbench" ]]; then
    AGENTBENCH="${VENV_BIN}/agentbench"
    PYTHON="${VENV_BIN}/python"
    PYTEST="${VENV_BIN}/pytest"
else
    AGENTBENCH="agentbench"
    PYTHON="python3"
    PYTEST="pytest"
fi

echo "1. Validating benchmark definitions..."
${AGENTBENCH} validate config-recovery-001
${AGENTBENCH} validate contract-repair-001
${AGENTBENCH} validate multi-service-cache-001

echo "2. Running unit tests..."
${PYTEST} tests/unit -q

echo "3. Testing Docker initialization smoke test..."
${AGENTBENCH} smoke-test config-recovery-001

echo "4. Executing scripted agent benchmark run..."
${AGENTBENCH} run config-recovery-001 --agent scripted
${AGENTBENCH} run multi-service-cache-001 --agent scripted

echo "5. Executing no-op agent benchmark run (expected failure)..."
set +e
${AGENTBENCH} run config-recovery-001 --agent noop
NOOP_EXIT=$?
set -e

if [[ ${NOOP_EXIT} -ne 1 ]]; then
    echo "ERROR: Expected no-op agent run to exit with code 1, got ${NOOP_EXIT}"
    exit 1
fi
echo "Verified: No-op agent failed grading as expected."

echo "6. Executing statistical trials (eval)..."
${AGENTBENCH} eval multi-service-cache-001 --agent scripted --trials 2

echo "7. Generating public leaderboards..."
${AGENTBENCH} leaderboard

echo "8. Executing benchmark matrix evaluation..."
${AGENTBENCH} matrix --tasks all --agents scripted,noop

echo "=================================================="
echo " Smoke test completed successfully! "
echo "=================================================="
