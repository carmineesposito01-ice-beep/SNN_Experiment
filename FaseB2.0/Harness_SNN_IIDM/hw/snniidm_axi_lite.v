`timescale 1 ns / 1 ps
// AXI4-Lite slave per Donatello_SNN_IIDM (controllore car-following COMPLETO, I/O FISICO). Protocollo dal template Vivado
// (identico a matlab/axi/snn_b2_axi_lite.v della Fase B); cambia solo la user logic.
//
// Mappa registri:
//   W 0x00..0x0C = s, v, dv, v_l   (Q?.20, interi con segno a 32 bit)
//   W 0x10 bit0  = COMMIT (fronte di salita)   bit1 = CLOCK GATING abilitato
//   R 0x10 bit0  = done
//   R 0x14..0x24 = v0, T, s0, a, b (Q7.13, 21 bit sign-extended a 32)
//
// Tre scelte di progetto, tutte da FATTI misurati (FaseB2.0/Harness_SNN/results/PROBES_T6B.md):
//  (a) COMMIT SINCRONO. Il Tier e' edge-triggered: se i 4 ingressi arrivassero uno alla volta, il primo cambio
//      lancerebbe un'inferenza su ingressi PARZIALI. I registri AXI sono quindi un BUFFER; i 4 ingressi del Tier
//      (_c) si aggiornano TUTTI INSIEME sul commit -> 1 solo edge -> 1 inferenza per control-step.
//  (b) DONE DA CONTATORE. Il probe P1 ha misurato che `ce_out` del Tier e' un CLOCK-ENABLE sempre alto
//      (1500/1500 cicli), NON un done: usarlo farebbe leggere al PS parametri non pronti. La latenza misurata
//      e' 364 clock (uscite che cambiano a cyc 364/865/1365, passo HOLD=500).
//  (c) CLOCK GATING del Tier via BUFGCE. Duty cycle reale ~0,0073% (364 clk su un control-step di 0,1 s):
//      il design e' fermo per il 99,993% del tempo. Lo STATO (hdl.RAM + flop) si conserva a clock fermo.
//      Il gating e' comandato da un BIT DI REGISTRO, non da un parametro di compilazione: cosi' "gatato" e
//      "non gatato" sono LA STESSA NETLIST e il confronto di potenza isola l'effetto del gating.
module snniidm_axi_lite #
(
  parameter integer C_S_AXI_DATA_WIDTH = 32,
  parameter integer C_S_AXI_ADDR_WIDTH = 6,
  // Attesa dal commit prima di latchare i parametri. MISURATA col probe di timing (non dedotta):
  //   commit @446 -> uscita valida @811 (Delta=365) ; commit @852 -> @1217 (Delta=365).
  // Il latch avviene a commit + LAT_CLK + 1 = commit + 371 -> 6 clock di margine oltre il valore misurato.
  // ⚠️ Latchare esattamente a Delta=365 cattura il valore PRECEDENTE (il non-blocking legge il pre-fronte,
  //    e l'uscita si aggiorna su QUEL fronte): e' l'off-by-one che dava 100% di mismatch al primo giro.
  //    Il margine non costa nulla: il control-step reale e' 0,1 s (milioni di clock).
  parameter integer LAT_CLK            = 560
)
(
  input  wire S_AXI_ACLK,
  input  wire S_AXI_ARESETN,
  input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_AWADDR,
  input  wire [2:0] S_AXI_AWPROT,
  input  wire S_AXI_AWVALID,
  output wire S_AXI_AWREADY,
  input  wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_WDATA,
  input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
  input  wire S_AXI_WVALID,
  output wire S_AXI_WREADY,
  output wire [1:0] S_AXI_BRESP,
  output wire S_AXI_BVALID,
  input  wire S_AXI_BREADY,
  input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_ARADDR,
  input  wire [2:0] S_AXI_ARPROT,
  input  wire S_AXI_ARVALID,
  output wire S_AXI_ARREADY,
  output wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_RDATA,
  output wire [1:0] S_AXI_RRESP,
  output wire S_AXI_RVALID,
  input  wire S_AXI_RREADY
);
  reg [C_S_AXI_ADDR_WIDTH-1:0] axi_awaddr, axi_araddr;
  reg axi_awready, axi_wready, axi_bvalid, axi_arready, axi_rvalid;
  reg [1:0] axi_bresp, axi_rresp;
  localparam integer ADDR_LSB = (C_S_AXI_DATA_WIDTH/32) + 1;   // 2
  localparam integer OPT_MEM_ADDR_BITS = 3;                    // 16 registri
  reg [C_S_AXI_DATA_WIDTH-1:0] slv_reg0, slv_reg1, slv_reg2, slv_reg3, slv_reg4;
  integer byte_index;
  reg [1:0] state_write, state_read;
  localparam Idle=2'b00, Waddr=2'b10, Wdata=2'b11, Raddr=2'b10, Rdata=2'b11;

  assign S_AXI_AWREADY = axi_awready;
  assign S_AXI_WREADY  = axi_wready;
  assign S_AXI_BRESP   = axi_bresp;
  assign S_AXI_BVALID  = axi_bvalid;
  assign S_AXI_ARREADY = axi_arready;
  assign S_AXI_RRESP   = axi_rresp;
  assign S_AXI_RVALID  = axi_rvalid;

  // ---------------- write FSM (invariata dal template) ----------------
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin
      axi_awready<=0; axi_wready<=0; axi_bvalid<=0; axi_bresp<=0; axi_awaddr<=0; state_write<=Idle;
    end else begin
      case (state_write)
        Idle: begin axi_awready<=1; axi_wready<=1; state_write<=Waddr; end
        Waddr: begin
          if (S_AXI_AWVALID && axi_awready) begin
            axi_awaddr<=S_AXI_AWADDR;
            if (S_AXI_WVALID) begin axi_awready<=1; state_write<=Waddr; axi_bvalid<=1; end
            else begin axi_awready<=0; state_write<=Wdata; if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0; end
          end else if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0;
        end
        Wdata: begin
          if (S_AXI_WVALID) begin state_write<=Waddr; axi_bvalid<=1; axi_awready<=1; end
          else if (S_AXI_BREADY&&axi_bvalid) axi_bvalid<=0;
        end
        default: state_write<=Idle;
      endcase
    end
  end

  // ---------------- write register logic (invariata dal template) ----------------
  wire [OPT_MEM_ADDR_BITS:0] wr_idx =
      (S_AXI_AWVALID) ? S_AXI_AWADDR[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB]
                      : axi_awaddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB];
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin slv_reg0<=0; slv_reg1<=0; slv_reg2<=0; slv_reg3<=0; slv_reg4<=0; end
    else if (S_AXI_WVALID) begin
      case (wr_idx)
        4'd0: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg0[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd1: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg1[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd2: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg2[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd3: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg3[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        4'd4: for (byte_index=0;byte_index<4;byte_index=byte_index+1) if (S_AXI_WSTRB[byte_index]) slv_reg4[byte_index*8 +: 8]<=S_AXI_WDATA[byte_index*8 +: 8];
        default: ;
      endcase
    end
  end

  // ---------------- read FSM (invariata dal template) ----------------
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin axi_arready<=0; axi_rvalid<=0; axi_rresp<=0; state_read<=Idle; end
    else begin
      case (state_read)
        Idle: begin state_read<=Raddr; axi_arready<=1; end
        Raddr: if (S_AXI_ARVALID&&axi_arready) begin state_read<=Rdata; axi_araddr<=S_AXI_ARADDR; axi_rvalid<=1; axi_arready<=0; end
        Rdata: if (S_AXI_RVALID&&S_AXI_RREADY) begin axi_rvalid<=0; axi_arready<=1; state_read<=Raddr; end
        default: state_read<=Idle;
      endcase
    end
  end

  // ================= user logic: Donatello_SNN_IIDM =================
  reg  signed [31:0] s_c, v_c, dv_c, vl_c;      // ingressi COMMITTED (cambiano tutti insieme)
  reg  [9:0]   lat_cnt;
  reg          busy, done_lat;
  reg  signed [12:0] accel_lat;
  reg          reg4_d0;
  always @(posedge S_AXI_ACLK) reg4_d0 <= slv_reg4[0];
  wire commit = slv_reg4[0] & ~reg4_d0;          // (a) fronte di salita del bit di controllo

  // (c) clock gating: CE alto solo mentre il DUT lavora; bit1=0 -> clock sempre attivo (riferimento)
  wire gate_mode = slv_reg4[1];
  wire dut_ce   = gate_mode ? (commit | busy) : 1'b1;
  wire clk_dut;
  BUFGCE u_gate (.O(clk_dut), .CE(dut_ce), .I(S_AXI_ACLK));

  // Il DUT resta IN RESET finche' non arriva il primo commit. Senza questo, all'uscita dal reset i suoi
  // ingressi passano da indefinito a 0: l'edge-detector vede un fronte e lancia un'inferenza SPURIA con
  // ingressi nulli, che avanza lo stato della rete (hdl.RAM) e disallinea TUTTE le inferenze successive
  // dal golden. Misurato: uscita che cambia a cyc 379 con reset rilasciato a 16 (16+364), cioe' PRIMA
  // dell'inferenza del primo commit. Nel deployment reale e' anche il comportamento corretto:
  // l'acceleratore sta fermo finche' il PS non gli da' lavoro.
  reg started;
  always @(posedge S_AXI_ACLK)
    if (!S_AXI_ARESETN) started <= 1'b0;
    else if (commit)    started <= 1'b1;
  wire dut_rst = ~S_AXI_ARESETN | ~started;

  wire signed [12:0] w_accel;                    // sfix13_En8 (Q4.8): UNA uscita, non 5 params
  wire w_ceout;
  Donatello_SNN_IIDM u_dut (
    .clk(clk_dut), .reset(dut_rst), .clk_enable(1'b1),
    .s(s_c), .v(v_c), .dv(dv_c), .v_l(vl_c),
    .accel(w_accel), .ce_out(w_ceout)
  );

  // (b) done da CONTATORE sul clock NON gatato (deve contare anche se il Tier fosse fermo)
  always @(posedge S_AXI_ACLK) begin
    if (!S_AXI_ARESETN) begin
      s_c<=0; v_c<=0; dv_c<=0; vl_c<=0;
      lat_cnt<=0; busy<=1'b0; done_lat<=1'b0; accel_lat<=0;
    end else begin
      if (commit) begin
        s_c <= slv_reg0; v_c <= slv_reg1; dv_c <= slv_reg2; vl_c <= slv_reg3;   // (a) tutti insieme
        lat_cnt  <= 0;
        busy     <= 1'b1;
        done_lat <= 1'b0;
      end else if (busy) begin
        if (lat_cnt >= LAT_CLK[9:0]) begin
          accel_lat  <= w_accel;
          done_lat   <= 1'b1;
          busy       <= 1'b0;
        end else begin
          lat_cnt <= lat_cnt + 1'b1;
        end
      end
    end
  end

  // ---------------- read mux ----------------
  reg [C_S_AXI_DATA_WIDTH-1:0] rd_data;
  wire [OPT_MEM_ADDR_BITS:0] rd_idx = axi_araddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB];
  always @(*) begin
    case (rd_idx)
      4'd0: rd_data = slv_reg0;
      4'd1: rd_data = slv_reg1;
      4'd2: rd_data = slv_reg2;
      4'd3: rd_data = slv_reg3;
      4'd4: rd_data = {31'd0, done_lat};
      4'd5: rd_data = {{19{accel_lat[12]}}, accel_lat};   // accel sfix13_En8 -> 32 bit con segno
      // 4'd6..9: liberi (il composto ha UNA sola uscita, non 5 params)
      default: rd_data = 0;
    endcase
  end
  assign S_AXI_RDATA = rd_data;
endmodule
