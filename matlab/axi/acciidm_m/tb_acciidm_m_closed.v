`timescale 1ns/1ps
// Harness B.2 anello LIVE (Fase B2.0-2a-M2): plant EGO nel TB (real, verificato da PLANT-PAR) <-> controllore
// RTL (Donatello_ACC_IIDM_M) in retroazione sull'accel. Ogni control-step: stato plant -> xq -> guida il DUT
// -> attende HOLD -> legge accel -> plant integra. Confronta la traiettoria (xq + accel) col riferimento
// (cl_ref_acciidm_m). B-LOOP: dmax=0. BEHAV: gap>0 (no collisione). `KVAL/`HOLD da cl_dims.vh.
`include "cl_dims.vh"
module tb_acciidm_m_closed;
  localparam integer K = `KVAL;
  localparam integer HOLD = `HOLD;
  reg [63:0] xl[0:K-1], vl[0:K-1], golds[0:K-1], goldv[0:K-1], golddv[0:K-1], goldacc[0:K-1];
  reg [63:0] cnst [0:3];
  real s_lo, v_cap, xe, ve, ve_prev, DT, S_MAX, s, dv, xqs, xqv, xqdv, acc, xe_new, ve_new;
  reg  clk = 0, reset = 0, clk_enable = 1;
  reg  [31:0] s_in, v_in, dv_in, vl_in;
  wire [12:0] accel;
  wire ce_out;
  integer k, nmis, firstbad, gap_bad;

  function real q(input real x); q = $floor(x * 1048576.0) / 1048576.0; endfunction
  function real clp(input real x, input real lo, input real hi);
    clp = (x < lo) ? lo : ((x > hi) ? hi : x); endfunction
  function [31:0] tofix(input real x); tofix = $rtoi(x * 1048576.0); endfunction  // real(mult 2^-20)->sfix32_En20

  Donatello_ACC_IIDM_M dut (.clk(clk), .reset(reset), .clk_enable(clk_enable),
     .s(s_in), .v(v_in), .dv(dv_in), .v_l(vl_in), .accel(accel), .ce_out(ce_out));
  always #62.5 clk = ~clk;

  task drive_xq;   // calcola xq dallo stato del plant e pilota gli ingressi del controllore
    begin
      s   = clp($bitstoreal(xl[k]) - xe, s_lo, S_MAX);
      dv  = ve_prev - $bitstoreal(vl[k]);
      xqs = q(s); xqv = q(ve); xqdv = q(dv);
      s_in = tofix(xqs); v_in = tofix(xqv); dv_in = tofix(xqdv); vl_in = tofix(q($bitstoreal(vl[k])));
    end
  endtask

  initial begin
    $readmemh("cl_xl.mem", xl); $readmemh("cl_vl.mem", vl); $readmemh("cl_accel.mem", goldacc);
    $readmemh("cl_golds.mem", golds); $readmemh("cl_goldv.mem", goldv); $readmemh("cl_golddv.mem", golddv);
    $readmemh("cl_const.mem", cnst);
    s_lo = $bitstoreal(cnst[0]); v_cap = $bitstoreal(cnst[1]);
    xe   = $bitstoreal(cnst[2]); ve    = $bitstoreal(cnst[3]);
    ve_prev = ve; DT = 0.1; S_MAX = 150.0;
    nmis = 0; firstbad = -1; gap_bad = 0;
    k = 0; drive_xq;                              // presenta xq[0] PRIMA di togliere reset
    reset = 1; repeat (8) @(posedge clk); reset = 0;
    for (k = 0; k < K; k = k + 1) begin
      if (k > 0) drive_xq;
      repeat (HOLD) @(posedge clk);
      acc = $itor($signed(accel)) / 256.0;        // accel RTL (Q4.8) -> real
      if ($realtobits(xqs) !== golds[k])   begin nmis=nmis+1; if(firstbad<0)firstbad=k; end
      if ($realtobits(xqv) !== goldv[k])   begin nmis=nmis+1; if(firstbad<0)firstbad=k; end
      if ($realtobits(xqdv)!== golddv[k])  begin nmis=nmis+1; if(firstbad<0)firstbad=k; end
      if ($realtobits(acc) !== goldacc[k]) begin nmis=nmis+1; if(firstbad<0)firstbad=k; end
      if (xqs <= 0.0) gap_bad = gap_bad + 1;       // BEHAV: gap deve restare > 0
      xe_new = xe + ve * DT;
      ve_new = clp(ve + acc * DT, 0.0, v_cap);
      ve_prev = ve; xe = xe_new; ve = ve_new;
    end
    $display("RTLRES nMismatch=%0d n=%0d firstbad=%0d gap_bad=%0d", nmis, K*4, firstbad, gap_bad);
    $finish;
  end
endmodule
