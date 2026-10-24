# Getting Started with agentbench

## Prerequisites
- macOS or Linux
- Python 3.12 or newer
- Docker Desktop or Docker Engine running

## Step-by-Step Installation

```bash
# 1. Clone repository
git clone https://github.com/example/ai-agent-evaluation-benchmarks.git
cd ai-agent-evaluation-benchmarks

# 2. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode
pip install -e ".[dev]"

# 4. Verify installation
agentbench --version
pytest tests/unit -v
```

## Running Your First Benchmark

```bash
# Validate task configuration
agentbench validate config-recovery-001

# Run baseline test with scripted agent
agentbench run config-recovery-001 --agent scripted

# Run baseline test with no-op agent (demonstrating failure detection)
agentbench run config-recovery-001 --agent noop

# Inspect the generated run report
agentbench report <RUN_ID>
```
