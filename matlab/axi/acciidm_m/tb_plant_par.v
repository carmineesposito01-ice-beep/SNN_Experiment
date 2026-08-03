`timescale 1ns/1ps
// Harness B.2 PLANT-PAR: verifica che il plant EGO riprodotto qui in `real` (double) == il plant di
// riferimento (cl_ref_acciidm_m), pilotato con la STESSA sequenza accel, SENZA il controllore RTL. Se
// combacia bit-exact, il plant-nel-TB e' fedele -> l'anello live (tb_acciidm_m_closed) puo' fidarsene.
// Double trasferiti bit-esatti: num2hex (MATLAB) -> $bitstoreal / $realtobits (qui). `KVAL da cl_dims.vh.
// Prova di SENSIBILITA': con -d SENS usa dv = ve - vl (istantanea) invece di ve_prev - vl -> deve divergere.
`include "cl_dims.vh"
module tb_plant_par;
  localparam integer K = `KVAL;
  reg [63:0] xl[0:K-1], vl[0:K-1], accel[0:K-1], golds[0:K-1], goldv[0:K-1], golddv[0:K-1];
  reg [63:0] cnst [0:3];
  real s_lo, v_cap, xe, ve, ve_prev, DT, S_MAX;
  real s, dv, xqs, xqv, xqdv, acc, xe_new, ve_new;
  integer k, nmis, firstbad;

  function real q(input real x); q = $floor(x * 1048576.0) / 1048576.0; endfunction
  function real clp(input real x, input real lo, input real hi);
    clp = (x < lo) ? lo : ((x > hi) ? hi : x);
  endfunction

  initial begin
    $readmemh("cl_xl.mem", xl);       $readmemh("cl_vl.mem", vl);       $readmemh("cl_accel.mem", accel);
    $readmemh("cl_golds.mem", golds); $readmemh("cl_goldv.mem", goldv); $readmemh("cl_golddv.mem", golddv);
    $readmemh("cl_const.mem", cnst);
    s_lo = $bitstoreal(cnst[0]); v_cap = $bitstoreal(cnst[1]);
    xe   = $bitstoreal(cnst[2]); ve    = $bitstoreal(cnst[3]);
    ve_prev = ve; DT = 0.1; S_MAX = 150.0;
    nmis = 0; firstbad = -1;
    for (k = 0; k < K; k = k + 1) begin
      s  = clp($bitstoreal(xl[k]) - xe, s_lo, S_MAX);
`ifdef SENS
      dv = ve - $bitstoreal(vl[k]);              // SBAGLIATO apposta (istantanea) -> deve divergere
`else
      dv = ve_prev - $bitstoreal(vl[k]);         // convenzione dataset (v PRIMA dell'update)
`endif
      xqs = q(s); xqv = q(ve); xqdv = q(dv);
      if ($realtobits(xqs)  !== golds[k])  begin nmis=nmis+1; if(firstbad<0) firstbad=k; end
      if ($realtobits(xqv)  !== goldv[k])  begin nmis=nmis+1; if(firstbad<0) firstbad=k; end
      if ($realtobits(xqdv) !== golddv[k]) begin nmis=nmis+1; if(firstbad<0) firstbad=k; end
      acc     = $bitstoreal(accel[k]);
      xe_new  = xe + ve * DT;                    // balistico: v VECCHIA
      ve_new  = clp(ve + acc * DT, 0.0, v_cap);
      ve_prev = ve; xe = xe_new; ve = ve_new;
    end
    $display("RTLRES nMismatch=%0d n=%0d firstbad=%0d", nmis, K*3, firstbad);
    $finish;
  end
endmodule
