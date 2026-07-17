`timescale 1ns/1ps
// Harness B.1 (Fase B2.0-2a-M2): pilota Donatello_ACC_IIDM_M (VHDL generato) con gli stimoli fisici,
// campiona l'accel a FINE control-step e la confronta col golden FEDELE (acciidm_m_traj). Gemello di
// tb_champion_stream ma con 1 uscita (accel, Q4.8, 13b). `KVAL/`HOLD da tb_params.vh (scritto dal runner).
`include "tb_params.vh"
module tb_acciidm_m_open;
  localparam integer K    = `KVAL;
  localparam integer HOLD = `HOLD;      // >= latenza RTL (~358); campiona a fine control-step
  reg  clk = 0, reset = 0, clk_enable = 1;
  reg  [31:0] s, v, dv, v_l;            // sfix32_En20
  wire [12:0] accel;                    // sfix13_En8 (Q4.8)
  wire ce_out;
  reg  [31:0] stim [0:K*4-1];
  reg  [12:0] gold [0:K-1];
  reg  [12:0] pw;
  integer k, nmis, firstbad;

  Donatello_ACC_IIDM_M dut (.clk(clk), .reset(reset), .clk_enable(clk_enable),
     .s(s), .v(v), .dv(dv), .v_l(v_l), .accel(accel), .ce_out(ce_out));

  always #62.5 clk = ~clk;              // 8 MHz

  initial begin
    $readmemh("stim.mem", stim);
    $readmemh("gold.mem", gold);
    // presenta il 1o control-step PRIMA di togliere reset (niente fase a ingresso 0 -> inferenza spuria)
    s = stim[0]; v = stim[1]; dv = stim[2]; v_l = stim[3];
    reset = 1; repeat (8) @(posedge clk); reset = 0;
    nmis = 0; firstbad = -1;
    for (k = 0; k < K; k = k + 1) begin
      if (k > 0) begin
        s = stim[k*4+0]; v = stim[k*4+1]; dv = stim[k*4+2]; v_l = stim[k*4+3];
      end
      repeat (HOLD) @(posedge clk);
      pw = accel;
      if (pw !== gold[k]) begin
        nmis = nmis + 1;
        if (firstbad < 0) firstbad = k;
      end
    end
    $display("RTLRES nMismatch=%0d n=%0d firstbad=%0d", nmis, K, firstbad);
    $finish;
  end
endmodule
