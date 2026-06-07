`default_nettype none
//
// tt_spi_host -- SPI-slave (mode 0) + CSR + streaming bridge to tensortile_engine.
//
// The system clock `clk` oversamples SCLK/CSn/MOSI (clk >> SCLK). Frames are MSB-first: the first
// byte after CSn falls is {rw, addr[6:0]}; subsequent bytes are write data (rw=0) or read data
// presented on MISO (rw=1). A long CSn-low burst to WDATA/ADATA/OUT moves many bytes. Byte buffers
// bridge the byte-wise CSR to the engine's per-cycle streaming (CSR map: regs/tensortile.rdl).
//
module tt_spi_host #(
    parameter integer ARRAY_N = 4,
    parameter integer DATA_W  = 8,
    parameter integer BIAS_W  = 16
) (
    input  wire clk,
    input  wire rst_n,
    input  wire sclk,
    input  wire csn,
    input  wire mosi,
    output wire miso,
    output wire irq,
    // engine interface (master)
    input  wire                              desc_full,
    output reg                               desc_wr,
    output reg  [22:0]                       desc_data,
    input  wire                              w_req,
    output reg                               w_load,
    output wire [ARRAY_N*ARRAY_N*DATA_W-1:0] w_flat,
    output reg                               b_load,
    output wire [ARRAY_N*BIAS_W-1:0]         b_flat,
    output wire                              col_valid,
    output wire [ARRAY_N*DATA_W-1:0]         a_flat,
    input  wire                              col_ready,
    input  wire                              out_valid,
    input  wire signed [DATA_W-1:0]          out_data,
    output wire                              out_ready,
    input  wire                              busy,
    input  wire                              idle,
    input  wire                              done_sticky
);
    localparam integer NW = ARRAY_N*ARRAY_N;
    localparam integer NB = ARRAY_N*2;
    localparam [6:0] A_STATUS=7'h01, A_DNC=7'h02, A_DNK=7'h03, A_DCF=7'h04,
                     A_WDATA=7'h05, A_ADATA=7'h06, A_OUT=7'h07, A_BDATA=7'h08;

    // ---- SPI sync + edge detect ------------------------------------------------------------
    reg [1:0] sclk_s, csn_s, mosi_s;
    reg       sclk_q;
    always @(posedge clk) begin
        sclk_s<={sclk_s[0],sclk}; csn_s<={csn_s[0],csn}; mosi_s<={mosi_s[0],mosi};
        sclk_q<=sclk_s[1];
    end
    wire active   = ~csn_s[1];
    wire rise     = active &  sclk_s[1] & ~sclk_q;
    wire mosi_now = mosi_s[1];

    // ---- frame state -----------------------------------------------------------------------
    reg [2:0] bitcnt;
    reg       header, rw;
    reg [6:0] addr;
    reg [6:0] shin;
    reg [7:0] rdbyte, d_nc, d_nk;
    wire [7:0] rx_byte = {shin, mosi_now};

    // ---- weight / bias / activation buffers ------------------------------------------------
    reg [7:0] wbuf [0:NW-1];
    reg [7:0] bbuf [0:NB-1];
    reg [7:0] acol [0:ARRAY_N-1];
    reg [7:0] wcnt, bcnt, acnt;
    reg       w_full, a_push;
    genvar gi;
    generate
        for (gi=0; gi<NW; gi=gi+1) assign w_flat[gi*DATA_W +: DATA_W] = wbuf[gi];
        for (gi=0; gi<NB; gi=gi+1) assign b_flat[gi*8 +: 8] = bbuf[gi];
    endgenerate
    wire [ARRAY_N*DATA_W-1:0] acol_flat;
    generate for (gi=0; gi<ARRAY_N; gi=gi+1) assign acol_flat[gi*DATA_W +: DATA_W]=acol[gi]; endgenerate

    wire act_empty, act_full;
    wire a_pop = col_ready & ~act_empty;
    /* verilator lint_off PINMISSING */
    tt_fifo #(.WIDTH(ARRAY_N*DATA_W), .DEPTH(8)) u_actfifo (
        .clk(clk), .rst_n(rst_n), .wr_en(a_push & ~act_full), .wr_data(acol_flat),
        .full(act_full), .rd_en(a_pop), .rd_data(a_flat), .empty(act_empty));
    wire out_empty, out_full;
    wire [DATA_W-1:0] out_head;
    reg  out_pop;
    tt_fifo #(.WIDTH(DATA_W), .DEPTH(16)) u_outfifo (
        .clk(clk), .rst_n(rst_n), .wr_en(out_valid & ~out_full), .wr_data(out_data),
        .full(out_full), .rd_en(out_pop), .rd_data(out_head), .empty(out_empty));
    /* verilator lint_on PINMISSING */
    assign col_valid = ~act_empty;
    assign out_ready = ~out_full;

    wire [7:0] status_byte = {3'b0, desc_full, ~out_empty, done_sticky, idle, busy};
    function [7:0] rd_csr(input [6:0] a);
        rd_csr = (a==A_STATUS) ? status_byte : (a==A_OUT) ? out_head : 8'h00;
    endfunction

    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            bitcnt<=0; header<=1; rw<=0; addr<=0; shin<=0; rdbyte<=0;
            d_nc<=0; d_nk<=0; wcnt<=0; bcnt<=0; acnt<=0; w_full<=0;
            desc_wr<=0; desc_data<=0; w_load<=0; b_load<=0; a_push<=0; out_pop<=0;
            for (i=0;i<NW;i=i+1) wbuf[i]<=0;
            for (i=0;i<NB;i=i+1) bbuf[i]<=0;
            for (i=0;i<ARRAY_N;i=i+1) acol[i]<=0;
        end else begin
            desc_wr<=0; w_load<=0; b_load<=0; a_push<=0; out_pop<=0;

            if (w_req & w_full) begin w_load<=1'b1; w_full<=1'b0; wcnt<=8'd0; end

            if (~active) begin
                bitcnt<=0; header<=1;
            end else if (rise) begin
                shin <= {shin[5:0], mosi_now};
                if (bitcnt==3'd7) begin
                    bitcnt<=3'd0;
                    if (header) begin
                        addr<=rx_byte[6:0]; rw<=rx_byte[7]; header<=1'b0;
                        if (rx_byte[7]) begin
                            rdbyte <= rd_csr(rx_byte[6:0]);
                            if (rx_byte[6:0]==A_OUT) out_pop <= ~out_empty;
                        end
                    end else if (~rw) begin
                        case (addr)
                            A_DNC: d_nc<=rx_byte;
                            A_DNK: d_nk<=rx_byte;
                            A_DCF: begin
                                desc_data <= {rx_byte[6], rx_byte[5], rx_byte[4:0], d_nk, d_nc};
                                desc_wr   <= ~desc_full;
                            end
                            A_WDATA: begin
                                wbuf[wcnt[$clog2(NW)-1:0]] <= rx_byte;
                                if (wcnt==8'(NW-1)) begin wcnt<=0; w_full<=1'b1; end else wcnt<=wcnt+8'd1;
                            end
                            A_BDATA: begin
                                bbuf[bcnt[$clog2(NB)-1:0]] <= rx_byte;
                                if (bcnt==8'(NB-1)) begin bcnt<=0; b_load<=1'b1; end else bcnt<=bcnt+8'd1;
                            end
                            A_ADATA: begin
                                acol[acnt[$clog2(ARRAY_N)-1:0]] <= rx_byte;
                                if (acnt==8'(ARRAY_N-1)) begin acnt<=0; a_push<=1'b1; end else acnt<=acnt+8'd1;
                            end
                            default: ;
                        endcase
                    end else begin   // read: byte boundary -> preload next
                        rdbyte <= rd_csr(addr);
                        if (addr==A_OUT) out_pop <= ~out_empty;
                    end
                end else begin
                    bitcnt <= bitcnt + 3'd1;
                end
            end
        end
    end

    assign miso = (active & rw & ~header) ? rdbyte[3'd7 - bitcnt] : 1'b0;
    assign irq  = done_sticky;
endmodule
`default_nettype wire
