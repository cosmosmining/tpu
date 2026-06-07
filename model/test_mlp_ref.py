"""Tests for the frozen quantized MLP: accuracy floor, batch==scalar, and K-tiled==full path."""
import numpy as np
import pytest
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

from model import gemm_ref as g
from model import mlp_ref

pytestmark = pytest.mark.skipif(not mlp_ref.WEIGHTS_NPZ.exists(),
                                reason="frozen weights missing; run model/mnist/train_quant.py")


@pytest.fixture(scope="module")
def params():
    return mlp_ref.load_params()


@pytest.fixture(scope="module")
def testset():
    digits = load_digits()
    X = digits.data / 16.0
    y = digits.target
    _, Xte, _, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    return mlp_ref.quantize_input(Xte, 7).T, yte  # (64, N), labels


def test_frozen_accuracy_floor(params, testset):
    Xq, y = testset
    acc = (mlp_ref.mlp_infer_batch(Xq, params) == y).mean()
    assert acc >= 0.93, f"quantized accuracy regressed to {acc:.4f}"


def test_batch_matches_scalar(params, testset):
    Xq, _ = testset
    batch = mlp_ref.mlp_infer_batch(Xq[:, :20], params)
    scalar = np.array([mlp_ref.mlp_infer(Xq[:, i], params)[1] for i in range(20)])
    np.testing.assert_array_equal(batch, scalar)


def test_layer1_ktiled_equals_full(params, testset):
    """The systolic core accumulates layer 1 over K=64 in ARRAY_N=4 chunks; that must match."""
    Xq, _ = testset
    x = Xq[:, :8]                       # a few images
    W1, b1, s1 = params["W1"], params["b1"], int(params["shift1"])
    full = g.quant_gemm(W1, x, s1, bias=b1, relu=True)
    Wt = [W1[:, i:i + 4] for i in range(0, 64, 4)]   # 16 K-tiles of width 4
    At = [x[i:i + 4, :] for i in range(0, 64, 4)]
    tiled = g.quant_gemm_ktiled(Wt, At, s1, bias=b1, relu=True)
    np.testing.assert_array_equal(full, tiled)


def test_inference_is_deterministic(params, testset):
    Xq, _ = testset
    a = mlp_ref.mlp_infer_batch(Xq, params)
    b = mlp_ref.mlp_infer_batch(Xq, params)
    np.testing.assert_array_equal(a, b)
