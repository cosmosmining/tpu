// tensortile.c -- TensorTile RP2040 driver implementation (over the SPI->CSR interface).
#include "tensortile.h"

#define N TT_ARRAY_N

void tt_init(void) {
    tt_hal_init();
    tt_wr8(TT_CTRL, 0x01);   // soft reset
    tt_wr8(TT_CTRL, 0x00);
}

void tt_enqueue(uint8_t num_cols, uint8_t num_k_tiles, uint8_t shift, int relu, int bias_en) {
    tt_wr8(TT_DESC_NC, num_cols);
    tt_wr8(TT_DESC_NK, num_k_tiles);
    uint8_t cf = (shift & 0x1F) | (relu ? 0x20 : 0) | (bias_en ? 0x40 : 0);
    tt_wr8(TT_DESC_CF, cf);   // commit/enqueue
}

void tt_load_bias(const int16_t *bias, int n) {
    for (int i = 0; i < n; i++) {
        tt_wr8(TT_BDATA, (uint8_t)(bias[i] & 0xFF));
        tt_wr8(TT_BDATA, (uint8_t)((bias[i] >> 8) & 0xFF));
    }
}

void tt_push_weight_tile(const int8_t *wflat_kc) {
    for (int i = 0; i < N * N; i++) tt_wr8(TT_WDATA, (uint8_t)wflat_kc[i]);
}

void tt_push_act_col(const int8_t *col) {
    for (int k = 0; k < N; k++) tt_wr8(TT_ADATA, (uint8_t)col[k]);
}

void tt_read_results(int8_t *out, int count) {
    for (int i = 0; i < count; i++) out[i] = (int8_t)tt_rd8(TT_OUT);
}

uint32_t tt_perf(int idx) {
    uint8_t b[4];
    tt_hal_read((uint8_t)(TT_PERF + idx * 4), b, 4);
    return (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
}

void tt_run_tile(uint8_t num_cols, uint8_t num_k_tiles, uint8_t shift, int relu,
                 const int16_t *bias_or_null,
                 const int8_t *wtiles_kc, const int8_t *acts_kc, int8_t *out) {
    if (bias_or_null) tt_load_bias(bias_or_null, N);
    tt_enqueue(num_cols, num_k_tiles, shift, relu, bias_or_null != 0);
    for (int kt = 0; kt < num_k_tiles; kt++) {
        // weights for this K-tile: (ARRAY_N*ARRAY_N) bytes in (k*N + c) order
        tt_push_weight_tile(wtiles_kc + kt * (N * N));
        // activation columns for this K-tile: num_cols columns of N bytes (col-major)
        for (int m = 0; m < num_cols; m++)
            tt_push_act_col(acts_kc + kt * (N * num_cols) + m * N);
    }
    tt_read_results(out, N * num_cols);
}
