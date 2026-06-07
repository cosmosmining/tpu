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
		$(VERILATOR) --lint-only -Wall -y rtl/core +libext+.v --top-module tensortile_core \
		  rtl/core/tensortile_core.v && \
		$(VERILATOR) --lint-only -Wall -y rtl/core -y rtl/tt_top +libext+.v \
		  --top-module $(TOP_MOD) $(RTL_TOP) \
		  && echo "   verilator: clean"; \
	else echo "   verilator: MISSING -> CI/later (SKIP, not silent: logged)"; fi
	@if command -v verible-verilog-lint >/dev/null 2>&1; then \
		verible-verilog-lint $(RTL_TOP) && echo "   verible: clean"; \
	else echo "   verible: MISSING -> CI/later (SKIP, not silent: logged)"; fi

metrics: ## append a METRICS.md row from summary.json
	@$(PY) scripts/metrics.py --from-summary summary.json

# ---- documented placeholders (go live in the noted phase) -------------------
sim: ## cocotb lockstep benches (array / requant / fifo / core) vs the NumPy model
	@PYTHONPATH=. $(PY) -m pytest dv/cocotb -q -k "not regress and not mnist"

demo: ## end-to-end MNIST through the RTL core (>=100 images, bit-exact vs model)
	@PYTHONPATH=. MNIST_IMAGES=$${MNIST_IMAGES:-100} $(PY) -m pytest dv/cocotb -q -k mnist

regress: ## constrained-random regression (>=1M MACs, >=95% func cov) -> dv/coverage_phase3.md
	@PYTHONPATH=. REGRESS_MACS=$${REGRESS_MACS:-1000000} $(PY) -m pytest dv/cocotb -q -k regress

formal: ## formal proofs (yosys sat k-induction): FIFO safety + core FSM/accumulator
	@if command -v yosys >/dev/null 2>&1; then \
		echo ">> formal: tt_fifo"        && yosys -q -s dv/formal/prove_fifo.ys && echo "   tt_fifo: PROVEN (k-induction)"; \
		echo ">> formal: tensortile_core" && yosys -q -s dv/formal/prove_core.ys && echo "   tensortile_core: PROVEN (k-induction)"; \
	else echo "   yosys: MISSING -> CI/later (SKIP, not silent: logged)"; fi

cov: ## [Phase 3] functional + code coverage report
	@echo ">> cov -- Phase 3 coverage report. Placeholder; see DECISIONS.md."

synth: ## Yosys generic synth: flop/cell counts per block -> synth/stat_*.txt
	@if command -v yosys >/dev/null 2>&1; then \
		yosys -q -s synth/synth_area.ys -l synth/synth.log && \
		echo "   synth done -> synth/stat_total.txt, synth/area_report.md"; \
	else echo "   yosys: MISSING -> CI/later (SKIP, not silent: logged)"; fi

dft: ## [Phase 6] Fault scan insertion + ATPG
	@echo ">> dft -- Phase 6 (scan + ATPG >=95%). Placeholder; see DECISIONS.md."

harden: ## [Phase 7] LibreLane/ORFS single-point hardening
	@echo ">> harden -- Phase 7 (LibreLane/ORFS). Placeholder; see DECISIONS.md."

sweep: ## sky130 area DSE across ARRAY_N x MAX_COLS x ACC_W -> pnr/dse_report.md
	@bash pnr/sweep_sky130.sh

predict: ## [Phase 7] freeze PREDICTIONS.md from STA/area
	@echo ">> predict -- Phase 7 (freeze PREDICTIONS.md). Placeholder; see DECISIONS.md."

clean: ## remove build artifacts
	@rm -rf build sim_build obj_dir *.vcd summary.json __pycache__ scripts/__pycache__ \
		model/__pycache__ dv/cocotb/__pycache__ .pytest_cache
	@echo "cleaned."
