`timescale 1ns/1ps
// Clocka micro_ac per molti cicli (1 shift-add/ciclo) per il SAIF. Porte: clk/reset/clk_enable/ce_out/y.
module tb_micro_ac;
  reg clk = 0, rst = 0;
  wire [31:0] y;
  wire ce_out;
  micro_ac dut (.clk(clk), .reset(rst), .clk_enable(1'b1), .ce_out(ce_out), .y(y));
  always #5 clk = ~clk;                       // 100 MHz
  initial begin
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    repeat (20000) @(posedge clk);            // 20k op
    $display("MICRO_AC_DONE y=%h", y);
    $finish;
  end
endmodule
