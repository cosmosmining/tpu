`default_nettype none
//
// tensortile_core -- weight-stationary INT8 systolic GEMM tile engine.
//
// Drives the host tiling protocol (SPEC s5) for one descriptor: produces an ARRAY_N x num_cols
// output tile, accumulated over num_k_tiles K-tiles, then bias + requant + ReLU to the output
// stream. Direct streaming interface (the SPI->APB->CSR wrapper and I/O FIFOs sit above this).
//
// Per K-tile the host: pulses w_load with the N x N weight tile (wmem[k][c] = W[c][k]), then
// streams num_cols activation columns (col_valid/a_flat). Results from tt_mac_array are
// accumulated into ACC[c][col] (cleared on the first K-tile). After the last K-tile the engine
// drains ACC through tt_requant in column order -> out stream.
//
// Output order: outer = column (0..num_cols-1), inner = row c (0..ARRAY_N-1).
//
module tensortile_core #(
    parameter integer ARRAY_N  = 4,
    parameter integer DATA_W   = 8,
    parameter integer ACC_W    = 24,
    parameter integer BIAS_W   = 16,
    parameter integer MAX_COLS = 8
) (
    input  wire                              clk,
    input  wire                              rst_n,
    // descriptor (latched on start)
    input  wire                              start,
    input  wire [7:0]                        num_cols,     // 1..MAX_COLS
    input  wire [7:0]                        num_k_tiles,  // >= 1
    input  wire [4:0]                        shift,
    input  wire                              relu_en,
    input  wire                              bias_en,
    output wire                              busy,
    output reg                               done,
    output wire                              w_req,        // high when awaiting a K-tile's weights
    // weight tile load (parallel, once per K-tile)
    input  wire                              w_load,
    input  wire [ARRAY_N*ARRAY_N*DATA_W-1:0] w_flat,
    // bias load (N biases, once)
    input  wire                              b_load,
    input  wire [ARRAY_N*BIAS_W-1:0]         b_flat,
    // activation column stream
    input  wire                              col_valid,
    input  wire [ARRAY_N*DATA_W-1:0]         a_flat,
    output wire                              col_ready,
    // result stream (INT8)
    output wire                              out_valid,
    output wire signed [DATA_W-1:0]          out_data,
    input  wire                              out_ready
);
    localparam [2:0] S_IDLE=3'd0, S_LOADW=3'd1, S_STREAM=3'd2, S_DRAIN=3'd3, S_DONE=3'd4;
    localparam integer RIDX = (ARRAY_N  <= 1) ? 1 : $clog2(ARRAY_N);
    localparam integer CIDX = (MAX_COLS <= 1) ? 1 : $clog2(MAX_COLS);

    reg [2:0] state;
    reg [7:0] d_cols, d_ktiles, kt, cin, cout, dcol, drow;
    reg [4:0] d_shift;
    reg       d_relu, d_bias;

    reg signed [ACC_W-1:0]  acc_buf [0:ARRAY_N-1][0:MAX_COLS-1];
    reg signed [BIAS_W-1:0] bias_rf [0:ARRAY_N-1];
    integer ic;

    // ---- array instance --------------------------------------------------------------------
    wire                     arr_en     = (state == S_STREAM);
    wire                     feed       = (state == S_STREAM) && col_valid && (cin < d_cols);
    wire                     arr_w_load = w_load && (state == S_LOADW);
    wire                     arr_outv;
    wire [ARRAY_N*ACC_W-1:0] arr_s_flat;

    tt_mac_array #(.ARRAY_N(ARRAY_N), .DATA_W(DATA_W), .ACC_W(ACC_W)) u_array (
        .clk(clk), .rst_n(rst_n), .en(arr_en),
        .w_load(arr_w_load), .w_flat(w_flat),
        .in_valid(feed), .a_flat(a_flat),
        .out_valid(arr_outv), .s_flat(arr_s_flat)
    );

    assign busy      = (state != S_IDLE);
    assign w_req     = (state == S_LOADW);
    assign col_ready = (state == S_STREAM) && (cin < d_cols);

    // ---- drain requant (combinational data/valid; index advances on handshake) -------------
    wire signed [ACC_W-1:0]  drain_acc  = acc_buf[drow[RIDX-1:0]][dcol[CIDX-1:0]];
    wire signed [BIAS_W-1:0] drain_bias = bias_rf[drow[RIDX-1:0]];
    tt_requant #(.ACC_W(ACC_W), .DATA_W(DATA_W), .BIAS_W(BIAS_W)) u_rq (
        .acc(drain_acc), .bias(drain_bias), .bias_en(d_bias),
        .shift(d_shift), .relu_en(d_relu), .y(out_data)
    );
    assign out_valid = (state == S_DRAIN);

    // ---- bias load -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            for (ic = 0; ic < ARRAY_N; ic = ic + 1) bias_rf[ic] <= {BIAS_W{1'b0}};
        end else if (b_load) begin
            for (ic = 0; ic < ARRAY_N; ic = ic + 1) bias_rf[ic] <= b_flat[ic*BIAS_W +: BIAS_W];
        end
    end

    // ---- main FSM --------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE; done <= 1'b0;
            kt <= 8'd0; cin <= 8'd0; cout <= 8'd0; dcol <= 8'd0; drow <= 8'd0;
            d_cols <= 8'd0; d_ktiles <= 8'd0; d_shift <= 5'd0; d_relu <= 1'b0; d_bias <= 1'b0;
        end else begin
            done <= 1'b0;
            case (state)
                S_IDLE: if (start) begin
                    d_cols   <= num_cols;   d_ktiles <= num_k_tiles;
                    d_shift  <= shift;      d_relu   <= relu_en;   d_bias <= bias_en;
                    kt <= 8'd0; cin <= 8'd0; cout <= 8'd0;
                    state <= S_LOADW;
                end

                S_LOADW: begin
                    cin <= 8'd0; cout <= 8'd0;
                    if (arr_w_load) state <= S_STREAM;
                end

                S_STREAM: begin
                    if (feed) cin <= cin + 8'd1;
                    if (arr_outv) begin
                        for (ic = 0; ic < ARRAY_N; ic = ic + 1) begin
                            if (kt == 8'd0)
                                acc_buf[ic][cout[CIDX-1:0]] <= arr_s_flat[ic*ACC_W +: ACC_W];
                            else
                                acc_buf[ic][cout[CIDX-1:0]] <=
                                    acc_buf[ic][cout[CIDX-1:0]] + arr_s_flat[ic*ACC_W +: ACC_W];
                        end
                        cout <= cout + 8'd1;
                        if (cout + 8'd1 == d_cols) begin
                            if (kt + 8'd1 == d_ktiles) begin
                                state <= S_DRAIN; dcol <= 8'd0; drow <= 8'd0;
                            end else begin
                                kt <= kt + 8'd1; state <= S_LOADW;
                            end
                        end
                    end
                end

                S_DRAIN: if (out_ready) begin
                    if (drow + 8'd1 == ARRAY_N[7:0]) begin
                        drow <= 8'd0;
                        if (dcol + 8'd1 == d_cols) state <= S_DONE;
                        else dcol <= dcol + 8'd1;
                    end else drow <= drow + 8'd1;
                end

                S_DONE: begin done <= 1'b1; state <= S_IDLE; end
                default: state <= S_IDLE;
            endcase
        end
    end

`ifdef FORMAL
    // Control-FSM + accumulator-safety properties (see dv/formal/). The host always programs valid
    // descriptors (clocked input constraint, sampled at every edge):
    localparam [7:0] MAXCOLS8 = MAX_COLS[7:0];
    always @(posedge clk) begin
        assume (num_cols >= 8'd1);
        assume (num_cols <= MAXCOLS8);
        assume (num_k_tiles >= 8'd1);
    end
    always @(posedge clk) if (rst_n) begin
        assert (state <= S_DONE);                       // FSM never enters an illegal state
        assert (d_cols <= MAX_COLS[7:0]);               // latched column count fits the buffer
        assert (drow < ARRAY_N[7:0]);                   // accumulator row index always in range
        // While streaming, the accumulate write index cout < d_cols (<= MAX_COLS); the cycle cout
        // reaches d_cols the FSM leaves S_STREAM, so the acc-buffer write index is always in range.
        if (state == S_STREAM) assert (cout < d_cols);
        // While draining, the read index dcol < d_cols (<= MAX_COLS) -> in range; and out_valid is
        // asserted only here, so accumulator reads and writes never occur in the same cycle (no
        // write-conflict / read-during-write).
        if (state == S_DRAIN) assert (dcol < d_cols);
        assert (out_valid == (state == S_DRAIN));       // outputs strictly confined to the drain phase
    end
`endif
endmodule
`default_nettype wire
