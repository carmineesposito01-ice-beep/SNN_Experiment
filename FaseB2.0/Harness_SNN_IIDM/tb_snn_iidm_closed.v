`timescale 1ns/1ps
`include "t7_params.vh"          // `KVAL, `HOLDV, `SCENF, `INITF, `OUTF
// -----------------------------------------------------------------------------------------------
// T7a — anello chiuso LIVE: plant (provato da PLANT-PAR) <-> Donatello_SNN_IIDM in retroazione.
//
// Ogni control-step: stato del plant -> quantizza a sfix32_En20 con FLOOR -> pilota il DUT ->
// attende HOLD clock -> legge accel (sfix13_En8) e i 5 parametri -> il plant integra.
//
// Le SERIE esportate sono la sorgente dei numeri riportati, e sono di due nature:
//   * stato FISICO del plant (s, v, vl, dv) NON quantizzato -> alimenta le metriche
//   * uscite del DUT (accel, 5 parametri)                   -> il prodotto dell'hardware
//
// HOLD deve superare la latenza del composto, MISURATA = 554 clock (probe P1).
// I 5 parametri sono segnali dell'architettura del top (il top espone solo `accel`): leggibili solo
// in simulazione COMPORTAMENTALE, perche' la netlist post-place&route perde i nomi gerarchici.
// -----------------------------------------------------------------------------------------------
module tb_snn_iidm_closed;
  localparam integer K = `KVAL;
  localparam integer HOLD = `HOLDV;
  localparam real DT = 0.1;
  reg [63:0] vlm[0:K-1], initm[0:3];
  real s, v, vl, dv, acc, vnew, cut_gap, impact_dv;
  integer k, cut_k, last, collided, fo;
  reg clk = 0, reset = 1, ce = 1;
  reg [31:0] s_in, v_in, dv_in, vl_in;
  wire [12:0] accel;
  wire ce_out;

  Donatello_SNN_IIDM dut(.clk(clk), .reset(reset), .clk_enable(ce),
                         .s(s_in), .v(v_in), .dv(dv_in), .v_l(vl_in),
                         .ce_out(ce_out), .accel(accel));
  always #5 clk = ~clk;

  // FLOOR a 2^-20 poi stored-integer a 32 bit: la convenzione fissata in spec §4 (probe P4b).
  // fi(...,'Floor') coincide ESATTAMENTE con floor(x*2^20)/2^20, quindi $floor e' conforme.
  function [31:0] toq(input real x);
    begin toq = $rtoi($floor(x * 1048576.0)); end
  endfunction

  task drive;                                        // stato del plant -> ingressi del DUT
    begin s_in = toq(s); v_in = toq(v); dv_in = toq(dv); vl_in = toq(vl); end
  endtask

  initial begin
    $readmemh(`SCENF, vlm); $readmemh(`INITF, initm);
    s = $bitstoreal(initm[0]); v = $bitstoreal(initm[1]);
    cut_k = $rtoi($bitstoreal(initm[2])); cut_gap = $bitstoreal(initm[3]);
    collided = 0; impact_dv = 0.0; last = K;
    fo = $fopen(`OUTF, "w");
    if (fo == 0) begin $display("T7-FATAL: impossibile aprire %s", `OUTF); $finish; end

    // Il primo control-step si presenta PRIMA del rilascio del reset: senza, all'uscita dal reset
    // gli ingressi passerebbero da indefinito a 0 e il rilevatore di fronte avvierebbe
    // un'inferenza SPURIA che avanza lo stato della rete (trappola T6b).
    if (cut_k == 1) s = cut_gap;
    vl = $bitstoreal(vlm[0]); dv = v - vl; drive;
    repeat (8) @(posedge clk); reset = 0;

    for (k = 1; k <= K; k = k + 1) begin
      if (k > 1) begin
        if (cut_k != 0 && k == cut_k) s = cut_gap;   // teletrasporto del cut-in (k 1-based)
        vl = $bitstoreal(vlm[k-1]);
        dv = v - vl;                                 // v CORRENTE, prima dell'update
        drive;
      end
      repeat (HOLD) @(posedge clk);
      acc = $itor($signed(accel)) / 256.0;           // sfix13_En8 -> real

      $fwrite(fo, "%0d %h %h %h %h %h %0d %0d %0d %0d %0d\n", k,
              $realtobits(s), $realtobits(v), $realtobits(vl), $realtobits(dv), $realtobits(acc),
`ifdef NETLIST_SIM
              0, 0, 0, 0, 0);                        // la netlist perde i nomi gerarchici (HDL_PHASE §9)
`else
              $signed(dut.Tier_v0), $signed(dut.Tier_T), $signed(dut.Tier_s0),
              $signed(dut.Tier_a),  $signed(dut.Tier_b));
`endif

      vnew = v + acc*DT; if (vnew < 0.0) vnew = 0.0;
      s = s + (vl - vnew)*DT;                        // usa la NUOVA v
      v = vnew;
      if (s <= 0.0) begin
        collided = 1; impact_dv = (v - vl) > 0.0 ? (v - vl) : 0.0; last = k;
        k = K + 1;                                   // esce dal for: equivale al break di MATLAB
      end
    end

    $fwrite(fo, "END %0d %0d %h %h\n", last, collided, $realtobits(s), $realtobits(impact_dv));
    $fclose(fo);
    $display("T7RES last=%0d collided=%0d", last, collided);
    $finish;
  end
endmodule
