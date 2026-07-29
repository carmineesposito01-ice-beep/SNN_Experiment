`timescale 1ns/1ps
`include "axi_params.vh"          // `define NSTEP <n>   `define GATEMODE <0|1>
// TB AXI-master per tier_axi_lite: per ogni control-step scrive i 4 ingressi, fa UN commit, attende `done`,
// legge i 5 parametri e li confronta col golden (l'oracolo di T6a). Verifica anche SYNC (1 commit = 1 inferenza)
// osservando quante volte cambia l'uscita del Tier dentro la gerarchia.
// UNA traiettoria per simulazione: il runner rifa xsim per ogni traiettoria (la hdl.RAM si azzera solo all'init).
module tb_tier_axi;
  localparam integer NSTEP    = `NSTEP;
  localparam integer GATEMODE = `GATEMODE;    // 0 = clock libero (riferimento) · 1 = clock gating attivo
  reg ACLK = 0, ARESETN = 0;
  reg  [5:0]  AWADDR = 0, ARADDR = 0;
  reg  AWVALID = 0, WVALID = 0, ARVALID = 0, RREADY = 0, BREADY = 1;
  reg  [31:0] WDATA = 0;
  reg  [3:0]  WSTRB = 4'hF;
  wire AWREADY, WREADY, BVALID, ARREADY, RVALID;
  wire [1:0] BRESP, RRESP;
  wire [31:0] RDATA;
  reg  [31:0] stim [0:NSTEP*4-1];
  reg  [20:0] gold [0:NSTEP*5-1];
  integer k, i, nmis, ninf;
  reg signed [20:0] prev_v0;
  reg [31:0] rd;

  tier_axi_lite dut (
    .S_AXI_ACLK(ACLK), .S_AXI_ARESETN(ARESETN),
    .S_AXI_AWADDR(AWADDR), .S_AXI_AWPROT(3'd0), .S_AXI_AWVALID(AWVALID), .S_AXI_AWREADY(AWREADY),
    .S_AXI_WDATA(WDATA), .S_AXI_WSTRB(WSTRB), .S_AXI_WVALID(WVALID), .S_AXI_WREADY(WREADY),
    .S_AXI_BRESP(BRESP), .S_AXI_BVALID(BVALID), .S_AXI_BREADY(BREADY),
    .S_AXI_ARADDR(ARADDR), .S_AXI_ARPROT(3'd0), .S_AXI_ARVALID(ARVALID), .S_AXI_ARREADY(ARREADY),
    .S_AXI_RDATA(RDATA), .S_AXI_RRESP(RRESP), .S_AXI_RVALID(RVALID), .S_AXI_RREADY(RREADY));

  always #5 ACLK = ~ACLK;                     // 100 MHz per la cosim funzionale

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
      // ⚠️ campionare RDATA subito dopo wait(RVALID) prende il dato dell'indirizzo PRECEDENTE: axi_araddr e'
      //    aggiornato in non-blocking e il read-mux e' combinatorio -> serve lasciarlo stabilizzare.
      //    (Sintomo: ogni lettura in ritardo di una transazione -> read[0] restituiva il registro done.)
      @(negedge ACLK);
      rd = RDATA;
      @(posedge ACLK); ARVALID <= 0; RREADY <= 0;
      @(posedge ACLK);
    end
  endtask

  // SYNC: conta i fronti del BUS D'INGRESSO COMMITTED del Tier (s_c,v_c,dv_c,vl_c).
  // ⚠️ NON si contano i cambi di v0: e' una stima lenta e due control-step possono dare lo STESSO valore
  //    -> quel contatore SOTTOCONTA e non misura cio' che serve. Cio' che va provato e' che i 4 ingressi
  //    cambino INSIEME: 1 solo fronte del bus per commit (se cambiassero separatamente si vedrebbero >1).
  wire [127:0] tin = {dut.s_c, dut.v_c, dut.dv_c, dut.vl_c};
  reg  [127:0] tin_d;
  always @(posedge ACLK) begin
    tin_d <= tin;
    if (ARESETN && tin !== tin_d) ninf <= ninf + 1;
  end

`ifdef PROBE_TIMING
  // Probe di timing: misura commit -> cambio uscita -> done, per TARARE LAT_CLK sul dato invece che dedurlo.
  // Attivo solo con `+define+PROBE_TIMING` (altrimenti spammerebbe il run full-60).
  integer cyc = 0;  reg done_d = 0;
  always @(posedge ACLK) begin
    cyc <= cyc + 1;
    done_d <= dut.done_lat;
    if (ARESETN && cyc < 3000) begin
      if (dut.commit)                        $display("PROBE commit  @cyc %0d", cyc);
      if (dut.u_tier.v0 !== prev_v0) begin   $display("PROBE v0_chg  @cyc %0d", cyc); prev_v0 <= dut.u_tier.v0; end
      if (dut.done_lat && !done_d)           $display("PROBE done    @cyc %0d", cyc);
    end
  end
`endif

  initial begin
    $readmemh("axi_stim.mem", stim);
    $readmemh("axi_gold.mem", gold);
    nmis = 0; ninf = 0;
    ARESETN = 0; repeat (16) @(posedge ACLK); ARESETN = 1; repeat (4) @(posedge ACLK);
    prev_v0 = dut.u_tier.v0;
    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});      // bit1 = clock gating, bit0 = commit basso
    for (k = 0; k < NSTEP; k = k + 1) begin
      axi_write(6'h00, stim[k*4+0]);
      axi_write(6'h04, stim[k*4+1]);
      axi_write(6'h08, stim[k*4+2]);
      axi_write(6'h0C, stim[k*4+3]);
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});    // control basso...
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b1});    // ...poi COMMIT (fronte di salita)
      rd = 0;
      while (rd[0] !== 1'b1) axi_read(6'h10);          // poll del done
      // DBG sul primo control-step: separa "il wrapper ha latchato male" da "il path di lettura sbaglia"
      if (k == 0) begin
        $display("DBG tier_out  v0=%06X T=%06X s0=%06X a=%06X b=%06X",
                 dut.u_tier.v0, dut.u_tier.T, dut.u_tier.s0, dut.u_tier.a, dut.u_tier.b);
        $display("DBG params_lat= %h", dut.params_lat);
        $display("DBG gold       v0=%06X T=%06X s0=%06X a=%06X b=%06X",
                 gold[0], gold[1], gold[2], gold[3], gold[4]);
      end
      for (i = 0; i < 5; i = i + 1) begin
        axi_read(6'h14 + i*4);
        if (k == 0) $display("DBG read[%0d]=%06X  gold=%06X", i, rd[20:0], gold[k*5+i]);
        if (rd[20:0] !== gold[k*5+i]) nmis = nmis + 1;
      end
    end
    $display("AXI-COSIM nMismatch=%0d n=%0d", nmis, NSTEP*5);
    $display("SYNC inferenze=%0d attese=%0d", ninf, NSTEP);
    $finish;
  end
endmodule
