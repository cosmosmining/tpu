#!/usr/bin/env bash
# PostToolUse hook -- lint + compile-check after any edit under rtl/.
#
# Reads the tool-call JSON on stdin, extracts the edited file, and if it is an RTL source under
# rtl/ runs `verilator --lint-only -Wall` with the core/top library dirs (which elaborates the
# hierarchy, i.e. acts as a compile check too). On a real lint error it exits 2 so the failure is
# fed straight back to Claude. Missing tools are skipped gracefully (SessionStart installs them).
set -uo pipefail

input="$(cat)"
fp="$(printf '%s' "$input" | python3 -c \
  'import sys,json;d=json.load(sys.stdin);print(d.get("tool_input",{}).get("file_path") or "")' \
  2>/dev/null)"

# Only act on RTL sources under rtl/.
case "$fp" in
  *rtl/*.v|*rtl/*.sv|*rtl/*.svh) ;;
  *) exit 0 ;;
esac
[ -f "$fp" ] || exit 0

proj="${CLAUDE_PROJECT_DIR:-.}"

if ! command -v verilator >/dev/null 2>&1; then
  echo "[post-rtl-edit] verilator not installed; skipping (will be checked in CI)."
  exit 0
fi

if out="$(verilator --lint-only -Wall \
            -y "$proj/rtl/core" -y "$proj/rtl/tt_top" +libext+.v+.sv "$fp" 2>&1)"; then
  echo "[post-rtl-edit] verilator lint clean: $fp"
  exit 0
else
  printf '[post-rtl-edit] verilator lint FAILED on %s:\n%s\n' "$fp" "$out" >&2
  exit 2
fi
