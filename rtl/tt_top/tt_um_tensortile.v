`default_nettype none
//
// tt_um_tensortile -- Tiny Tapeout top for the TensorTile INT8 systolic GEMM accelerator.
//
// SPI-slave host (ui_in[2:0] = SCLK/CSn/MOSI) -> CSR/streaming bridge (tt_spi_host) ->
// descriptor queue + core (tensortile_engine). Outputs: uo_out[0]=MISO, [1]=IRQ, [2]=busy,
// [3]=done. Pin map per docs/SPEC.md §8 / docs/INTEGRATION.md. Single clock; the design
// oversamples SCLK (clk >> SCLK). uio reserved (inputs) in normal mode; scan muxing (Phase 6)
// goes under a test_en CSR bit.
//
module tt_um_tensortile #(
    parameter integer ARRAY_N  = 4,
    parameter integer DATA_W   = 8,
    parameter integer ACC_W    = 24,
    parameter integer BIAS_W   = 16,
    parameter integer MAX_COLS = 8,
    parameter integer QDEPTH   = 4
) (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    // ---- engine <-> bridge nets ------------------------------------------------------------
    wire                              desc_full, desc_wr;
    wire [22:0]                       desc_data;
    wire                              w_req, w_load;
    wire [ARRAY_N*ARRAY_N*DATA_W-1:0] w_flat;
    wire                              b_load;
    wire [ARRAY_N*BIAS_W-1:0]         b_flat;
    wire                              col_valid, col_ready;
    wire [ARRAY_N*DATA_W-1:0]         a_flat;
    wire                              out_valid, out_ready;
    wire signed [DATA_W-1:0]          out_data;
    wire                              busy, done, idle;
    wire [31:0]                       perf_busy, perf_mac, perf_stall_act, perf_stall_bp;

    // ---- done sticky (set on a finished descriptor, cleared when a new one is enqueued) -----
    reg done_sticky;
    always @(posedge clk) begin
        if (!rst_n)        done_sticky <= 1'b0;
        else if (done)     done_sticky <= 1'b1;
        else if (desc_wr)  done_sticky <= 1'b0;
    end

    // ---- SPI host / CSR / streaming bridge -------------------------------------------------
    tt_spi_host #(.ARRAY_N(ARRAY_N), .DATA_W(DATA_W), .BIAS_W(BIAS_W)) u_host (
        .clk(clk), .rst_n(rst_n),
        .sclk(ui_in[0]), .csn(ui_in[1]), .mosi(ui_in[2]), .miso(uo_out[0]), .irq(uo_out[1]),
        .desc_full(desc_full), .desc_wr(desc_wr), .desc_data(desc_data),
        .w_req(w_req), .w_load(w_load), .w_flat(w_flat),
        .b_load(b_load), .b_flat(b_flat),
        .col_valid(col_valid), .a_flat(a_flat), .col_ready(col_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .busy(busy), .idle(idle), .done_sticky(done_sticky)
    );

    // ---- descriptor queue + core (queue lives inside the engine) ---------------------------
    /* verilator lint_off PINMISSING */
    tensortile_engine #(.ARRAY_N(ARRAY_N), .DATA_W(DATA_W), .ACC_W(ACC_W),
                        .BIAS_W(BIAS_W), .MAX_COLS(MAX_COLS), .QDEPTH(QDEPTH)) u_engine (
        .clk(clk), .rst_n(rst_n),
        .desc_wr(desc_wr), .desc_data(desc_data), .desc_full(desc_full),
        .w_req(w_req), .w_load(w_load), .w_flat(w_flat),
        .b_load(b_load), .b_flat(b_flat),
        .col_valid(col_valid), .a_flat(a_flat), .col_ready(col_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .busy(busy), .done(done), .idle(idle),
        .perf_busy(perf_busy), .perf_mac(perf_mac),
        .perf_stall_act(perf_stall_act), .perf_stall_bp(perf_stall_bp)
    );
    /* verilator lint_on PINMISSING */

    // ---- output pins -----------------------------------------------------------------------
    assign uo_out[2] = busy;
    assign uo_out[3] = done_sticky;
    assign uo_out[7:4] = 4'b0;
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;   // bidir pins are inputs in normal mode

    // sink unused inputs (perf counters surface via CSR in a later revision)
    wire _unused = &{ena, ui_in[7:3], uio_in,
                     perf_busy, perf_mac, perf_stall_act, perf_stall_bp, 1'b0};
endmodule
`default_nettype wire
