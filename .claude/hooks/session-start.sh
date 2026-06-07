#!/usr/bin/env bash
# SessionStart hook -- re-provision tools each session.
#
# Containers are ephemeral: every session is a fresh clone with no EDA tools, so we reinstall
# them up front. Synchronous mode (no async wrapper): guarantees tools are ready before the agent
# runs tests/linters, at the cost of slightly slower startup. Web-only (guarded by
# $CLAUDE_CODE_REMOTE). Switch to async later if startup latency matters.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Persist PYTHONPATH so `import model...` and DV benches resolve from the repo root.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PYTHONPATH=\"$proj\"" >> "$CLAUDE_ENV_FILE"
fi

bash "$proj/scripts/setup_tools.sh" --quiet
echo "[session-start] TensorTile tools provisioned."
