"""pytest entry points that build the RTL and run the cocotb lockstep benches via the runner.

Run all:   PYTHONPATH=. python3 -m pytest dv/cocotb -q
One level: PYTHONPATH=. python3 -m pytest dv/cocotb -q -k array
Sim:       SIM=icarus (default) or SIM=verilator
"""
import os
from pathlib import Path

from cocotb_tools.runner import get_runner, get_results

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "rtl" / "core"
SIM = os.environ.get("SIM", "icarus")
PARAMS = {"ARRAY_N": 4, "DATA_W": 8, "ACC_W": 24}


def _env():
    env = dict(os.environ)
    extra = [str(REPO), str(REPO / "dv" / "cocotb")]
    if env.get("PYTHONPATH"):
        extra.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(extra)
    env.update(ARRAY_N=str(PARAMS["ARRAY_N"]), DATA_W=str(PARAMS["DATA_W"]),
               ACC_W=str(PARAMS["ACC_W"]), MAX_COLS="8",
               FIFO_WIDTH="8", FIFO_DEPTH="8")
    return env


def _run(sources, toplevel, test_module, params=None):
    params = PARAMS if params is None else params
    runner = get_runner(SIM)
    runner.build(sources=[str(s) for s in sources], hdl_toplevel=toplevel,
                 parameters=params, build_dir=str(REPO / "build" / f"sim_{toplevel}"),
                 timescale=("1ns", "1ps"), always=True)
    results = runner.test(hdl_toplevel=toplevel, test_module=test_module,
                          test_dir=str(REPO / "dv" / "cocotb"), extra_env=_env())
    total, failed = get_results(results)
    assert failed == 0, f"{failed}/{total} cocotb tests failed in {test_module}"


def test_array():
    _run([CORE / "tt_pe.v", CORE / "tt_mac_array.v"], "tt_mac_array", "tb_array")


def test_requant():
    _run([CORE / "tt_requant.v"], "tt_requant", "tb_requant",
         params={"ACC_W": 24, "DATA_W": 8, "BIAS_W": 16})


def test_fifo():
    _run([CORE / "tt_fifo.v"], "tt_fifo", "tb_fifo", params={"WIDTH": 8, "DEPTH": 8})


def test_core():
    _run([CORE / "tt_pe.v", CORE / "tt_mac_array.v", CORE / "tt_requant.v",
          CORE / "tensortile_core.v"], "tensortile_core", "tb_core",
         params={"ARRAY_N": 4, "DATA_W": 8, "ACC_W": 24, "BIAS_W": 16, "MAX_COLS": 8})
