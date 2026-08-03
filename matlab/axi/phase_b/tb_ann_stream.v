`timescale 1ns/1ps
// Guida ann_mlp_flat con lo stimolo: start, attende valid (~1312 cicli/inf), next. 8 MHz (come B2).
module tb_ann_stream;
  localparam NROW = 16;
  reg clk = 0, rst = 0, start = 0;
  reg  [75:0] xn = 0;
  wire [104:0] out_flat;
  wire valid, ce_out;
  reg  [18:0] mem [0:NROW*4-1];
  integer r, c0, c1;

  ann_mlp_flat dut (.clk(clk), .reset(rst), .clk_enable(1'b1), .xn(xn), .start(start),
                    .ce_out(ce_out), .out_flat(out_flat), .valid(valid));

  always #62.5 clk = ~clk;               // 8 MHz

  initial begin
    $readmemh("__STIM__", mem);
    rst = 1; repeat (8) @(posedge clk); rst = 0; repeat (2) @(posedge clk);
    for (r = 0; r < NROW; r = r + 1) begin
      xn = {mem[r*4+3], mem[r*4+2], mem[r*4+1], mem[r*4+0]};   // {xn3,xn2,xn1,xn0}
      @(posedge clk); start = 1; @(posedge clk); start = 0;
      c0 = $time;
      while (!valid) @(posedge clk);
      c1 = $time;
      if (r == 0) $display("CICLI_INF %0d", (c1 - c0) / 125);
      @(posedge clk);
    end
    $display("ANN_STREAM_DONE %0d inferenze", NROW);
    $finish;
  end
endmodule
