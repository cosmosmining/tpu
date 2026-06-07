`default_nettype none
//
// tt_mac_array -- ARRAY_N x ARRAY_N weight-stationary systolic MAC array.
//
// Holds an N x N weight tile (wmem[k][c], k = contraction row, c = output column). Activation
// columns are presented one per cycle on a_col (element k on lane k); lane k is internally skewed
// by k cycles so that, as partial sums flow DOWN each column (registered, 1 cycle/row), the
// product w[k][c]*a[k] aligns with the descending partial sum. After a fill latency of ARRAY_N
// cycles, s_out[c] = sum_k wmem[k][c]*a[k] for the presented column -- one result column/cycle.
//
//   Mapping: to compute acc[n,m] = sum_k W[n,k]*A[k,m], load wmem[k][n] = W[n,k] (W transposed),
//   present a_col[k] = A[k,m]; then s_out[n] = acc[n,m].  (See model/gemm_ref.matmul_acc.)
//
// Ports use flattened vectors (SV unpacked-array ports are avoided for iverilog portability).
//
module tt_mac_array #(
    parameter integer ARRAY_N = 4,
    parameter integer DATA_W  = 8,
    parameter integer ACC_W   = 24
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          en,        // advance the array one column-step
    // weight load: parallel load of the whole tile (shift-chain serialization is a load-path
    // concern handled in the core/wrapper). wmem[k][c] = w_flat[(k*ARRAY_N + c)*DATA_W +: DATA_W]
    input  wire                          w_load,
    input  wire [ARRAY_N*ARRAY_N*DATA_W-1:0] w_flat,
    // activation column in: a_col[k] = a_flat[k*DATA_W +: DATA_W]
    input  wire                          in_valid,
    input  wire [ARRAY_N*DATA_W-1:0]     a_flat,
    // results out: s_out[c] = s_flat[c*ACC_W +: ACC_W], valid out_valid (ARRAY_N cycles later)
    output wire                          out_valid,
    output wire [ARRAY_N*ACC_W-1:0]      s_flat
);
    genvar k, c;

    // ---- stationary weight memory ----------------------------------------------------------
    reg signed [DATA_W-1:0] wmem [0:ARRAY_N-1][0:ARRAY_N-1];
    integer ik, ic;
    always @(posedge clk) begin
        if (!rst_n) begin
            for (ik = 0; ik < ARRAY_N; ik = ik + 1)
                for (ic = 0; ic < ARRAY_N; ic = ic + 1)
                    wmem[ik][ic] <= {DATA_W{1'b0}};
        end else if (w_load) begin
            for (ik = 0; ik < ARRAY_N; ik = ik + 1)
                for (ic = 0; ic < ARRAY_N; ic = ic + 1)
                    wmem[ik][ic] <= w_flat[(ik*ARRAY_N + ic)*DATA_W +: DATA_W];
        end
    end

    // ---- per-row activation skew: lane k delayed by k cycles -------------------------------
    wire signed [DATA_W-1:0] a_row [0:ARRAY_N-1];
    generate
        for (k = 0; k < ARRAY_N; k = k + 1) begin: gen_skew
            wire signed [DATA_W-1:0] a_lane = a_flat[k*DATA_W +: DATA_W];
            if (k == 0) begin: g_nodelay
                assign a_row[0] = a_lane;
            end else begin: g_delay
                reg signed [DATA_W-1:0] sr [0:k-1];
                integer d;
                always @(posedge clk) begin
                    if (!rst_n) begin
                        for (d = 0; d < k; d = d + 1) sr[d] <= {DATA_W{1'b0}};
                    end else if (en) begin
                        sr[0] <= a_lane;
                        for (d = 1; d < k; d = d + 1) sr[d] <= sr[d-1];
                    end
                end
                assign a_row[k] = sr[k-1];
            end
        end
    endgenerate

    // ---- PE grid: psum flows down each column ---------------------------------------------
    // psum_chain[c][k] = partial sum entering row k of column c; row 0 entry is 0.
    wire signed [ACC_W-1:0] psum_chain [0:ARRAY_N-1][0:ARRAY_N];
    generate
        for (c = 0; c < ARRAY_N; c = c + 1) begin: gen_col
            assign psum_chain[c][0] = {ACC_W{1'b0}};
            for (k = 0; k < ARRAY_N; k = k + 1) begin: gen_row
                tt_pe #(.DATA_W(DATA_W), .ACC_W(ACC_W)) pe (
                    .clk(clk), .rst_n(rst_n), .en(en),
                    .w(wmem[k][c]), .a_in(a_row[k]),
                    .psum_in(psum_chain[c][k]),
                    .psum_out(psum_chain[c][k+1])
                );
            end
            assign s_flat[c*ACC_W +: ACC_W] = psum_chain[c][ARRAY_N];
        end
    endgenerate

    // ---- valid pipeline: in_valid -> out_valid after ARRAY_N cycles ------------------------
    reg [ARRAY_N-1:0] vpipe;
    always @(posedge clk) begin
        if (!rst_n)      vpipe <= {ARRAY_N{1'b0}};
        else if (en)     vpipe <= {vpipe[ARRAY_N-2:0], in_valid};
    end
    assign out_valid = vpipe[ARRAY_N-1];
endmodule
`default_nettype wire
