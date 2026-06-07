// tensortile.h -- RP2040 host driver for the TensorTile accelerator (SPI -> CSR).
// Targets the CSR map in docs/INTEGRATION.md. HW-untested pending the SPI/CSR top + silicon
// bring-up; the demo logic mirrors the verified dv/cocotb/tb_mnist flow.
#ifndef TENSORTILE_H
#define TENSORTILE_H
#include <stdint.h>

#define TT_ARRAY_N 4

// CSR map (7-bit addr; SPI frame = {R/W, addr[6:0]} then data byte(s))
enum {
    TT_CTRL    = 0x00,  // [0]=soft_reset [1]=irq_en [7]=test_en
    TT_STATUS  = 0x01,  // [0]=busy [1]=idle [2]=done [3]=out_valid [4]=desc_full
    TT_DESC_NC = 0x02,  // num_cols
    TT_DESC_NK = 0x03,  // num_k_tiles
    TT_DESC_CF = 0x04,  // {bias_en[6],relu_en[5],shift[4:0]} -- write commits/enqueues descriptor
    TT_WDATA   = 0x05,  // push a weight byte (bridge loads the N*N tile on w_req)
    TT_ADATA   = 0x06,  // push an activation byte (one column = N bytes)
    TT_OUT     = 0x07,  // read a result byte (INT8)
    TT_BDATA   = 0x08,  // push a bias byte (N * 2 bytes, little-endian int16)
    TT_PERF    = 0x10,  // 0x10..0x1F: 4 x uint32 perf counters (busy,mac,stall_act,stall_bp)
};

// --- SPI HAL (provided by the platform: pico-sdk hardware/spi.h, or a mock for tests) ---
void tt_hal_init(void);
void tt_hal_write(uint8_t addr, const uint8_t *data, uint32_t n);
void tt_hal_read(uint8_t addr, uint8_t *data, uint32_t n);

// --- register helpers ---
static inline void tt_wr8(uint8_t a, uint8_t v) { tt_hal_write(a, &v, 1); }
static inline uint8_t tt_rd8(uint8_t a) { uint8_t v; tt_hal_read(a, &v, 1); return v; }

// --- driver API ---
void tt_init(void);
void tt_enqueue(uint8_t num_cols, uint8_t num_k_tiles, uint8_t shift, int relu, int bias_en);
void tt_load_bias(const int16_t *bias, int n);            // n biases (<= ARRAY_N)
void tt_push_weight_tile(const int8_t *wflat_kc);         // ARRAY_N*ARRAY_N bytes, (k*N + c) order
void tt_push_act_col(const int8_t *col);                  // ARRAY_N bytes
void tt_read_results(int8_t *out, int count);
uint32_t tt_perf(int idx);                                // 0=busy 1=mac 2=stall_act 3=stall_bp

// Run a GEMM tile (one output row-tile, K-tiled). Caller supplies the per-K-tile weight tiles
// (wflat_kc, ARRAY_N*ARRAY_N each) and activation columns. Returns ARRAY_N*num_cols results.
void tt_run_tile(uint8_t num_cols, uint8_t num_k_tiles, uint8_t shift, int relu,
                 const int16_t *bias_or_null,
                 const int8_t *wtiles_kc,   // num_k_tiles * (ARRAY_N*ARRAY_N)
                 const int8_t *acts_kc,     // num_k_tiles * (ARRAY_N*num_cols), col-major per tile
                 int8_t *out);              // ARRAY_N*num_cols

#endif
