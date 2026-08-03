`timescale 1ns/1ps
// PROBE P1 (T6b) — semantica di `ce_out` del Tier: e' un "done" (1 impulso per inferenza) o un clock-enable
// che pulsa in continuazione? Decide se il wrapper AXI puo' usarlo come valid o se serve un contatore di latenza.
// Stampa: i cicli in cui ce_out e' alto e i cicli in cui l'uscita v0 cambia, su 3 control-step.
module probe_ceout_tb;
  localparam integer HOLD = 500;
  reg clk = 0, reset = 0, clk_enable = 1;
  reg  signed [31:0] s, v, dv, v_l;
  wire signed [20:0] v0, T, s0, a, b;
  wire ce_out;
  integer cyc, k, i, nce, nchg;
  reg signed [20:0] pv0;

  Donatello_Tier dut (.clk(clk), .reset(reset), .clk_enable(clk_enable),
    .s(s), .v(v), .dv(dv), .v_l(v_l), .v0(v0), .T(T), .s0(s0), .a(a), .b(b), .ce_out(ce_out));

  always #62.5 clk = ~clk;

  initial begin
    cyc = 0; nce = 0; nchg = 0;
    // ingressi fisici plausibili in Q?.20: s=30 m, v=20 m/s, dv=-1 m/s, v_l=21 m/s
    s = 30 <<< 20; v = 20 <<< 20; dv = -(1 <<< 20); v_l = 21 <<< 20;
    reset = 1; repeat (8) @(posedge clk); reset = 0;
    pv0 = v0;
    for (k = 0; k < 3; k = k + 1) begin
      s = (30 + k) <<< 20;                      // nuovo control-step (cambio d'ingresso = edge)
      for (i = 0; i < HOLD; i = i + 1) begin
        @(posedge clk);
        cyc = cyc + 1;
        if (ce_out === 1'b1) begin
          nce = nce + 1;
          if (nce <= 12) $display("P1 CEOUT   @cyc %0d (step %0d)", cyc, k);
        end
        if (v0 !== pv0) begin
          nchg = nchg + 1;
          $display("P1 PARAMCHG @cyc %0d (step %0d)", cyc, k);
          pv0 = v0;
        end
      end
    end
    $display("P1 TOTALI: ce_out alto %0d volte su %0d cicli | cambi di v0 = %0d (attesi 3 = 1/control-step)",
             nce, cyc, nchg);
    if (nce == 3)      $display("P1 VERDETTO: ce_out = DONE (1 impulso per inferenza) -> usabile come valid");
    else if (nce > 50) $display("P1 VERDETTO: ce_out = CLOCK-ENABLE continuo -> NON usabile come done, serve contatore di latenza");
    else               $display("P1 VERDETTO: ce_out ha %0d impulsi -> semantica da interpretare (vedi elenco sopra)", nce);
    $finish;
  end
endmodule
