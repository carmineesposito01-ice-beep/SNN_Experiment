`timescale 1 ns / 1 ps
// AXI4-Lite slave per snn_top_b2 (SNN Donatello B2 + decode). Protocollo dal template Vivado.
// Mappa registri: W 0x00-0x0C = xn0..3 (Q5.13, 19b); W 0x10 = control (bit0=start pulse);
//                 R 0x10 = status (bit0=done); R 0x14-0x24 = params0..4 (Q7.13, sign-ext 32b).
module snn_b2_axi_lite #
(
  parameter integer C_S_AXI_DATA_WIDTH = 32,
  parameter integer C_S_AXI_ADDR_WIDTH = 6
)
(
  input  wire S_AXI_ACLK,
  input  wire S_AXI_ARESETN,
  input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_AWADDR,
  input  wire [2:0] S_AXI_AWPROT,
  input  wire S_AXI_AWVALID,
  output wire S_AXI_AWREADY,
  input  wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_WDATA,
  input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
  input  wire S_AXI_WVALID,
  output wire S_AXI_WREADY,
  output wire [1:0] S_AXI_BRESP,
  output wire S_AXI_BVALID,
  input  wire S_AXI_BREADY,
  input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_ARADDR,
  input  wire [2:0] S_AXI_ARPROT,
  input  wire S_AXI_ARVALID,
  output wire S_AXI_ARREADY,
  output wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_RDATA,
  output wire [1:0] S_AXI_RRESP,
  output wire S_AXI_RVALID,
  input  wire S_AXI_RREADY
);
  reg [C_S_AXI_ADDR_WIDTH-1:0] axi_awaddr, axi_araddr;
  reg axi_awready, axi_wready, axi_bvalid, axi_arready, axi_rvalid;
  reg [1:0] axi_bresp, axi_rresp;
  localparam integer ADDR_LSB = (C_S_AXI_DATA_WIDTH/32) + 1;   // 2
  localparam integer OPT_MEM_ADDR_BITS = 3;                    // 16 registri
  reg [C_S_AXI_DATA_WIDTH-1:0] slv_reg0, slv_reg1, slv_reg2, slv_reg3, slv_reg4;
  integer byte_index;
  reg [1:0] state_write, state_read;
  localparam Idle=2'b00, Waddr=2'b10, Wdata=2'b11, Raddr=2'b10, Rdata=2'b11;

  assign S_AXI_AWREADY = axi_awready;
  assign S_AXI_WREADY  = axi_wready;
  assign S_AXI_BRESP   = axi_bresp;
  assign S_AXI_BVALID  = axi_bvalid;
  assign S_AXI_ARREADY = axi_arready;
  assign S_AXI_RRESP   = axi_rresp;
  assign S_AXI_RVALID  = axi_rvalid;

  // write FSM
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin
      axi_awready<=0; axi_wready<=0; axi_bvalid<=0; axi_bresp<=0; axi_awaddr<=0; state_write<=Idle;
    end else begin
      case (state_write)
        Idle: begin axi_awready<=1; axi_wready<=1; state_write<=Waddr; end
        Waddr: begin
          if (S_AXI_AWVALID && axi_awready) begin
            axi_awaddr<=S_AXI_AWADDR;
            if (S_AXI_WVALID) begin axi_awready<=1; state_write<=Waddr; axi_bvalid<=1; end
            else begin axi_awready<=0; state_write<=Wdata; if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0; end
          end else if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0;
        end
        Wdata: begin
          if (S_AXI_WVALID) begin state_write<=Waddr; axi_bvalid<=1; axi_awready<=1; end
          else if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0;
        end
        default: state_write<=Idle;
      endcase
    end
  end

  // write register logic
  wire [OPT_MEM_ADDR_BITS:0] wr_idx =
      (S_AXI_AWVALID) ? S_AXI_AWADDR[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB]
                      : axi_awaddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB];
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin slv_reg0<=0; slv_reg1<=0; slv_reg2<=0; slv_reg3<=0; slv_reg4<=0; end
    else if (S_AXI_WVALID) begin
      case (wr_idx)
        4'd0: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg0[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd1: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg1[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd2: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg2[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd3: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg3[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd4: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg4[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        default: ;
      endcase
    end
  end

  // read FSM
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin axi_arready<=0; axi_rvalid<=0; axi_rresp<=0; state_read<=Idle; end
    else begin
      case (state_read)
        Idle: begin state_read<=Raddr; axi_arready<=1; end
        Raddr: if (S_AXI_ARVALID&&axi_arready) begin state_read<=Rdata; axi_araddr<=S_AXI_ARADDR; axi_rvalid<=1; axi_arready<=0; end
        Rdata: if (S_AXI_RVALID&&S_AXI_RREADY) begin axi_rvalid<=0; axi_arready<=1; state_read<=Raddr; end
        default: state_read<=Idle;
      endcase
    end
  end

  // user logic: snn_top_b2 (via wrapper flat)
  wire [75:0] xn_flat = {slv_reg3[18:0], slv_reg2[18:0], slv_reg1[18:0], slv_reg0[18:0]};
  reg reg4_d0;
  always @(posedge S_AXI_ACLK) reg4_d0 <= slv_reg4[0];
  wire start_pulse = slv_reg4[0] & ~reg4_d0;       // pulse su fronte di salita del control
  wire [104:0] params_w; wire done_w, ce_w;
  snn_top_b2_flat u_snn (
    .clk(S_AXI_ACLK), .reset(~S_AXI_ARESETN), .clk_enable(1'b1),
    .xn(xn_flat), .start(start_pulse), .ce_out(ce_w), .params(params_w), .done(done_w)
  );
  reg [104:0] params_lat; reg done_lat;
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin params_lat<=0; done_lat<=0; end
    else begin
      if (start_pulse) done_lat<=0;
      if (done_w) begin params_lat<=params_w; done_lat<=1'b1; end
    end
  end

  // read mux
  reg [C_S_AXI_DATA_WIDTH-1:0] rd_data;
  wire [OPT_MEM_ADDR_BITS:0] rd_idx = axi_araddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB];
  always @(*) begin
    case (rd_idx)
      4'd0: rd_data = slv_reg0;
      4'd1: rd_data = slv_reg1;
      4'd2: rd_data = slv_reg2;
      4'd3: rd_data = slv_reg3;
      4'd4: rd_data = {31'd0, done_lat};
      4'd5: rd_data = {{11{params_lat[20]}},  params_lat[20:0]};
      4'd6: rd_data = {{11{params_lat[41]}},  params_lat[41:21]};
      4'd7: rd_data = {{11{params_lat[62]}},  params_lat[62:42]};
      4'd8: rd_data = {{11{params_lat[83]}},  params_lat[83:63]};
      4'd9: rd_data = {{11{params_lat[104]}}, params_lat[104:84]};
      default: rd_data = 0;
    endcase
  end
  assign S_AXI_RDATA = rd_data;
endmodule
