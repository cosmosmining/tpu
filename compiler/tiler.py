"""
tiler.py -- map a quantized GEMM/MLP layer onto ARRAY_N x ARRAY_N TensorTile descriptors.

A layer computes Y(Nout x M) = requant(Wq(Nout x K) @ Aq(K x M) + bias). The core processes one
ARRAY_N-row output tile at a time, K-tiled over ceil(K/ARRAY_N) tiles. This produces the per-tile
descriptors + weight/activation streams the core (and, later, the RP2040 firmware) consume.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class RowTile:
    r0: int                 # first output row this tile covers
    r1: int                 # one past last valid output row (r1-r0 <= ARRAY_N)
    W: np.ndarray           # (ARRAY_N, K) INT8, zero-padded rows beyond r1-r0
    bias: np.ndarray        # (ARRAY_N,) INT64, zero-padded
    shift: int
    relu: bool


def tile_layer(Wq: np.ndarray, bias, shift: int, relu: bool, array_n: int = 4):
    """Split a layer's weights/bias into ARRAY_N-row tiles (zero-padding the final tile)."""
    Nout, K = Wq.shape
    if K % array_n != 0:
        raise ValueError(f"K={K} must be a multiple of ARRAY_N={array_n}")
    b = np.zeros(Nout, np.int64) if bias is None else np.asarray(bias, np.int64)
    tiles = []
    for r0 in range(0, Nout, array_n):
        r1 = min(r0 + array_n, Nout)
        Wt = np.zeros((array_n, K), np.int8)
        Wt[:r1 - r0] = Wq[r0:r1]
        bt = np.zeros(array_n, np.int64)
        bt[:r1 - r0] = b[r0:r1]
        tiles.append(RowTile(r0, r1, Wt, bt, shift, relu))
    return tiles


def compile_mlp(params: dict, array_n: int = 4):
    """Return per-layer RowTile lists for the 2-layer MNIST MLP."""
    layer1 = tile_layer(params["W1"], params["b1"], int(params["shift1"]), True, array_n)
    layer2 = tile_layer(params["W2"], params["b2"], int(params["shift2"]), False, array_n)
    return {"layer1": layer1, "layer2": layer2,
            "in_shift": int(params["in_shift"]), "hidden": int(params["hidden"])}


if __name__ == "__main__":
    from model import mlp_ref
    plan = compile_mlp(mlp_ref.load_params())
    n1, n2 = len(plan["layer1"]), len(plan["layer2"])
    K1 = plan["layer1"][0].W.shape[1]
    K2 = plan["layer2"][0].W.shape[1]
    print(f"MLP tiling (ARRAY_N=4): layer1 {n1} row-tiles x {K1//4} K-tiles, "
          f"layer2 {n2} row-tiles x {K2//4} K-tiles; in_shift={plan['in_shift']}")
