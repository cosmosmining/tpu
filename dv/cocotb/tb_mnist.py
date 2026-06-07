"""
tb_mnist.py -- end-to-end 8x8 MNIST demo through the RTL core (Phase 5 flagship).

Compiles the frozen quantized MLP into ARRAY_N x ARRAY_N tiles and runs >= MNIST_IMAGES test
images through tensortile_core, assembling hidden/logits from the per-tile results. Every image's
RTL prediction (and logits) must match model/mlp_ref bit-exactly; reports demo accuracy.
"""
import os

import cocotb
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

from coreio import reset, run_descriptor
from compiler.tiler import compile_mlp
from model import mlp_ref

NIMG = int(os.environ.get("MNIST_IMAGES", "100"))


async def _run_layer(dut, tiles, A_q):
    """Run one layer (list of RowTile) on activation A_q (K x 1) -> output vector (Nout,)."""
    Nout = max(t.r1 for t in tiles)
    out = np.zeros(Nout, dtype=np.int64)
    for t in tiles:
        y = await run_descriptor(dut, t.W, A_q, shift=t.shift,
                                 bias=t.bias, relu=t.relu)          # (ARRAY_N, 1)
        out[t.r0:t.r1] = y[:t.r1 - t.r0, 0]
    return out


@cocotb.test()
async def test_mnist_demo(dut):
    await reset(dut)
    params = mlp_ref.load_params()
    plan = compile_mlp(params)

    digits = load_digits()
    X = digits.data / 16.0
    y = digits.target
    _, Xte, _, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    Xq = mlp_ref.quantize_input(Xte, plan["in_shift"]).astype(np.int8)   # (Ntest, 64)

    nimg = min(NIMG, Xq.shape[0])
    correct = 0
    bitexact = 0
    for i in range(nimg):
        x = Xq[i].reshape(64, 1)
        hidden = await _run_layer(dut, plan["layer1"], x)               # (32,)
        h_q = hidden.astype(np.int8).reshape(plan["hidden"], 1)
        logits = await _run_layer(dut, plan["layer2"], h_q)            # (10,)
        rtl_pred = int(np.argmax(logits))

        ref_logits, ref_pred = mlp_ref.mlp_infer(Xq[i], params)
        assert np.array_equal(logits[:10], ref_logits.astype(np.int64)), (
            f"img {i}: RTL logits {logits[:10]} != model {ref_logits}")
        assert rtl_pred == ref_pred, f"img {i}: RTL pred {rtl_pred} != model {ref_pred}"
        bitexact += 1
        if rtl_pred == int(yte[i]):
            correct += 1

    acc = 100.0 * correct / nimg
    dut._log.info(f"MNIST demo: {nimg} images, RTL==model bit-exact on {bitexact}/{nimg}, "
                  f"silicon accuracy {acc:.2f}%")
    assert bitexact == nimg, f"only {bitexact}/{nimg} bit-exact"
    if not os.environ.get("MNIST_QUICK"):
        assert nimg >= 100, f"demo ran only {nimg} images (< 100); set MNIST_IMAGES>=100"
