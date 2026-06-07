`default_nettype none
//
// tt_fifo -- synchronous first-word-fall-through FIFO (flops only, depth <= 16).
// Single clock. Write when (wr_en & !full); read/advance when (rd_en & !empty).
// rd_data continuously presents the head word (valid when !empty).
//
module tt_fifo #(
    parameter integer WIDTH = 8,
    parameter integer DEPTH = 8
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             wr_en,
    input  wire [WIDTH-1:0] wr_data,
    output wire             full,
    input  wire             rd_en,
    output wire [WIDTH-1:0] rd_data,
    output wire             empty,
    output reg  [$clog2(DEPTH+1)-1:0] count
);
    localparam integer CNT_W = $clog2(DEPTH + 1);
    localparam integer PTR_W = (DEPTH <= 1) ? 1 : $clog2(DEPTH);

    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [PTR_W-1:0] wr_ptr, rd_ptr;

    assign empty   = (count == {CNT_W{1'b0}});
    assign full    = (count == DEPTH[CNT_W-1:0]);
    assign rd_data = mem[rd_ptr];

    wire do_wr = wr_en & ~full;
    wire do_rd = rd_en & ~empty;

    localparam [PTR_W-1:0] LASTP = DEPTH[PTR_W-1:0] - 1'b1;
    function [PTR_W-1:0] incp(input [PTR_W-1:0] p);
        incp = (p == LASTP) ? {PTR_W{1'b0}} : (p + 1'b1);
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= {PTR_W{1'b0}};
            rd_ptr <= {PTR_W{1'b0}};
            count  <= {CNT_W{1'b0}};
        end else begin
            if (do_wr) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr <= incp(wr_ptr);
            end
            if (do_rd) rd_ptr <= incp(rd_ptr);
            case ({do_wr, do_rd})
                2'b10:   count <= count + 1'b1;
                2'b01:   count <= count - 1'b1;
                default: count <= count;   // 00 or 11: unchanged
            endcase
        end
    end
endmodule
`default_nettype wire
