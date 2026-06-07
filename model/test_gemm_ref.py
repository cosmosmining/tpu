"""Unit tests for the bit-exact GEMM reference. These also pin the worked examples in SPEC s2."""
import numpy as np
import pytest

from model import gemm_ref as g


# --- rounding rule: round half up (ties toward +inf), arithmetic shift -----------------------
@pytest.mark.parametrize("t,shift,expected", [
    (0, 0, 0),
    (5, 0, 5),            # shift 0 = exact passthrough
    (6, 2, 2),            # 6/4 = 1.5 -> half up -> 2
    (5, 2, 1),            # 5/4 = 1.25 -> 1
    (7, 2, 2),            # 7/4 = 1.75 -> 2
    (-6, 2, -1),          # -6/4 = -1.5 -> half up (toward +inf) -> -1
    (-5, 2, -1),          # -5/4 = -1.25 -> -1
    (-7, 2, -2),          # -7/4 = -1.75 -> -2
    (-2, 2, 0),           # -2/4 = -0.5 -> 0
    (2, 2, 1),            # 2/4 = 0.5 -> 1
    (1 << 23, 9, 16384),  # large positive exact
])
def test_round_half_up(t, shift, expected):
    assert g.round_half_up_shift(t, shift) == expected


def test_round_negative_shift_rejected():
    with pytest.raises(ValueError):
        g.round_half_up_shift(4, -1)


# --- saturation + ReLU ----------------------------------------------------------------------
def test_saturation_high():
    assert g.requant_scalar(300, shift=0) == 127           # 300 -> sat 127
    assert g.requant_scalar(1 << 20, shift=0) == 127


def test_saturation_low():
    assert g.requant_scalar(-300, shift=0) == -128          # -300 -> sat -128
    assert g.requant_scalar(-300, shift=0, relu=True) == 0  # ReLU lower bound is 0


def test_relu():
    assert g.requant_scalar(-5, shift=0, relu=False) == -5
    assert g.requant_scalar(-5, shift=0, relu=True) == 0
    assert g.requant_scalar(50, shift=0, relu=True) == 50


def test_bias():
    assert g.requant_scalar(100, shift=0, bias=27) == 127        # 127 exactly
    assert g.requant_scalar(100, shift=0, bias=28) == 127        # 128 -> sat 127
    assert g.requant_scalar(-100, shift=0, bias=-28, relu=False) == -128
    with pytest.raises(ValueError):
        g.requant_scalar(0, shift=0, bias=g.BIAS_MAX + 1)


# --- most-negative operand: -128 * -128 = +16384 (no abs() trap) -----------------------------
def test_most_negative_operands():
    W = np.array([[-128]], dtype=np.int8)
    A = np.array([[-128]], dtype=np.int8)
    assert int(g.matmul_acc(W, A)[0, 0]) == 16384
    # 4 such products then requant by 9: (65536 + 256) >> 9 = 128 -> sat 127
    W4 = np.full((1, 4), -128, dtype=np.int8)
    A4 = np.full((4, 1), -128, dtype=np.int8)
    assert int(g.matmul_acc(W4, A4)[0, 0]) == 65536
    assert int(g.quant_gemm(W4, A4, shift=9)[0, 0]) == 127
    # 127 * -128 = -16256 is the most-negative single product
    assert int(g.matmul_acc(np.array([[127]], np.int8),
                            np.array([[-128]], np.int8))[0, 0]) == -16256


# --- known-answer matmul (matches scripts/smoke.py) -----------------------------------------
def test_known_answer_matmul():
    W = np.array([[1, 2, 3], [-4, 5, -6]], dtype=np.int8)
    A = np.array([[7, -8], [9, 10], [-11, 12]], dtype=np.int8)
    np.testing.assert_array_equal(g.matmul_acc(W, A),
                                  np.array([[-8, 48], [83, 10]], dtype=np.int64))


# --- K-tiling carry equals the full untiled GEMM --------------------------------------------
def test_ktiling_equals_full():
    rng = np.random.default_rng(0)
    Nout, K, M = 4, 12, 5
    W = rng.integers(-128, 128, size=(Nout, K), dtype=np.int8)
    A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
    bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=Nout)
    for shift in (0, 3, 7):
        for relu in (False, True):
            full = g.quant_gemm(W, A, shift, bias=bias, relu=relu)
            # split K into tiles of 4 (ARRAY_N)
            Wt = [W[:, i:i + 4] for i in range(0, K, 4)]
            At = [A[i:i + 4, :] for i in range(0, K, 4)]
            tiled = g.quant_gemm_ktiled(Wt, At, shift, bias=bias, relu=relu)
            np.testing.assert_array_equal(full, tiled)


def test_accumulator_overflow_detected():
    # Force > 24-bit accumulation across many max-magnitude tiles.
    W = np.full((1, 4), 127, dtype=np.int8)
    A = np.full((4, 1), 127, dtype=np.int8)   # 4*127*127 = 64516 per tile
    tiles = 200                               # 200*64516 = 12.9M > 2^23-1
    with pytest.raises(OverflowError):
        g.quant_gemm_ktiled([W] * tiles, [A] * tiles, shift=0)


# --- input validation -----------------------------------------------------------------------
def test_out_of_range_inputs_rejected():
    with pytest.raises(ValueError):
        g.matmul_acc(np.array([[200]], dtype=np.int16), np.array([[1]], dtype=np.int16))


# --- cross-check vectorized requant vs scalar over a sweep -----------------------------------
def test_vectorized_matches_scalar():
    rng = np.random.default_rng(1)
    acc = rng.integers(-(1 << 20), 1 << 20, size=200, dtype=np.int64)
    bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=200)
    for shift in (0, 1, 5, 11):
        for relu in (False, True):
            vec = g.requant_tensor(acc, shift, bias=bias, relu=relu)
            sca = np.array([g.requant_scalar(int(a), shift, int(b), relu)
                            for a, b in zip(acc, bias)], dtype=np.int8)
            np.testing.assert_array_equal(vec, sca)
