`timescale 1ns/1ps
`include "t7_params.vh"          // `KVAL, `SCENF, `INITF, `ACCF, `OUTF
// -----------------------------------------------------------------------------------------------
// PLANT-PAR (T7a Task 1): il plant del testbench riproduce qz_cl_sim?
// Pilotato con la sequenza accel del RIFERIMENTO e SENZA DUT: isola i difetti d'integrazione prima
// dell'anello live, cosi' che un difetto del plant non si travesta da difetto del blocco.
//
// Ordine ESATTO di qz_cl_sim (matlab/Quantizzation_Study/qz_cl_sim.m, righe 18-31):
//   cut-in -> vl -> dv (con v CORRENTE) -> registra PRE-update -> v = max(0,v+a*DT)
//   -> s = s + (vl - v_NUOVA)*DT -> break se s <= 0
// Verilog `real` e' IEEE-754 double come MATLAB: la parita' dev'essere ESATTA, non "al livello del float".
// -----------------------------------------------------------------------------------------------
module tb_plant_only;
  localparam integer K = `KVAL;
  localparam real DT = 0.1;
  reg [63:0] vlm[0:K-1], initm[0:3], accm[0:K-1];
  real s, v, vl, dv, acc, vnew, cut_gap, impact_dv;
  integer k, cut_k, last, collided, fo;

  initial begin
    $readmemh(`SCENF, vlm); $readmemh(`INITF, initm); $readmemh(`ACCF, accm);
    s = $bitstoreal(initm[0]); v = $bitstoreal(initm[1]);
    cut_k = $rtoi($bitstoreal(initm[2])); cut_gap = $bitstoreal(initm[3]);
    collided = 0; impact_dv = 0.0; last = K;
    fo = $fopen(`OUTF, "w");
    if (fo == 0) begin $display("PLANTPAR-FATAL: impossibile aprire %s", `OUTF); $finish; end

    for (k = 1; k <= K; k = k + 1) begin
      if (cut_k != 0 && k == cut_k) s = cut_gap;      // teletrasporto (k 1-based, come MATLAB)
      vl  = $bitstoreal(vlm[k-1]);
      dv  = v - vl;                                   // v CORRENTE, prima dell'update
      acc = $bitstoreal(accm[k-1]);                   // niente DUT: accel dal riferimento
      $fwrite(fo, "%0d %h %h %h %h\n", k, $realtobits(s), $realtobits(v),
              $realtobits(vl), $realtobits(dv));      // registra PRE-update
      vnew = v + acc*DT; if (vnew < 0.0) vnew = 0.0;
      s = s + (vl - vnew)*DT;                         // usa la NUOVA v
      v = vnew;
      if (s <= 0.0) begin
        collided = 1; impact_dv = (v - vl) > 0.0 ? (v - vl) : 0.0; last = k;
        k = K + 1;                                    // esce dal for: equivale al break di MATLAB
      end
    end

    $fwrite(fo, "END %0d %0d %h %h\n", last, collided, $realtobits(s), $realtobits(impact_dv));
    $fclose(fo);
    $display("PLANTPAR last=%0d collided=%0d", last, collided);
    $finish;
  end
endmodule
