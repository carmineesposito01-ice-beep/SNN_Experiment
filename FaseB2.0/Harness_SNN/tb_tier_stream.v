`timescale 1ns/1ps
`include "tier_params.vh"
// Pilota Donatello_Tier (VHDL) con gli stim, campiona i 5 param a fine control-step vs gold; misura LAT.
// Nomi porta confermati dall'ENTITY generata (Task 1): s,v,dv,v_l (sfix32_En20) -> v0,T,s0,a,b (sfix21_En13).
module tb_tier_stream;
  localparam integer K    = `KVAL;
  localparam integer HOLD = `HOLD;      // >= latenza RTL (~364); campiona a fine control-step
  reg clk = 0, reset = 0, clk_enable = 1;
  reg  signed [31:0] s, v, dv, v_l;
  wire signed [20:0] v0, T, s0, a, b;   // Q7.13, 21b
  wire ce_out;
  reg  [31:0] stim [0:K*4-1];
  reg  [20:0] gold [0:K*5-1];
  reg  signed [20:0] pw [0:4];
  integer k, i, nmis, lat; reg signed [20:0] prev0;

  Donatello_Tier dut (.clk(clk), .reset(reset), .clk_enable(clk_enable),
     .s(s), .v(v), .dv(dv), .v_l(v_l), .v0(v0), .T(T), .s0(s0), .a(a), .b(b), .ce_out(ce_out));

  always #62.5 clk = ~clk;              // 8 MHz

  initial begin
    $readmemh(`STIMF, stim); $readmemh(`GOLDF, gold);
    s = stim[0]; v = stim[1]; dv = stim[2]; v_l = stim[3];   // 1o control-step PRIMA del de-assert reset
    reset = 1; repeat (8) @(posedge clk); reset = 0;
    prev0 = v0; lat = 0;                                     // misura LAT: 1o clock in cui v0 cambia
    while (v0 === prev0 && lat < HOLD) begin @(posedge clk); lat = lat + 1; end
    $display("LAT_RTL %0d", lat);
    repeat (HOLD - lat) @(posedge clk);
    nmis = 0; pw[0]=v0; pw[1]=T; pw[2]=s0; pw[3]=a; pw[4]=b;
    for (i=0;i<5;i=i+1) if (pw[i] !== gold[i]) nmis = nmis + 1;
    for (k = 1; k < K; k = k + 1) begin
      s = stim[k*4+0]; v = stim[k*4+1]; dv = stim[k*4+2]; v_l = stim[k*4+3];
      repeat (HOLD) @(posedge clk);
      pw[0]=v0; pw[1]=T; pw[2]=s0; pw[3]=a; pw[4]=b;
      for (i=0;i<5;i=i+1) if (pw[i] !== gold[k*5+i]) nmis = nmis + 1;
    end
    $display("RTLRES nMismatch=%0d n=%0d", nmis, K*5);
    $finish;
  end
endmodule
