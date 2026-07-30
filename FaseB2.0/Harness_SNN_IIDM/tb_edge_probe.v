`timescale 1ns/1ps
`include "t7_params.vh"          // `KVAL, `HOLDV, `SCENF, `INITF, `OUTF
// -----------------------------------------------------------------------------------------------
// T7b — PROBE DEL MECCANISMO: quanti FRONTI vedono gli ingressi dell'ACC per control-step?
//
// `align` esiste per garantire UNA sola inferenza per control-step: se i 9 ingressi dell'ACC
// cambiassero in due momenti diversi, il filtro OU verrebbe aggiornato DUE volte (bug silenzioso,
// dichiarato nella descrizione del blocco).
//
// Il registro di confine ha cambiato il comportamento del controllore (581/600 accel diverse,
// persistente con margine 4x). L'ipotesi da provare: SENZA registro l'ACC vede un DOPPIO fronte, e
// il registro l'ha accidentalmente corretto -> il blocco NUOVO sarebbe quello giusto.
//
// Qui si contano i fronti dei 9 ingressi dell'ACC nel primo control-step, con il tempo in cui
// avvengono. Il conteggio e' il fatto discriminante: 1 fronte = corretto, 2 = doppio aggiornamento.
// Compilare con `ACC_IN_PIPE` per la versione col registro (i segnali si chiamano pipe*_out1).
// -----------------------------------------------------------------------------------------------
module tb_edge_probe;
  localparam integer K = `KVAL;
  localparam integer HOLD = `HOLDV;
  localparam real DT = 0.1;
  reg [63:0] vlm[0:K-1], initm[0:3];
  real s, v, vl, dv, cut_gap;
  integer k, cut_k, cyc, nedge;
  reg clk = 0, reset = 1, ce = 1;
  reg [31:0] s_in, v_in, dv_in, vl_in;
  wire [12:0] accel;
  wire ce_out;

  Donatello_SNN_IIDM dut(.clk(clk), .reset(reset), .clk_enable(ce),
                         .s(s_in), .v(v_in), .dv(dv_in), .v_l(vl_in),
                         .ce_out(ce_out), .accel(accel));
  always #5 clk = ~clk;
  function [31:0] toq(input real x); begin toq = $rtoi($floor(x * 1048576.0)); end endfunction

  // vista dei 9 ingressi dell'ACC: col registro sono i pipe*, senza sono align/Tier diretti
`ifdef ACC_IN_PIPE
  wire [180:0] acc_in = {dut.pipe1_out1, dut.pipe2_out1, dut.pipe3_out1, dut.pipe4_out1,
                         dut.pipe5_out1, dut.pipe6_out1, dut.pipe7_out1, dut.pipe8_out1, dut.pipe9_out1};
`else
  wire [180:0] acc_in = {dut.sa, dut.va, dut.dva, dut.vla,
                         dut.Tier_v0, dut.Tier_T, dut.Tier_s0, dut.Tier_a, dut.Tier_b};
`endif
  reg [180:0] acc_in_d;

  initial begin
    $readmemh(`SCENF, vlm); $readmemh(`INITF, initm);
    s = $bitstoreal(initm[0]); v = $bitstoreal(initm[1]);
    cut_k = $rtoi($bitstoreal(initm[2])); cut_gap = $bitstoreal(initm[3]);
    vl = $bitstoreal(vlm[0]); dv = v - vl;
    s_in = toq(s); v_in = toq(v); dv_in = toq(dv); vl_in = toq(vl);
    repeat (8) @(posedge clk); reset = 0;
    cyc = 0; nedge = 0; acc_in_d = acc_in;
    repeat (HOLD) begin
      @(posedge clk);
      cyc = cyc + 1;
      if (acc_in !== acc_in_d) begin
        nedge = nedge + 1;
        $display("EDGE  n=%0d  al ciclo %0d  (accel corrente = %0d)", nedge, cyc, $signed(accel));
      end
      acc_in_d = acc_in;
    end
    $display("EDGEPROBE fronti_ingressi_ACC = %0d  nel primo control-step (%0d cicli)  accel_finale = %0d",
             nedge, HOLD, $signed(accel));
    $finish;
  end
endmodule
