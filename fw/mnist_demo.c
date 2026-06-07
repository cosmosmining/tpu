// mnist_demo.c -- TensorTile RP2040 MNIST demo (8x8 digits, M=1 inference).
// Mirrors the verified dv/cocotb/tb_mnist flow: tile each MLP layer into ARRAY_N x ARRAY_N tiles,
// stream through the accelerator, assemble the layer output, argmax. HW-untested (pending silicon).
#include <stdint.h>
#include <stdio.h>
#include "tensortile.h"
#include "mnist_weights.h"

#define N TT_ARRAY_N

// Quantize an 8x8 pixel (0..16) to INT8 at scale 2^-TT_IN_SHIFT: x_q = clamp(pixel<<(in_shift-4),127).
static inline int8_t quant_px(uint8_t px) {
    int v = (int)px << (TT_IN_SHIFT - 4);   // in_shift=7 -> px*8
    return (int8_t)(v > 127 ? 127 : v);
}

// One output row-tile (rows r0..r0+valid-1, K-tiled), activation = column x[0..K-1]. M=1.
// w_rowmajor is the layer's weights (Nout x K), row-major. Writes `valid` results to out.
static void run_row_tile(const int8_t *w_rowmajor, int K, int r0, int valid,
                         uint8_t shift, int relu, const int16_t *bias_row, const int8_t *x,
                         int8_t *out) {
    int nkt = K / N;
    if (bias_row) tt_load_bias(bias_row, N);
    tt_enqueue(1 /*num_cols*/, (uint8_t)nkt, shift, relu, bias_row != 0);
    int8_t wtile[N * N];
    for (int kt = 0; kt < nkt; kt++) {
        for (int kl = 0; kl < N; kl++)
            for (int c = 0; c < N; c++)
                wtile[kl * N + c] = (c < valid) ? w_rowmajor[(r0 + c) * K + (kt * N + kl)] : 0;
        tt_push_weight_tile(wtile);
        tt_push_act_col(&x[kt * N]);                 // one column (N activations)
    }
    int8_t res[N];
    tt_read_results(res, N);                          // N results (col-major, M=1)
    for (int c = 0; c < valid; c++) out[c] = res[c];
}

// Classify one 8x8 image (pixels 0..16). Returns predicted digit 0..9.
int tt_classify(const uint8_t img[64]) {
    int8_t x[TT_IN_DIM];
    for (int i = 0; i < TT_IN_DIM; i++) x[i] = quant_px(img[i]);

    int8_t hidden[TT_HIDDEN];
    for (int r0 = 0; r0 < TT_HIDDEN; r0 += N) {
        int valid = (TT_HIDDEN - r0 < N) ? (TT_HIDDEN - r0) : N;
        int16_t bias_row[N] = {0};
        for (int c = 0; c < valid; c++) bias_row[c] = tt_b1[r0 + c];
        run_row_tile(tt_w1, TT_IN_DIM, r0, valid, TT_SHIFT1, 1 /*relu*/, bias_row, x, &hidden[r0]);
    }

    int8_t logits[TT_OUT_DIM];
    for (int r0 = 0; r0 < TT_OUT_DIM; r0 += N) {
        int valid = (TT_OUT_DIM - r0 < N) ? (TT_OUT_DIM - r0) : N;
        int16_t bias_row[N] = {0};
        for (int c = 0; c < valid; c++) bias_row[c] = tt_b2[r0 + c];
        run_row_tile(tt_w2, TT_HIDDEN, r0, valid, TT_SHIFT2, 0 /*no relu*/, bias_row, hidden, &logits[r0]);
    }

    int best = 0;
    for (int i = 1; i < TT_OUT_DIM; i++) if (logits[i] > logits[best]) best = i;
    return best;
}

int main(void) {
    tt_init();
    extern const uint8_t demo_image[64];             // supplied by host over UART, or a test ROM
    int digit = tt_classify(demo_image);
    printf("TensorTile MNIST: predicted digit = %d\n", digit);
    printf("perf: busy=%lu macs=%lu stall_act=%lu stall_bp=%lu\n",
           (unsigned long)tt_perf(0), (unsigned long)tt_perf(1),
           (unsigned long)tt_perf(2), (unsigned long)tt_perf(3));
    return 0;
}
