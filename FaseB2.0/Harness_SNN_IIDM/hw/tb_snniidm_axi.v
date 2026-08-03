`timescale 1ns/1ps
`include "axi_params.vh"          // `NSTEP  `GATEMODE  `CLKHALF
// -----------------------------------------------------------------------------------------------
// TB AXI-master per snniidm_axi_lite (T7b): per ogni control-step scrive i 4 ingressi, fa UN commit,
// attende `done` e legge **UNA** uscita — l'accel (sfix13_En8) — confrontandola col golden del BLOCCO.
// Gemello di tb_tier_axi.v di T6b, che ne leggeva 5 (i params della SNN sola).
//
// UNA traiettoria per simulazione: lo stato SNN vive nella hdl.RAM e si azzera solo all'init (finding T6a).
// -----------------------------------------------------------------------------------------------
module tb_snniidm_axi;
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
  reg  [12:0] gold [0:NSTEP-1];               // UNA accel per control-step
  reg  [31:0] lenm [0:0];
  integer k, nmis, nrun;
  reg [31:0] rd;

  snniidm_axi_lite dut (
    .S_AXI_ACLK(ACLK), .S_AXI_ARESETN(ARESETN),
    .S_AXI_AWADDR(AWADDR), .S_AXI_AWPROT(3'd0), .S_AXI_AWVALID(AWVALID), .S_AXI_AWREADY(AWREADY),
    .S_AXI_WDATA(WDATA), .S_AXI_WSTRB(WSTRB), .S_AXI_WVALID(WVALID), .S_AXI_WREADY(WREADY),
    .S_AXI_BRESP(BRESP), .S_AXI_BVALID(BVALID), .S_AXI_BREADY(BREADY),
    .S_AXI_ARADDR(ARADDR), .S_AXI_ARPROT(3'd0), .S_AXI_ARVALID(ARVALID), .S_AXI_ARREADY(ARREADY),
    .S_AXI_RDATA(RDATA), .S_AXI_RRESP(RRESP), .S_AXI_RVALID(RVALID), .S_AXI_RREADY(RREADY));

  // ⚠️ Nella sim COMPORTAMENTALE il semi-periodo e' irrilevante (nessun ritardo). Nella sim di TIMING
  //    (netlist + SDF) NON lo e': va usato il periodo dell'FCLK per cui il design e' stato implementato.
  //    Pilotare la netlist piu' veloce genera violazioni di setup e risultati sbagliati -- che sono la
  //    risposta CORRETTA del simulatore a uno stimolo sbagliato, non un difetto del design (T6b).
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
      // ⚠️ campionare RDATA subito dopo wait(RVALID) prende il dato dell'indirizzo PRECEDENTE: axi_araddr
      //    e' aggiornato in non-blocking e il read-mux e' combinatorio -> va lasciato stabilizzare.
      //    (In T6b il sintomo era: ogni lettura in ritardo di una transazione.)
      @(negedge ACLK);
      rd = RDATA;
      @(posedge ACLK); ARVALID <= 0; RREADY <= 0;
      @(posedge ACLK);
    end
  endtask

  initial begin
    $readmemh("axi_stim.mem", stim);
    $readmemh("axi_gold.mem", gold);
    // ⚠️ Gli scenari che COLLIDONO hanno la serie TRONCATA (N < NSTEP): il golden ha solo N valori.
    //    Eseguire NSTEP passi fissi farebbe leggere memoria NON INIZIALIZZATA oltre N, producendo
    //    disallineamenti che non sono del DUT ma del banco. Il numero di passi si legge a runtime.
    $readmemh("axi_len.mem", lenm);
    nrun = lenm[0];
    if (nrun < 1 || nrun > NSTEP) begin
      $display("TB-FATAL: axi_len.mem = %0d, fuori da [1,%0d]", nrun, NSTEP); $finish;
    end
    nmis = 0;
    ARESETN = 0; repeat (16) @(posedge ACLK); ARESETN = 1; repeat (4) @(posedge ACLK);

    axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});      // bit1 = clock gating, bit0 = commit basso
    for (k = 0; k < nrun; k = k + 1) begin
      axi_write(6'h00, stim[k*4+0]);
      axi_write(6'h04, stim[k*4+1]);
      axi_write(6'h08, stim[k*4+2]);
      axi_write(6'h0C, stim[k*4+3]);
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b0});    // control basso...
      axi_write(6'h10, {30'd0, GATEMODE[0], 1'b1});    // ...poi COMMIT (fronte di salita)
      rd = 0;
      while (rd[0] !== 1'b1) axi_read(6'h10);          // poll del done

      // DBG sul primo control-step: separa "il wrapper ha latchato male" da "il path di lettura sbaglia".
      // Senza questi valori, un disallineamento non dice QUALE dei due e' rotto (lezione T6b).
`ifndef NETLIST_SIM
      if (k == 0) begin
        $display("DBG dut_accel = %04X", dut.w_accel);
        $display("DBG accel_lat = %04X", dut.accel_lat);
        $display("DBG gold      = %04X", gold[0]);
      end
`endif
      axi_read(6'h14);                                  // UNA sola lettura: l'accel
      if (k == 0) $display("DBG read = %04X  gold = %04X", rd[12:0], gold[0]);
      if (rd[12:0] !== gold[k]) nmis = nmis + 1;
    end

    $display("AXI-COSIM nMismatch=%0d n=%0d gatemode=%0d", nmis, nrun, GATEMODE);
    $finish;
  end
endmodule
