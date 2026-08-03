// PROBE P2 (T6b) — wrapper Verilog MINIMO che istanzia il DUT VHDL: verifica che Vivado accetti la
// gerarchia mixed-language in SINTESI (in simulazione e' gia' provato dal TB di T6a).
module probe_wrap (
  input  wire        clk,
  input  wire        reset,
  input  wire        ce,
  input  wire signed [31:0] s,
  input  wire signed [31:0] v,
  input  wire signed [31:0] dv,
  input  wire signed [31:0] vl,
  output wire signed [20:0] p0, p1, p2, p3, p4,
  output wire        ceo
);
  Donatello_Tier u_tier (
    .clk(clk), .reset(reset), .clk_enable(ce),
    .s(s), .v(v), .dv(dv), .v_l(vl),
    .v0(p0), .T(p1), .s0(p2), .a(p3), .b(p4), .ce_out(ceo)
  );
endmodule
