#!/usr/bin/env bash
# TensorTile tool provisioner.
#
# Detect -> install what we can -> report the rest (for CI / DECISIONS.md).
# Idempotent and non-interactive: safe to run every session (containers are
# ephemeral, so tools must be re-provisioned on each fresh clone).
#
# Tiers:
#   REQUIRED  (pip): numpy cocotb cocotb-bus pytest   -> model + DV smoke
#   LOCAL     (apt): iverilog verilator                -> RTL compile/lint/sim
#   CI-ONLY   (heavy / release-binary): yosys sby verible openroad ...
#             provisioned in later phases / CI; never silently skipped.
#
# Usage: scripts/setup_tools.sh [--quiet]
set -uo pipefail

QUIET="${1:-}"
log() { [ "$QUIET" = "--quiet" ] || echo "$@"; }
have() { command -v "$1" >/dev/null 2>&1; }

PIP_OK=1
APT_OK=1

log "=== TensorTile tool provisioner ==="

# ---------------------------------------------------------------------------
# Tier 1: Python deps (REQUIRED) — pip is reliable here.
# ---------------------------------------------------------------------------
if have python3; then
  log "[pip] installing Python requirements ..."
  if [ -f "${CLAUDE_PROJECT_DIR:-.}/requirements.txt" ]; then
    REQ="${CLAUDE_PROJECT_DIR:-.}/requirements.txt"
  elif [ -f requirements.txt ]; then
    REQ="requirements.txt"
  else
    REQ=""
  fi
  if [ -n "$REQ" ]; then
    python3 -m pip install --quiet --disable-pip-version-check -r "$REQ" || PIP_OK=0
  else
    python3 -m pip install --quiet --disable-pip-version-check \
      numpy cocotb cocotb-bus pytest || PIP_OK=0
  fi
else
  echo "[pip] python3 missing — cannot install required deps" >&2
  PIP_OK=0
fi

# ---------------------------------------------------------------------------
# Tier 2: lightweight EDA via apt (LOCAL, best-effort).
# ---------------------------------------------------------------------------
need_apt=0
for t in iverilog verilator; do have "$t" || need_apt=1; done
SUDO=""
if [ "$(id -u)" -ne 0 ] && have sudo; then SUDO="sudo"; fi
if [ "$need_apt" = 1 ] && have apt-get; then
  log "[apt] installing iverilog + verilator (best-effort) ..."
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -qq >/dev/null 2>&1 || true
  $SUDO apt-get install -y -qq iverilog verilator >/dev/null 2>&1 || APT_OK=0
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
log ""
log "=== tool matrix ==="
report() {
  printf "  %-12s %s\n" "$1:" "$(have "$1" && echo "OK ($(command -v "$1"))" || echo "MISSING -> CI/later")"
}
for t in python3 iverilog verilator yosys sby verible-verilog-lint openroad; do report "$t"; done
log ""
python3 - <<'PY' 2>/dev/null || true
mods = []
for m in ("numpy", "cocotb", "pytest"):
    try:
        mod = __import__(m); mods.append(f"{m} {getattr(mod,'__version__','?')}")
    except Exception:
        mods.append(f"{m} MISSING")
print("  python pkgs:", ", ".join(mods))
PY

# Required tier must succeed; EDA-tier shortfalls fall through to CI.
if [ "$PIP_OK" != 1 ]; then
  echo "ERROR: required Python deps failed to install." >&2
  exit 1
fi
log "=== provisioning done (pip=$PIP_OK apt=$APT_OK) ==="
exit 0
