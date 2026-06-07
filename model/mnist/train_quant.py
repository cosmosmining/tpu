"""
train_quant.py -- offline training + power-of-two post-training quantization of the 8x8 MNIST MLP.

Reproducible (seeded). Trains a float 2-layer MLP on sklearn's 8x8 'digits' dataset (offline, no
network), then quantizes it to INT8 using ONLY power-of-two scales so the on-chip requantization
is a pure arithmetic shift (matching docs/SPEC.md s2). Freezes the integer parameters to
mnist_int8.npz (committed) and reports float vs quantized accuracy.

Run:  PYTHONPATH=. python3 model/mnist/train_quant.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

from model import gemm_ref as g
from model import mlp_ref

SEED = 0
HIDDEN = 32
IN_SHIFT = 7  # input scale 2**-7: x_q = round((pixel/16)*128) in [0,127]
OUT = Path(__file__).resolve().parent / "mnist_int8.npz"


def po2_exp_for_max(maxabs: float) -> int:
    """Exponent e so that 2**e ~= maxabs/127 (weights map into INT8 with full range)."""
    if maxabs <= 0:
        return 0
    return math.ceil(math.log2(maxabs / g.INT8_MAX))


def quantize_weights(Wf: np.ndarray):
    e = po2_exp_for_max(np.abs(Wf).max())
    scale = 2.0 ** e
    Wq = np.clip(np.rint(Wf / scale), g.INT8_MIN, g.INT8_MAX).astype(np.int8)
    return Wq, e


def quantize_bias(bf: np.ndarray, acc_scale_exp: int):
    """Bias lives in the accumulator domain: b_q = round(b_f / (2**acc_scale_exp)), clamp 16b."""
    scale = 2.0 ** acc_scale_exp
    bq = np.clip(np.rint(bf / scale), g.BIAS_MIN, g.BIAS_MAX).astype(np.int64)
    return bq


def choose_shift(acc: np.ndarray) -> int:
    """Smallest shift>=0 mapping the max accumulator magnitude into INT8 range."""
    m = int(np.abs(acc).max())
    if m <= g.INT8_MAX:
        return 0
    return max(0, math.ceil(math.log2(m / g.INT8_MAX)))


def main() -> int:
    digits = load_digits()
    X = digits.data / 16.0           # normalize pixels [0,16] -> [0,1]
    y = digits.target
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=SEED, stratify=y)

    clf = MLPClassifier(hidden_layer_sizes=(HIDDEN,), activation="relu", solver="adam",
                        alpha=1e-4, max_iter=600, random_state=SEED)
    clf.fit(Xtr, ytr)
    float_acc = clf.score(Xte, yte)

    # --- extract float params (W1: H x 64, W2: 10 x H) ---
    W1f = clf.coefs_[0].T.astype(np.float64)
    b1f = clf.intercepts_[0].astype(np.float64)
    W2f = clf.coefs_[1].T.astype(np.float64)
    b2f = clf.intercepts_[1].astype(np.float64)

    # --- quantize (power-of-two scales) ---
    W1q, e_w1 = quantize_weights(W1f)
    W2q, e_w2 = quantize_weights(W2f)
    # accumulator scale exponents: acc ~ real / 2**(e_w + e_x)
    e_x = -IN_SHIFT
    acc1_exp = e_w1 + e_x
    b1q = quantize_bias(b1f, acc1_exp)

    # quantize training inputs to pick shift1 deterministically
    Xtr_q = mlp_ref.quantize_input(Xtr, IN_SHIFT).T   # (64, Ntr)
    acc1 = g.matmul_acc(W1q, Xtr_q) + b1q[:, None]
    shift1 = choose_shift(acc1)
    e_h = acc1_exp + shift1                            # hidden activation scale exponent
    acc2_exp = e_w2 + e_h
    b2q = quantize_bias(b2f, acc2_exp)

    h_tr = g.requant_tensor(acc1, shift1, bias=None, relu=True)  # bias already folded into acc1
    acc2 = g.matmul_acc(W2q, h_tr) + b2q[:, None]
    shift2 = choose_shift(acc2)

    params = dict(
        W1=W1q, b1=b1q, shift1=np.int64(shift1),
        W2=W2q, b2=b2q, shift2=np.int64(shift2),
        in_shift=np.int64(IN_SHIFT), hidden=np.int64(HIDDEN),
        e_w1=np.int64(e_w1), e_w2=np.int64(e_w2), e_x=np.int64(e_x),
        e_h=np.int64(e_h), acc1_exp=np.int64(acc1_exp), acc2_exp=np.int64(acc2_exp),
    )

    # --- evaluate the frozen integer model on the test set ---
    Xte_q = mlp_ref.quantize_input(Xte, IN_SHIFT).T   # (64, Nte)
    pred = mlp_ref.mlp_infer_batch(Xte_q, params)
    quant_acc = float((pred == yte).mean())

    np.savez(OUT, **params)

    print("=== TensorTile MNIST (8x8) train+quant ===")
    print(f"  hidden={HIDDEN}  seed={SEED}  train/test={len(ytr)}/{len(yte)}")
    print(f"  scales (po2 exponents): e_x={e_x} e_w1={e_w1} e_h={e_h} e_w2={e_w2}")
    print(f"  requant shifts: shift1={shift1} shift2={shift2}")
    print(f"  bias range used: b1[{int(b1q.min())},{int(b1q.max())}] "
          f"b2[{int(b2q.min())},{int(b2q.max())}] (16b limit +-32768)")
    print(f"  FLOAT  test accuracy: {float_acc*100:.2f}%")
    print(f"  INT8   test accuracy: {quant_acc*100:.2f}%  (bit-exact integer path)")
    print(f"  frozen weights -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
