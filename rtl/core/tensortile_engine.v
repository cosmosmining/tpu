`default_nettype none
//
// tensortile_engine -- descriptor command queue (P1) + tensortile_core.
//
// Wraps the verified core unchanged. A 4-deep FIFO (the proven tt_fifo) holds descriptors; a tiny
// controller issues them back-to-back: when the core is idle and the queue is non-empty it pops a
// descriptor and pulses `start`. The host enqueues descriptors via desc_wr/desc_data and supplies
// weights/activations on demand through the pass-through streaming ports (w_req/col_ready), exactly
// as for the bare core. This decouples descriptor submission from execution.
//
// Descriptor packing: [7:0]=num_cols [15:8]=num_k_tiles [20:16]=shift [21]=relu_en [22]=bias_en.
//
module tensortile_engine #(
    parameter integer ARRAY_N  = 4,
    parameter integer DATA_W   = 8,
    parameter integer ACC_W    = 24,
    parameter integer BIAS_W   = 16,
    parameter integer MAX_COLS = 8,
    parameter integer QDEPTH   = 4
) (
    input  wire                              clk,
    input  wire                              rst_n,
    // descriptor enqueue
    input  wire                              desc_wr,
    input  wire [22:0]                       desc_data,
    output wire                              desc_full,
    output wire [$clog2(QDEPTH+1)-1:0]       desc_occupancy,
    // weights / bias / activations / results (pass-through to the core)
    output wire                              w_req,
    input  wire                              w_load,
    input  wire [ARRAY_N*ARRAY_N*DATA_W-1:0] w_flat,
    input  wire                              b_load,
    input  wire [ARRAY_N*BIAS_W-1:0]         b_flat,
    input  wire                              col_valid,
    input  wire [ARRAY_N*DATA_W-1:0]         a_flat,
    output wire                              col_ready,
    output wire                              out_valid,
    output wire signed [DATA_W-1:0]          out_data,
    input  wire                              out_ready,
    // status + performance counters (from the core)
    output wire                              busy,        // core busy
    output wire                              done,        // 1-cycle pulse per finished descriptor
    output wire                              idle,        // engine idle: core idle AND queue empty
    output wire [31:0]                       perf_busy,
    output wire [31:0]                       perf_mac,
    output wire [31:0]                       perf_stall_act,
    output wire [31:0]                       perf_stall_bp
);
    // ---- descriptor FIFO (reuses the formally-proven tt_fifo) ------------------------------
    wire             q_empty;
    wire [22:0]      q_head;
    wire             core_busy, core_done;

    reg  c_run;                       // 0 = ready to issue, 1 = descriptor in flight
    wire start = (~c_run) & ~q_empty & ~core_busy;
    wire q_rd  = start;               // pop as we issue

    tt_fifo #(.WIDTH(23), .DEPTH(QDEPTH)) u_descq (
        .clk(clk), .rst_n(rst_n),
        .wr_en(desc_wr), .wr_data(desc_data), .full(desc_full),
        .rd_en(q_rd), .rd_data(q_head), .empty(q_empty), .count(desc_occupancy)
    );

    always @(posedge clk) begin
        if (!rst_n)      c_run <= 1'b0;
        else if (start)  c_run <= 1'b1;
        else if (core_done) c_run <= 1'b0;
    end

    assign busy = core_busy;
    assign done = core_done;
    assign idle = ~core_busy & q_empty;

    // ---- core (unchanged) ------------------------------------------------------------------
    tensortile_core #(.ARRAY_N(ARRAY_N), .DATA_W(DATA_W), .ACC_W(ACC_W),
                      .BIAS_W(BIAS_W), .MAX_COLS(MAX_COLS)) u_core (
        .clk(clk), .rst_n(rst_n), .start(start),
        .num_cols(q_head[7:0]), .num_k_tiles(q_head[15:8]), .shift(q_head[20:16]),
        .relu_en(q_head[21]), .bias_en(q_head[22]),
        .busy(core_busy), .done(core_done), .w_req(w_req),
        .w_load(w_load), .w_flat(w_flat), .b_load(b_load), .b_flat(b_flat),
        .col_valid(col_valid), .a_flat(a_flat), .col_ready(col_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .perf_busy(perf_busy), .perf_mac(perf_mac),
        .perf_stall_act(perf_stall_act), .perf_stall_bp(perf_stall_bp)
    );
endmodule
`default_nettype wire
