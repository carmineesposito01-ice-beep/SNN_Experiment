`timescale 1ns/1ps
`include "axi_params.vh"      // `define GATEMODE · `define CLKHALF · `define NSTEP · `define IDLECYC
// T6b · M3 — CROSS-CHECK della composizione: control-step realistici a duty RIDOTTO (inferenza + idle vero),
// con SAIF su TUTTA la finestra. Serve a PROVARE la formula
//     E_step = P_attiva*t_attivo + P_idle*t_idle
// confrontando l'energia MISURATA a duty noto con quella COMPOSTA dalle P_attiva/P_idle misurate separatamente.
// Non si simula il duty reale (0,0071% => ~5 M clock per control-step): il costo e' dato dal CLOCK, non dal
// tempo simulato, e a duty ridotto (idle di `IDLECYC clock) la verifica e' equivalente e affordable.
module tb_power_duty;
  localparam integer GATEMODE = `GATEMODE;
  localparam integer NSTEP    = `NSTEP;
  localparam integer IDLECYC  = `IDLECYC;
  reg ACLK = 0, ARESETN = 0;
  reg  [5:0]  AWADDR = 0, ARADDR = 0;
  reg  AWVALID = 0, WVALID = 0, ARVALID = 0, RREADY = 0, BREADY = 1;
  reg  [31:0] WDATA = 0;
  reg  [3:0]  WSTRB = 4'hF;
  wire AWREADY, WREADY, BVALID, ARREADY, RVALID;
  wire [1:0] BRESP, RRESP;
  wire [31:0] RDATA;
  reg  [31:0] rd;
  integer k;
  reg  [31:0] stim [0:NSTEP*4-1];

  tier_axi_lite dut (
    .S_AXI_ACLK(ACLK), .S_AXI_ARESETN(ARESETN),
    .S_AXI_AWADDR(AWADDR), .S_AXI_AWPROT(3'd0), .S_AXI_AWVALID(AWVALID), .S_AXI_AWREADY(AWREADY),
    .S_AXI_WDATA(WDATA), .S_AXI_WSTRB(WSTRB), .S_AXI_WVALID(WVALID), .S_AXI_WREADY(WREADY),
    .S_AXI_BRESP(BRESP), .S_AXI_BVALID(BVALID), .S_AXI_BREADY(BREADY),
    .S_AXI_ARADDR(ARADDR), .S_AXI_ARPROT(3'd0), .S_AXI_ARVALID(ARVALID), .S_AXI_ARREADY(ARREADY),
    .S_AXI_RDATA(RDATA), .S_AXI_RRESP(RRESP), .S_AXI_RVALID(RVALID), .S_AXI_RREADY(RREADY));

  always #(`CLKHALF) ACLK = ~ACLK;

  task axi_write(input [5:0] a, input [31:0] d);
    begin
      @(posedge ACLK); AWADDR <= a; AWVALID <= 1; WDATA <= d; WVALID <= 1;
      wait (AWREADY && WREADY);
      @(posedge ACLK); AWVALID <= 0; WVALID <= 0;
      @(posedge ACLK);
    end
  endtask
  task axi_read(input [5:0] a);
    begin
      @(posedge ACLK); ARADDR <= a; ARVALID <= 1; RREADY <= 1;
      wait (RVALID); @(negedge ACLK); rd = RDATA;
      @(posedge ACLK); ARVALID <= 0; RREADY <= 0; @(posedge ACLK);
    end
  endtask

  initial begin
    $readmemh("axi_stim.mem", stim);
    ARESETN = 0; repeat (16) @(posedge ACLK); ARESETN = 1; repeat (4) @(posedge ACLK);
    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});
    $display("DUTY-READY t=%0t", $time);      // il tcl apre la finestra SAIF da qui
    for (k = 0; k < NSTEP; k = k + 1) begin
      axi_write(6'h00, stim[k*4+0]);
      axi_write(6'h04, stim[k*4+1]);
      axi_write(6'h08, stim[k*4+2]);
      axi_write(6'h0C, stim[k*4+3]);
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b1});   // COMMIT
      rd = 0;
      while (rd[0] !== 1'b1) axi_read(6'h10);          // attende done (fase ATTIVA)
      repeat (IDLECYC) @(posedge ACLK);                // fase IDLE vera
    end
    $display("DUTY-DONE steps=%0d idle=%0d", NSTEP, IDLECYC);
  end
endmodule
