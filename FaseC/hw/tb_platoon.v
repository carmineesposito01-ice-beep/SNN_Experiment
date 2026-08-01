`timescale 1ns/1ps
`include "p2_params.vh"        // `KVAL, `NVEH, `HOLDV, `SCENF, `INITF, `ACCF, `OUTF
// -----------------------------------------------------------------------------------------------
// P2 -- plotone in RTL. N veicoli in fila, ciascuno col PROPRIO Donatello_SNN_IIDM.
//
// DUE MODALITA', UN SOLO PLANT:
//   `PLATOON_PAR definito  -> le accelerazioni si RIGIOCANO da plat_acc_<i>.mem (nessun DUT).
//                             Prova il plant da solo: se le traiettorie divergono, il difetto
//                             e' nel plant e non ha niente a che vedere con l'acceleratore.
//   altrimenti             -> N DUT in retroazione: l'anello chiuso vero.
//
// Il plant e' scritto UNA VOLTA e le due modalita' lo condividono. Se fossero due copie,
// PLATOON-PAR proverebbe un plant e l'anello ne userebbe un altro -- e la prova non varrebbe.
//
// Il plant e' quello del PLOTONE (utils/platoon_eval.simulate_platoon), che lavora sulle
// POSIZIONI, non l'integrazione del gap di qz_cl_sim:
//     gap[i] = xlead[i] - x[i] - VEH_LEN
//     v[i]   = max(0, v[i] + a[i]*DT);   x[i] = x[i] + v[i]*DT
//
// ⚠️ Ordine: TUTTI i gap e i dv si calcolano dallo stato VECCHIO, poi TUTTI i veicoli si
// aggiornano. In numpy e' implicito nella vettorizzazione; qui, con un ciclo, aggiornare
// mentre si legge darebbe a ogni veicolo lo stato gia' avanzato di quello davanti -- una
// traiettoria plausibile e diversa.
// -----------------------------------------------------------------------------------------------
module tb_platoon;
  localparam integer K    = `KVAL;
  localparam integer N    = `NVEH;
  localparam integer HOLD = `HOLDV;

  reg [63:0] leadm[0:K-1], initm[0:3];
`ifdef PLATOON_PAR
  reg [63:0] accm[0:K*N-1];
`endif

  real x[0:N-1], v[0:N-1], a_out[0:N-1];
  real x_old[0:N-1], v_old[0:N-1];
  real gap[0:N-1], dvv[0:N-1], vlead[0:N-1];
  real v_set, gap_eq, VEH_LEN, DT, x_head_leader;
  integer t, i, fo, collided;

  reg clk = 0, reset = 1, ce = 1;
  reg  [31:0] s_in[0:N-1], v_in[0:N-1], dv_in[0:N-1], vl_in[0:N-1];
  wire [12:0] accel[0:N-1];
  wire        ce_out[0:N-1];

  always #5 clk = ~clk;

  // FLOOR a 2^-20: la convenzione del progetto (fi(...,'Floor')).
  function [31:0] toq(input real z);
    begin toq = $rtoi($floor(z * 1048576.0)); end
  endfunction

`ifndef PLATOON_PAR
  genvar gi;
  generate
    for (gi = 0; gi < N; gi = gi + 1) begin : veh
      Donatello_SNN_IIDM dut(.clk(clk), .reset(reset), .clk_enable(ce),
                             .s(s_in[gi]), .v(v_in[gi]), .dv(dv_in[gi]), .v_l(vl_in[gi]),
                             .ce_out(ce_out[gi]), .accel(accel[gi]));
    end
  endgenerate
`endif

  // ---------------------------------------------------------------- il plant, in un posto solo
  task calcola_ingressi;                 // stato VECCHIO -> gap, dv, vlead di tutti i veicoli
    begin
      for (i = 0; i < N; i = i + 1) begin
        x_old[i] = x[i]; v_old[i] = v[i];
      end
      for (i = 0; i < N; i = i + 1) begin
        vlead[i] = (i == 0) ? $bitstoreal(leadm[t])       : v_old[i-1];
        gap[i]   = ((i == 0) ? x_head_leader : x_old[i-1]) - x_old[i] - VEH_LEN;
        dvv[i]   = v_old[i] - vlead[i];
      end
    end
  endtask

  // ⚠️ MISURATO, non supposto: nel motore di riferimento `_accel` torna da torch in float32, e
  // numpy tiene il prodotto `acc * DT` in float32 (uno scalare Python non promuove un array
  // float32). L'incremento di velocita' del plotone e' quindi in SINGOLA precisione, mentre
  // l'anello chiuso (qz_cl_sim, plant_ps) lavora in doppia.
  //
  // Qui si riproduce, non si corregge: P2 verifica che l'RTL riproduca cio' che P1 HA MISURATO.
  // Ignorarlo dava uno scarto di 2,79e-10 al primo passo, che si accumula a 2,8e-6 su 600 --
  // piccolo, ma sistematico, e mascherarlo con una tolleranza nasconderebbe la classe di
  // difetti che questo cancello esiste per trovare.
  function real f32(input real z);
    shortreal s;
    begin s = z; f32 = s; end
  endfunction

  task integra;                          // accelerazioni -> nuovo stato
    real vnew;
    begin
      for (i = 0; i < N; i = i + 1) begin
        vnew = v[i] + f32(a_out[i] * DT);
        if (vnew < 0.0) vnew = 0.0;
        v[i] = vnew;
        x[i] = x[i] + vnew * DT;         // con la v NUOVA
        if (gap[i] <= 0.0) collided = 1;
      end
      x_head_leader = x_head_leader + $bitstoreal(leadm[t]) * DT;
    end
  endtask

  initial begin
    $readmemh(`SCENF, leadm); $readmemh(`INITF, initm);
`ifdef PLATOON_PAR
    $readmemh(`ACCF, accm);
`endif
    v_set   = $bitstoreal(initm[0]); gap_eq = $bitstoreal(initm[1]);
    VEH_LEN = $bitstoreal(initm[2]); DT     = $bitstoreal(initm[3]);

    for (i = 0; i < N; i = i + 1) begin
      x[i] = -1.0 * i * (gap_eq + VEH_LEN);
      v[i] = v_set;
    end
    x_head_leader = gap_eq + VEH_LEN;
    collided = 0;

    fo = $fopen(`OUTF, "w");
    if (fo == 0) begin $display("P2-FATAL: impossibile aprire %s", `OUTF); $finish; end

`ifndef PLATOON_PAR
    // Il primo control-step si presenta PRIMA del rilascio del reset: senza, all'uscita dal
    // reset gli ingressi passerebbero da indefinito a 0 e il rilevatore di fronte lancerebbe
    // un'inferenza SPURIA che avanza lo stato della rete (trappola gia' pagata in T6b).
    t = 0; calcola_ingressi;
    for (i = 0; i < N; i = i + 1) begin
      s_in[i] = toq(gap[i]); v_in[i] = toq(v_old[i]);
      dv_in[i] = toq(dvv[i]); vl_in[i] = toq(vlead[i]);
    end
    repeat (8) @(posedge clk); reset = 0;
`endif

    for (t = 0; t < K; t = t + 1) begin
      calcola_ingressi;
`ifdef PLATOON_PAR
      for (i = 0; i < N; i = i + 1) a_out[i] = $bitstoreal(accm[t*N + i]);
`else
      for (i = 0; i < N; i = i + 1) begin
        s_in[i] = toq(gap[i]); v_in[i] = toq(v_old[i]);
        dv_in[i] = toq(dvv[i]); vl_in[i] = toq(vlead[i]);
      end
      repeat (HOLD) @(posedge clk);
      for (i = 0; i < N; i = i + 1) a_out[i] = $itor($signed(accel[i])) / 256.0;
`endif

      for (i = 0; i < N; i = i + 1)
        $fwrite(fo, "%0d %0d %h %h %h %h\n", t, i,
                $realtobits(gap[i]), $realtobits(v_old[i]),
                $realtobits(x_old[i]), $realtobits(a_out[i]));

      integra;
    end

    $fwrite(fo, "END %0d %0d\n", K, collided);
    $fclose(fo);
    $display("P2RES K=%0d N=%0d collided=%0d", K, N, collided);
    $finish;
  end
endmodule
