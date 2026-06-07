`default_nettype none
//
// fv_core -- formal harness for tensortile_core.
//
// yosys `sat` ignores $assume cells, so instead of assuming valid descriptors we constrain them
// STRUCTURALLY here: num_cols and num_k_tiles are derived to lie in [1..MAX_COLS] / [1..]. All
// other inputs are free. The safety assertions live inside tensortile_core (under `FORMAL) and are
// checked by `sat -prove-asserts` on this wrapper. (SymbiYosys can use the in-module assumes
// directly; this wrapper keeps the proof runnable with the bare `sat` engine — see DECISIONS.md.)
//
module fv_core (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [7:0]  cols_raw,
    input  wire [7:0]  kt_raw,
    input  wire [4:0]  shift,
    input  wire        relu_en,
    input  wire        bias_en,
    input  wire        w_load,
    input  wire [127:0] w_flat,   // ARRAY_N*ARRAY_N*DATA_W = 4*4*8
    input  wire        b_load,
    input  wire [63:0] b_flat,    // ARRAY_N*BIAS_W = 4*16
    input  wire        col_valid,
    input  wire [31:0] a_flat,    // ARRAY_N*DATA_W = 4*8
    input  wire        out_ready
);
    localparam integer N = 4, DW = 8, AW = 24, BW = 16, MC = 8;

    // structural input constraints: 1..MC columns, >=1 K-tiles
    wire [7:0] num_cols    = {5'b0, cols_raw[2:0]} + 8'd1;   // 1..8
    wire [7:0] num_k_tiles = {5'b0, kt_raw[2:0]}   + 8'd1;   // 1..8

    wire busy, done, w_req, col_ready, out_valid;
    wire signed [DW-1:0] out_data;

    tensortile_core #(.ARRAY_N(N), .DATA_W(DW), .ACC_W(AW), .BIAS_W(BW), .MAX_COLS(MC)) dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .num_cols(num_cols), .num_k_tiles(num_k_tiles), .shift(shift),
        .relu_en(relu_en), .bias_en(bias_en),
        .busy(busy), .done(done), .w_req(w_req),
        .w_load(w_load), .w_flat(w_flat), .b_load(b_load), .b_flat(b_flat),
        .col_valid(col_valid), .a_flat(a_flat), .col_ready(col_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready)
    );
endmodule
`default_nettype wire
