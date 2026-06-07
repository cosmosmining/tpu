"""
mlp_ref.py -- 2-layer quantized MLP reference for the 8x8 MNIST demo.

Pure-integer inference built on gemm_ref.quant_gemm, using the frozen INT8 parameters in
model/mnist/mnist_int8.npz (produced by model/mnist/train_quant.py). This defines the bit-exact
classifications the silicon must reproduce end-to-end.

Network: x(64 INT8) -> [W1: H x 64, bias1, requant shift1, ReLU] -> h(H INT8)
                    -> [W2: 10 x H, bias2, requant shift2]        -> logits(10 INT8) -> argmax
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from model import gemm_ref as g

WEIGHTS_NPZ = Path(__file__).resolve().parent / "mnist" / "mnist_int8.npz"


def load_params(path=WEIGHTS_NPZ) -> dict:
    d = np.load(path)
    return {k: d[k] for k in d.files}


def quantize_input(x_norm: np.ndarray, in_shift: int) -> np.ndarray:
    """Quantize normalized pixels in [0,1] to INT8 with a power-of-two scale 2**in_shift."""
    q = np.rint(np.asarray(x_norm, dtype=np.float64) * (1 << in_shift))
    return np.clip(q, 0, g.INT8_MAX).astype(np.int8)


def mlp_infer(x_q: np.ndarray, p: dict):
    """Run one image (x_q: 64 INT8 column) through the quantized MLP.

    Returns (logits_int8[10], predicted_class). x_q may be shape (64,) or (64,1).
    """
    x = np.asarray(x_q, dtype=np.int8).reshape(64, 1)
    h = g.quant_gemm(p["W1"], x, int(p["shift1"]), bias=p["b1"], relu=True)      # (H,1)
    logits = g.quant_gemm(p["W2"], h, int(p["shift2"]), bias=p["b2"], relu=False)  # (10,1)
    logits = logits.ravel()
    return logits, int(np.argmax(logits))  # argmax: lowest index on tie


def mlp_infer_batch(X_q: np.ndarray, p: dict) -> np.ndarray:
    """Vectorized: X_q is (64, B) INT8 -> predicted classes (B,)."""
    X = np.asarray(X_q, dtype=np.int8)
    h = g.quant_gemm(p["W1"], X, int(p["shift1"]), bias=p["b1"], relu=True)        # (H,B)
    logits = g.quant_gemm(p["W2"], h, int(p["shift2"]), bias=p["b2"], relu=False)  # (10,B)
    return np.argmax(logits, axis=0)


if __name__ == "__main__":
    p = load_params()
    print("loaded params:", {k: v.shape if hasattr(v, "shape") else v for k, v in p.items()})
