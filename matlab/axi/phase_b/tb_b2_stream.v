`timescale 1ns/1ps
// Guida snn_top_b2_flat con le righe di uno .mem: start, attende done, next. 8 MHz (Fclk reale B2).
// Porte reali (da snn_top_b2_flat.vhd): clk, reset, clk_enable, xn[75:0], start, ce_out, params[104:0], done.
// xn impacchettato {xn3,xn2,xn1,xn0}. Il path .mem (__STIM__) e' sostituito dal Tcl (path corto, no spazi).
module tb_b2_stream;
  localparam NROW = 64;                  // inferenze per il SAIF (attivita' sufficiente, sim trattabile)
  reg clk = 0, rst = 0, start = 0;
  reg  [75:0] xn = 0;
  wire [104:0] params;
  wire done, ce_out;
  reg  [18:0] mem [0:NROW*4-1];
  integer r, c0, c1;

  snn_top_b2_flat dut (.clk(clk), .reset(rst), .clk_enable(1'b1),
                       .xn(xn), .start(start), .ce_out(ce_out),
                       .params(params), .done(done));

  always #62.5 clk = ~clk;               // mezzo periodo 62.5 ns -> 8 MHz

  initial begin
    $readmemh("__STIM__", mem);
    rst = 1; repeat (8) @(posedge clk); rst = 0; repeat (2) @(posedge clk);
    for (r = 0; r < NROW; r = r + 1) begin
      xn = {mem[r*4+3], mem[r*4+2], mem[r*4+1], mem[r*4+0]};   // {xn3,xn2,xn1,xn0}
      @(posedge clk); start = 1; @(posedge clk); start = 0;
      c0 = $time;
      while (!done) @(posedge clk);
      c1 = $time;
      if (r == 0) $display("CICLI_INF %0d", (c1 - c0) / 125);
      @(posedge clk);
    end
    $display("STREAM_DONE %0d inferenze", NROW);
    $finish;
  end
endmodule
