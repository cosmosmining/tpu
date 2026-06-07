"""
gemm_ref.py -- TensorTile bit-exact quantized GEMM reference (THE arithmetic contract).

This module DEFINES the arithmetic. RTL and silicon must match it to the bit on every output.
It may NEVER be edited to make failing RTL pass -- changes require a docs/SPEC.md citation and a
DECISIONS.md entry. See docs/SPEC.md section 2 for the prose contract and worked examples (which
are generated from -- and tested against -- this code).

Pipeline for one output element y:
    1. acc = sum_k W[n,k] * A[k,m]              # INT8 x INT8 products, exact, signed
       (K-tiling: acc carries across tiles; bias added only on the final tile)
    2. t   = acc + bias                          # bias: signed, 16-bit (P1); 0 if disabled
    3. r   = round_half_up(t / 2**shift)         # arithmetic right shift, round half toward +inf
    4. y   = clamp(r, lo, 127),  lo = 0 if relu else -128   # saturate to INT8 (ReLU = lo 0)

Widths: operands DATA_W=8 (INT8), accumulator ACC_W=24 signed (two's complement, non-saturating
-- valid descriptors must not overflow it; see SPEC section 2.3 for the K bound). Internally we
compute in Python/NumPy integers (exact) so the model is the golden truth; the RTL realizes the
same values in fixed widths.
"""
from __future__ import annotations

import numpy as np

# --- parameters / constants (mirror RTL top params; never hardcode elsewhere) ---------------
DATA_W = 8
ACC_W = 24
INT8_MIN, INT8_MAX = -128, 127
ACC_MIN, ACC_MAX = -(1 << (ACC_W - 1)), (1 << (ACC_W - 1)) - 1      # signed 24b
BIAS_W = 16
BIAS_MIN, BIAS_MAX = -(1 << (BIAS_W - 1)), (1 << (BIAS_W - 1)) - 1  # signed 16b


# ============================================================================================
# Scalar requantization -- the rounding/saturation rule, defined once.
# ============================================================================================
def round_half_up_shift(t: int, shift: int) -> int:
    """floor((t + 2**(shift-1)) / 2**shift): arithmetic right shift, ties round toward +inf.

    shift == 0 is exact passthrough (no rounding bias added). Python's >> on ints is an
    arithmetic floor shift, which is exactly a two's-complement arithmetic right shift.
    """
    if shift < 0:
        raise ValueError("shift must be >= 0")
    if shift == 0:
        return int(t)
    return (int(t) + (1 << (shift - 1))) >> shift


def clamp(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x


def requant_scalar(acc: int, shift: int, bias: int = 0, relu: bool = False) -> int:
    """Full per-element requant: (acc + bias) -> round-half-up shift -> saturate to INT8."""
    if not (BIAS_MIN <= bias <= BIAS_MAX):
        raise ValueError(f"bias {bias} outside signed {BIAS_W}-bit range")
    t = int(acc) + int(bias)
    r = round_half_up_shift(t, shift)
    lo = 0 if relu else INT8_MIN
    return clamp(r, lo, INT8_MAX)


# ============================================================================================
# Tensor-level helpers.
# ============================================================================================
def _check_int8(name: str, a: np.ndarray) -> np.ndarray:
    a = np.asarray(a)
    if not np.issubdtype(a.dtype, np.integer):
        raise TypeError(f"{name} must be integer dtype, got {a.dtype}")
    if a.min(initial=0) < INT8_MIN or a.max(initial=0) > INT8_MAX:
        raise ValueError(f"{name} has values outside INT8 [{INT8_MIN},{INT8_MAX}]")
    return a.astype(np.int64)


def matmul_acc(W_i8: np.ndarray, A_i8: np.ndarray) -> np.ndarray:
    """Exact integer accumulation Y[n,m] = sum_k W[n,k]*A[k,m]. Returns int64 (the 'acc').

    W: (Nout, K) INT8 weights (weight-stationary).  A: (K, M) INT8 activations.
    """
    W = _check_int8("W", W_i8)
    A = _check_int8("A", A_i8)
    if W.shape[1] != A.shape[0]:
        raise ValueError(f"K mismatch: W is {W.shape}, A is {A.shape}")
    return W @ A  # int64, exact for our operand ranges


def requant_tensor(acc: np.ndarray, shift: int, bias=None, relu: bool = False) -> np.ndarray:
    """Vectorized requant of an accumulator tensor -> INT8 ndarray. bias broadcasts over outputs."""
    acc = np.asarray(acc, dtype=np.int64)
    if bias is None:
        b = np.zeros(acc.shape[:1] if acc.ndim else (), dtype=np.int64)
    else:
        b = np.asarray(bias, dtype=np.int64)
        if np.any(b < BIAS_MIN) or np.any(b > BIAS_MAX):
            raise ValueError("bias outside signed 16-bit range")
    # broadcast bias over the output-row axis (first axis) when 2-D
    if acc.ndim == 2 and b.ndim == 1:
        b = b[:, None]
    t = acc + b
    if shift == 0:
        r = t
    else:
        r = (t + (1 << (shift - 1))) >> shift  # numpy >> on int64 is arithmetic
    lo = 0 if relu else INT8_MIN
    return np.clip(r, lo, INT8_MAX).astype(np.int8)


def quant_gemm(W_i8, A_i8, shift: int, bias=None, relu: bool = False) -> np.ndarray:
    """Full quantized GEMM: requant(W@A + bias). Returns INT8 (Nout, M)."""
    return requant_tensor(matmul_acc(W_i8, A_i8), shift, bias=bias, relu=relu)


def quant_gemm_ktiled(W_tiles, A_tiles, shift: int, bias=None, relu: bool = False) -> np.ndarray:
    """K-tiled GEMM: accumulate across K-tiles (hardware accumulate-enable), bias+requant on the
    final tile only. Must equal quant_gemm on the concatenation of the tiles (validated in tests).

    W_tiles: list of (Nout, Kt) INT8.   A_tiles: list of (Kt, M) INT8.
    """
    if len(W_tiles) != len(A_tiles):
        raise ValueError("tile count mismatch")
    acc = None
    for Wt, At in zip(W_tiles, A_tiles):
        part = matmul_acc(Wt, At)
        acc = part if acc is None else acc + part
        if not (np.all(acc >= ACC_MIN) and np.all(acc <= ACC_MAX)):
            raise OverflowError("accumulator exceeded signed 24-bit range (invalid descriptor)")
    return requant_tensor(acc, shift, bias=bias, relu=relu)


if __name__ == "__main__":
    # tiny self-demo
    W = np.array([[1, 2, 3], [-4, 5, -6]], dtype=np.int8)
    A = np.array([[7, -8], [9, 10], [-11, 12]], dtype=np.int8)
    print("acc =\n", matmul_acc(W, A))
    print("quant_gemm(shift=2) =\n", quant_gemm(W, A, shift=2))
