`default_nettype none
//
// tt_um_tensortile -- Tiny Tapeout top wrapper for the TensorTile accelerator.
//
// PHASE-0 SCAFFOLD STUB: TT pin interface + top-level parameters only, with NO
// functional datapath. It drives a safe reset state (zeros; bidir pins as inputs)
// so that the toolchain (iverilog/verilator) and the pin interface are locked in
// and `make smoke` / `make lint` exercise the real flow. This module is replaced
// by the real core wrapper in Phase 2, after docs/SPEC.md is frozen and approved.
// See DECISIONS.md (2026-06-07). Engineering standard #1 (no design RTL before
// spec) is respected: there is intentionally no arithmetic here.
//
module tt_um_tensortile #(
    parameter integer ARRAY_N = 4,   // systolic array dimension (N x N PEs)
    parameter integer DATA_W  = 8,   // operand width (INT8)
    parameter integer ACC_W   = 24   // accumulator width (signed)
) (
    input  wire [7:0] ui_in,    // dedicated inputs
    output wire [7:0] uo_out,   // dedicated outputs
    input  wire [7:0] uio_in,   // IO inputs
    output wire [7:0] uio_out,  // IO outputs
    output wire [7:0] uio_oe,   // IO output-enable (1 = drive out)
    input  wire       ena,      // always 1 when the design is powered/selected
    input  wire       clk,      // single clock from the TT harness
    input  wire       rst_n     // synchronous active-low reset
);

    // Sequential + reset-clean heartbeat so clk/rst_n are genuinely exercised
    // (no latches, synchronous active-low reset, single clock domain).
    reg heartbeat;
    always @(posedge clk) begin
        if (!rst_n) heartbeat <= 1'b0;
        else        heartbeat <= 1'b0;   // held low: no functionality yet
    end

    // Safe reset state on all outputs.
    assign uo_out  = {7'b0, heartbeat};
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;               // all bidir pins are inputs in Phase 0

    // Reference the top-level parameters and sink currently-unused inputs so the
    // stub is lint-clean. All of these become real signals/sizing in Phase 2.
    localparam [31:0] NMACS = ARRAY_N * ARRAY_N;
    wire [ACC_W-1:0]  acc_zero = {ACC_W{1'b0}};
    wire [DATA_W-1:0] dat_zero = {DATA_W{1'b0}};
    wire [31:0]       nmacs_w  = NMACS;
    wire _unused = &{ena, ui_in, uio_in, acc_zero, dat_zero, nmacs_w, 1'b0};

endmodule
`default_nettype wire
