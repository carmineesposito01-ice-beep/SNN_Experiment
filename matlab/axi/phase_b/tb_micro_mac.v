`timescale 1ns/1ps
// Clocka micro_mac per molti cicli (1 MAC/ciclo) per il SAIF. Uscita 48-bit.
module tb_micro_mac;
  reg clk = 0, rst = 0;
  wire [47:0] y;
  wire ce_out;
  micro_mac dut (.clk(clk), .reset(rst), .clk_enable(1'b1), .ce_out(ce_out), .y(y));
  always #5 clk = ~clk;                       // 100 MHz
  initial begin
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    repeat (20000) @(posedge clk);
    $display("MICRO_MAC_DONE y=%h", y);
    $finish;
  end
endmodule
