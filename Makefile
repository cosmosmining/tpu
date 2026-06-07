# TensorTile -- top-level Makefile.
# Everything reproducible from a clean clone: `make <target>` reproduces every result.
# Real today (Phase 0): setup, smoke, lint, metrics, clean.
# Documented placeholders (print a notice, exit 0; see DECISIONS.md): sim, regress, formal,
# cov, synth, dft, harden, sweep, predict -- each goes live in its phase.

PY        ?= python3
VERILATOR ?= verilator
IVERILOG  ?= iverilog
TOP_MOD   := tt_um_tensortile
RTL_TOP   := rtl/tt_top/tt_um_tensortile.v
RTL_INC   := rtl/core rtl/tt_top

.DEFAULT_GOAL := help
.PHONY: help setup smoke lint sim regress formal cov synth dft harden sweep predict metrics clean

help: ## list targets
	@echo "TensorTile make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

setup: ## provision tools (pip + apt; idempotent)
	@bash scripts/setup_tools.sh

smoke: ## PHASE-0 GATE: env + known-answer matmul + compile top stub
	@$(PY) scripts/smoke.py

lint: ## verilator --lint-only -Wall (+ verible if present); zero errors required
	@echo ">> lint"
	@if command -v $(VERILATOR) >/dev/null 2>&1; then \
		$(VERILATOR) --lint-only -Wall $(addprefix -I,$(RTL_INC)) --top-module $(TOP_MOD) $(RTL_TOP) \
		  && echo "   verilator: clean"; \
	else echo "   verilator: MISSING -> CI/later (SKIP, not silent: logged)"; fi
	@if command -v verible-verilog-lint >/dev/null 2>&1; then \
		verible-verilog-lint $(RTL_TOP) && echo "   verible: clean"; \
	else echo "   verible: MISSING -> CI/later (SKIP, not silent: logged)"; fi

metrics: ## append a METRICS.md row from summary.json
	@$(PY) scripts/metrics.py --from-summary summary.json

# ---- documented placeholders (go live in the noted phase) -------------------
sim: ## [Phase 2] cocotb lockstep benches
	@echo ">> sim -- Phase 2 (cocotb PE/row/array/core lockstep). Placeholder; see DECISIONS.md."

regress: ## [Phase 3] full constrained-random regression (>=1M MACs)
	@echo ">> regress -- Phase 3 (>=1M MACs, >=95% func cov). Placeholder; see DECISIONS.md."

formal: ## [Phase 4] SymbiYosys proofs
	@echo ">> formal -- Phase 4 (FIFO/FSM/descq/accumulator). Placeholder; see DECISIONS.md."

cov: ## [Phase 3] functional + code coverage report
	@echo ">> cov -- Phase 3 coverage report. Placeholder; see DECISIONS.md."

synth: ## [Phase 2+] Yosys synth + area/flop report
	@echo ">> synth -- Phase 2+ (Yosys area/flops -> METRICS.md). Placeholder; see DECISIONS.md."

dft: ## [Phase 6] Fault scan insertion + ATPG
	@echo ">> dft -- Phase 6 (scan + ATPG >=95%). Placeholder; see DECISIONS.md."

harden: ## [Phase 7] LibreLane/ORFS single-point hardening
	@echo ">> harden -- Phase 7 (LibreLane/ORFS). Placeholder; see DECISIONS.md."

sweep: ## [Phase 7] parallel DSE (ARRAY_N x pipelining x clk x density)
	@echo ">> sweep -- Phase 7 (Pareto DSE). Placeholder; see DECISIONS.md."

predict: ## [Phase 7] freeze PREDICTIONS.md from STA/area
	@echo ">> predict -- Phase 7 (freeze PREDICTIONS.md). Placeholder; see DECISIONS.md."

clean: ## remove build artifacts
	@rm -rf build sim_build obj_dir *.vcd summary.json __pycache__ scripts/__pycache__ \
		model/__pycache__ dv/cocotb/__pycache__ .pytest_cache
	@echo "cleaned."
