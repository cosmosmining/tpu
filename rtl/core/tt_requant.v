`default_nettype none
//
// tt_requant -- combinational requantization (SPEC s2): (acc + bias) -> round-half-up
// arithmetic shift -> saturate to INT8 (ReLU sets the lower bound to 0).
//
//   t = acc + (bias_en ? bias : 0)
//   r = (shift==0) ? t : (t + (1<<(shift-1))) >>> shift     (arithmetic, ties toward +inf)
//   y = clamp(r, relu_en ? 0 : -128, 127)
//
module tt_requant #(
    parameter integer ACC_W  = 24,
    parameter integer DATA_W = 8,
    parameter integer BIAS_W = 16
) (
    input  wire signed [ACC_W-1:0]  acc,
    input  wire signed [BIAS_W-1:0] bias,
    input  wire                     bias_en,
    input  wire [4:0]               shift,
    input  wire                     relu_en,
    output wire signed [DATA_W-1:0] y
);
    localparam integer RQ_W = ACC_W + BIAS_W;   // headroom for acc+bias and the round constant
    localparam signed [RQ_W-1:0] HI  =  127;
    localparam signed [RQ_W-1:0] LON = -128;

    wire signed [RQ_W-1:0] acc_ext  = {{(RQ_W-ACC_W){acc[ACC_W-1]}},  acc};
    wire signed [RQ_W-1:0] bias_ext = bias_en ? {{(RQ_W-BIAS_W){bias[BIAS_W-1]}}, bias}
                                              : {RQ_W{1'b0}};
    wire signed [RQ_W-1:0] t = acc_ext + bias_ext;

    wire signed [RQ_W-1:0] one = {{(RQ_W-1){1'b0}}, 1'b1};
    wire signed [RQ_W-1:0] round_const = (shift == 5'd0) ? {RQ_W{1'b0}} : (one << (shift - 5'd1));
    wire signed [RQ_W-1:0] r = (t + round_const) >>> shift;

    wire signed [RQ_W-1:0] LO = relu_en ? {RQ_W{1'b0}} : LON;
    assign y = (r > HI) ? 8'sd127 :
               (r < LO) ? (relu_en ? 8'sd0 : 8'sh80) :
                          r[DATA_W-1:0];
endmodule
`default_nettype wire
