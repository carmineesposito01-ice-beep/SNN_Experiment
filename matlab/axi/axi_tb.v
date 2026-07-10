`timescale 1ns/1ps
// TB master AXI4-Lite per snn_b2_axi_lite: scrive xn, pulse start, poll done, legge params.
module axi_tb;
  reg clk=0, resetn=0;
  reg [5:0] AWADDR=0; reg AWVALID=0; wire AWREADY;
  reg [31:0] WDATA=0; reg [3:0] WSTRB=0; reg WVALID=0; wire WREADY;
  wire [1:0] BRESP; wire BVALID; reg BREADY=0;
  reg [5:0] ARADDR=0; reg ARVALID=0; wire ARREADY;
  wire [31:0] RDATA; wire [1:0] RRESP; wire RVALID; reg RREADY=0;
  reg [31:0] rd;
  integer errors=0, i;

  snn_b2_axi_lite dut (
    .S_AXI_ACLK(clk), .S_AXI_ARESETN(resetn),
    .S_AXI_AWADDR(AWADDR), .S_AXI_AWPROT(3'b0), .S_AXI_AWVALID(AWVALID), .S_AXI_AWREADY(AWREADY),
    .S_AXI_WDATA(WDATA), .S_AXI_WSTRB(WSTRB), .S_AXI_WVALID(WVALID), .S_AXI_WREADY(WREADY),
    .S_AXI_BRESP(BRESP), .S_AXI_BVALID(BVALID), .S_AXI_BREADY(BREADY),
    .S_AXI_ARADDR(ARADDR), .S_AXI_ARPROT(3'b0), .S_AXI_ARVALID(ARVALID), .S_AXI_ARREADY(ARREADY),
    .S_AXI_RDATA(RDATA), .S_AXI_RRESP(RRESP), .S_AXI_RVALID(RVALID), .S_AXI_RREADY(RREADY)
  );

  always #5 clk = ~clk;

  task axi_write(input [5:0] a, input [31:0] d);
    begin
      @(posedge clk); AWADDR<=a; WDATA<=d; WSTRB<=4'hF; AWVALID<=1; WVALID<=1; BREADY<=1;
      @(posedge clk);
      while (!(AWREADY && WREADY)) @(posedge clk);
      AWVALID<=0; WVALID<=0;
      while (!BVALID) @(posedge clk);
      @(posedge clk); BREADY<=0;
    end
  endtask

  task axi_read(input [5:0] a);
    begin
      @(posedge clk); ARADDR<=a; ARVALID<=1; RREADY<=1;
      @(posedge clk);
      while (!ARREADY) @(posedge clk);
      ARVALID<=0;
      while (!RVALID) @(posedge clk);
      rd = RDATA;
      @(posedge clk); RREADY<=0;
    end
  endtask

  task chk(input [31:0] got, input [31:0] exp, input [80*8:1] nm);
    begin
      if (got !== exp) begin $display("MISMATCH %0s: got %08X exp %08X", nm, got, exp); errors=errors+1; end
      else $display("OK %0s = %08X", nm, got);
    end
  endtask

  initial begin
    resetn=0; repeat(12) @(posedge clk); resetn=1; repeat(6) @(posedge clk);
    axi_write(6'h00, 32'h00001462);   // xn0
    axi_write(6'h04, 32'h000008A2);   // xn1
    axi_write(6'h08, 32'h00000150);   // xn2
    axi_write(6'h0C, 32'h00000087);   // xn3
    axi_write(6'h10, 32'h00000001);   // control: start (pulse su fronte)
    axi_write(6'h10, 32'h00000000);   // clear control
    rd=0; i=0;
    while (rd[0]==1'b0 && i<3000) begin axi_read(6'h10); i=i+1; end
    $display("done dopo %0d poll (status=%08X)", i, rd);
    axi_read(6'h14); chk(rd, 32'h00034FB6, "p0_v0");
    axi_read(6'h18); chk(rd, 32'h00003426, "p1_T");
    axi_read(6'h1C); chk(rd, 32'h00004E6C, "p2_s0");
    axi_read(6'h20); chk(rd, 32'h00002044, "p3_a");
    axi_read(6'h24); chk(rd, 32'h000036C6, "p4_b");
    if (errors==0) $display("**************AXI TEST PASSED**************");
    else           $display("**************AXI TEST FAILED (%0d err)**************", errors);
    $finish;
  end
endmodule
