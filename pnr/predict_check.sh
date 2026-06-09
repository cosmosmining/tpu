#!/usr/bin/env bash
# Phase 7 `make predict`: re-derive full-chip sky130 area at the tapeout point
# (ARRAY_N=4, MAX_COLS=4, ACC_W=24, 8x2 tiles) and enforce the <=70% util gate that
# PREDICTIONS.md pre-registers. NB: yosys-abc area here runs ~30% below OpenLane synth (see
# PREDICTIONS addendum 2026-06-08); Fmax/placement are graded in CI (OpenSTA/OpenROAD).
set -uo pipefail
DIE_UM2=${DIE_UM2:-256000}     # 8x2 TT tiles (~1280x200 um)
UTIL_TGT=70
SRC="rtl/core/tt_pe.v rtl/core/tt_mac_array.v rtl/core/tt_requant.v rtl/core/tt_fifo.v \
     rtl/core/tensortile_core.v rtl/core/tensortile_engine.v rtl/tt_top/tt_spi_host.v \
     rtl/tt_top/tt_um_tensortile.v"

LIB=$(find "${PDK_ROOT:-/home/user/.volare}" -iname "sky130_fd_sc_hd__tt_025C_1v80.lib" 2>/dev/null | head -1)
if [ -z "$LIB" ] || ! command -v yosys >/dev/null 2>&1; then
  echo "predict: yosys/sky130 liberty not present -> area re-check is CI/later (frozen values in PREDICTIONS.md)"
  exit 0
fi

AREA=$(yosys -p "read_verilog -sv $SRC; hierarchy -top tt_um_tensortile;
  synth -top tt_um_tensortile -flatten; dfflibmap -liberty $LIB; abc -liberty $LIB; clean;
  stat -liberty $LIB" 2>/dev/null | grep -m1 "Chip area" | grep -oE "[0-9]+\.[0-9]+")
if [ -z "$AREA" ]; then echo "predict: synth produced no area -> check tools"; exit 1; fi

UTIL=$(awk -v a="$AREA" -v d="$DIE_UM2" 'BEGIN{printf "%.1f", 100*a/d}')
printf "predict @ FROZEN point (N4,MC4,ACC24,6x2): area=%.0f um^2  util=%s%% of %s  (target <=%s%%)\n" \
       "$AREA" "$UTIL" "$DIE_UM2" "$UTIL_TGT"
PASS=$(awk -v u="$UTIL" -v t="$UTIL_TGT" 'BEGIN{print (u<=t)?"PASS":"FAIL"}')
echo "predict: area gate $PASS.  Fmax(OpenSTA)+placement util(OpenROAD) graded in CI vs PREDICTIONS.md targets."
[ "$PASS" = "PASS" ] || exit 1