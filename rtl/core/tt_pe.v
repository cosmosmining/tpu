`default_nettype none
//
// tt_pe -- TensorTile processing element (weight-stationary INT8 MAC).
//
// Registered partial-sum pass-down:  psum_out <= psum_in + (w * a_in).
// The product (2*DATA_W bits) is sign-extended to ACC_W before the add. The top row of the
// array drives psum_in = 0; each row registers its partial sum for the row below (systolic).
//
module tt_pe #(
    parameter integer DATA_W = 8,
    parameter integer ACC_W  = 24
) (
    input  wire                       clk,
    input  wire                       rst_n,   // sync active-low
    input  wire                       en,      // advance the pipeline
    input  wire signed [DATA_W-1:0]   w,       // stationary weight (held by the array)
    input  wire signed [DATA_W-1:0]   a_in,    // activation for this row (skewed upstream)
    input  wire signed [ACC_W-1:0]    psum_in, // partial sum from the row above
    output reg  signed [ACC_W-1:0]    psum_out // partial sum to the row below (registered)
);
    wire signed [2*DATA_W-1:0] prod = w * a_in;              // exact INT8xINT8 product
    // explicit sign-extension to ACC_W (width-matched; requires ACC_W >= 2*DATA_W)
    wire signed [ACC_W-1:0]    prod_ext =
        {{(ACC_W-2*DATA_W){prod[2*DATA_W-1]}}, prod};

    always @(posedge clk) begin
        if (!rst_n)      psum_out <= {ACC_W{1'b0}};
        else if (en)     psum_out <= psum_in + prod_ext;
    end
endmodule
`default_nettype wire
