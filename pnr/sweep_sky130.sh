#!/usr/bin/env bash
# Phase-7 area DSE: sky130-mapped synthesis of tensortile_core across design points.
# Reports std-cell count + cell area (um^2) + utilization vs the 4x2 TT tile (~128000 um^2).
# Needs yosys + the sky130_fd_sc_hd tt liberty (volare). Fmax needs OpenSTA (CI/later).
set -uo pipefail
DIE_UM2=${DIE_UM2:-128000}     # 4x2 TT tiles ~640x200 um (SPEC area budget)
UTIL_TGT=70

LIB=$(find "${PDK_ROOT:-/home/user/.volare}" -iname "sky130_fd_sc_hd__tt_025C_1v80.lib" 2>/dev/null | head -1)
if [ -z "$LIB" ]; then echo "sky130 liberty not found (volare enable sky130) -> CI/later"; exit 0; fi

printf "%-32s %8s %12s %8s\n" "config(ARRAY_N,MAX_COLS,ACC_W)" "cells" "area_um2" "util%"
run() { # $1=ARRAY_N $2=MAX_COLS $3=ACC_W
  local n=$1 mc=$2 aw=$3 log
  log=$(yosys -p "
    read_verilog rtl/core/tt_pe.v rtl/core/tt_mac_array.v rtl/core/tt_requant.v rtl/core/tensortile_core.v
    hierarchy -top tensortile_core -chparam ARRAY_N $n -chparam DATA_W 8 -chparam ACC_W $aw -chparam BIAS_W 16 -chparam MAX_COLS $mc
    synth -top tensortile_core -flatten
    dfflibmap -liberty $LIB
    abc -liberty $LIB
    clean
    stat -liberty $LIB
  " 2>/dev/null)
  local cells area util
  cells=$(echo "$log" | grep -m1 "Number of cells:" | grep -oE "[0-9]+")
  area=$(echo "$log" | grep -m1 "Chip area" | grep -oE "[0-9]+\.[0-9]+")
  util=$(awk -v a="$area" -v d="$DIE_UM2" 'BEGIN{printf "%.1f", 100*a/d}')
  printf "%-32s %8s %12.0f %8s\n" "N=$n,MC=$mc,ACC=$aw" "$cells" "$area" "$util"
}
run 4 8 24
run 4 4 24
run 4 2 24
run 4 8 20
run 3 4 24
echo "(area = sum of std-cell areas, pre-place; util vs ${DIE_UM2}um^2 die; target <=${UTIL_TGT}%."
echo " core only — add I/O FIFOs + SPI/CSR wrapper for full-chip. Fmax via OpenSTA: CI/later.)"
