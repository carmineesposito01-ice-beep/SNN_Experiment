`timescale 1ns/1ps
// Harness A (Fase B2.0-2a): pilota Donatello_Champion (VHDL generato) con gli stimoli, campiona i 5
// parametri IDM a FINE control-step (uscita settata e stabile) e li confronta col golden. Bit-accurate:
// reg/wire non-signed, il confronto e' `!==` sui bit (== stored-integer complemento a 2 delle .mem).
// `KVAL (control-step) e `HOLD (clock/control-step) arrivano da tb_params.vh, scritto dal runner
// (NON via xvlog -d: l'`=` si perde nel passaggio Git-Bash->.bat -> "Can not find file: <val>").
// I file stim.mem/gold.mem hanno nome FISSO (il runner ce li copia).
`include "tb_params.vh"
module tb_champion_stream;
  localparam integer K    = `KVAL;
  localparam integer HOLD = `HOLD;      // >= latenza RTL (~358); campiona a fine control-step
  reg  clk = 0, reset = 0, clk_enable = 1;
  reg  [31:0] s, v, dv, v_l;            // sfix32_En20 (bit = stored integer)
  wire [20:0] v0, T, s0, a, b;          // sfix21_En13
  wire ce_out;
  reg  [31:0] stim [0:K*4-1];
  reg  [20:0] gold [0:K*5-1];
  reg  [20:0] pw [0:4];
  integer k, i, nmis, firstbad;

  Donatello_Champion dut (.clk(clk), .reset(reset), .clk_enable(clk_enable),
     .s(s), .v(v), .dv(dv), .v_l(v_l),
     .v0(v0), .T(T), .s0(s0), .a(a), .b(b), .ce_out(ce_out));

  always #62.5 clk = ~clk;              // 8 MHz (mezzo periodo 62.5 ns)

  initial begin
    $readmemh("stim.mem", stim);
    $readmemh("gold.mem", gold);
    // presenta il 1o control-step PRIMA di togliere reset (come From Workspace a t=0): tenere gli
    // ingressi a 0 dopo il reset farebbe scattare la logica "prima inferenza" (started) su un ingresso
    // NULLO -> inferenza spuria -> lo stato ricorrente della SNN si desincronizza (params vicini ma sbagliati).
    s = stim[0]; v = stim[1]; dv = stim[2]; v_l = stim[3];
    reset = 1; repeat (8) @(posedge clk); reset = 0;
    nmis = 0; firstbad = -1;
    for (k = 0; k < K; k = k + 1) begin
      if (k > 0) begin                  // k==0 gia' presentato prima del reset-deassert
        s = stim[k*4+0]; v = stim[k*4+1]; dv = stim[k*4+2]; v_l = stim[k*4+3];
      end
      repeat (HOLD) @(posedge clk);     // l'edge-trigger avvia l'inferenza; a fine HOLD e' settata
      pw[0]=v0; pw[1]=T; pw[2]=s0; pw[3]=a; pw[4]=b;
`ifdef DIAG
      if (k < 5) $display("DIAG k=%0d  v0=%h/%h  T=%h/%h  s0=%h/%h  a=%h/%h  b=%h/%h  ce=%b (rtl/gold)",
                          k, v0,gold[k*5+0], T,gold[k*5+1], s0,gold[k*5+2], a,gold[k*5+3], b,gold[k*5+4], ce_out);
`endif
      for (i = 0; i < 5; i = i + 1)
        if (pw[i] !== gold[k*5+i]) begin
          nmis = nmis + 1;
          if (firstbad < 0) firstbad = k;
        end
    end
    $display("RTLRES nMismatch=%0d n=%0d firstbad=%0d", nmis, K*5, firstbad);
    $finish;
  end
endmodule
