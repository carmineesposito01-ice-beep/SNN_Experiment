`timescale 1ns/1ps
`include "axi_params.vh"      // `define GATEMODE <0|1>   `define CLKHALF <ns>
// T6b · M3 — TB per la fase IDLE: esegue UNA inferenza, poi lascia girare il clock SENZA altri commit.
// La finestra SAIF viene aperta dal tcl DOPO che l'inferenza e' finita, cosi' misura solo l'idle.
// L'idle e' uno stato STAZIONARIO (ingressi fermi, commuta solo l'albero del clock) -> non dipende dal
// workload: basta una misura per stato di gating (gatato / non gatato).
// `IDLE_START (ns) e' il momento oltre il quale il TB segnala che l'inferenza e' conclusa: il tcl lo usa
// per aprire la finestra. Segnale osservabile: idle_flag.
module tb_power_idle;
  localparam integer GATEMODE = `GATEMODE;
  reg ACLK = 0, ARESETN = 0;
  reg  [5:0]  AWADDR = 0, ARADDR = 0;
  reg  AWVALID = 0, WVALID = 0, ARVALID = 0, RREADY = 0, BREADY = 1;
  reg  [31:0] WDATA = 0;
  reg  [3:0]  WSTRB = 4'hF;
  wire AWREADY, WREADY, BVALID, ARREADY, RVALID;
  wire [1:0] BRESP, RRESP;
  wire [31:0] RDATA;
  reg  [31:0] rd;
  reg  idle_flag = 0;          // 1 = il DUT e' in idle (nessun commit in corso): finestra SAIF valida

  snniidm_axi_lite dut (
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
      wait (RVALID);
      @(negedge ACLK);
      rd = RDATA;
      @(posedge ACLK); ARVALID <= 0; RREADY <= 0;
      @(posedge ACLK);
    end
  endtask

  initial begin
    ARESETN = 0; repeat (16) @(posedge ACLK); ARESETN = 1; repeat (4) @(posedge ACLK);
    // una sola inferenza, con ingressi realistici (s=30 m, v=20, dv=-1, v_l=21 in Q?.20)
    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});
    axi_write(6'h00, 32'd31457280);     // 30.0 * 2^20
    axi_write(6'h04, 32'd20971520);     // 20.0 * 2^20
    axi_write(6'h08, -32'd1048576);     // -1.0 * 2^20
    axi_write(6'h0C, 32'd22020096);     // 21.0 * 2^20
    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});
    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b1});   // COMMIT
    rd = 0;
    while (rd[0] !== 1'b1) axi_read(6'h10);          // attende done
    repeat (20) @(posedge ACLK);
    idle_flag = 1;                                   // da qui in poi: IDLE (nessun commit, nessun accesso AXI)
    $display("IDLE-READY t=%0t", $time);
    // niente $finish: il tcl chiude la simulazione dopo la finestra SAIF
  end
endmodule
