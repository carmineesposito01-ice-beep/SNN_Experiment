function wout = snn_ram_probe(xn, tlr) %#codegen
%SNN_RAM_PROBE  [B2 hdl.RAM] Probe cycle-based: 1 neurone per chiamata (1 clock).
%  V/fatigue in hdl.RAM (Dual port), pesi in ROM (coder.const), pipeline 2-stadi
%  (read -> compute -> write) per la latenza di lettura RAM (1 ciclo). I neuroni sono
%  indipendenti -> il pipeline preserva la correttezza. Scopo: provare che hdl.RAM
%  serializza in HW = 1 LANE + RAM (synth piccolo). Output: readout accumulato (5x1).
  T = snn_types('fixed', 13);
  sh = 3;
  persistent Vram fatram ctr ...
             s1_valid s1_ctr s1_xn s1_tlr ...
             s2_valid s2_ctr s2_V s2_fat wacc inited
  if isempty(inited)
    Vram   = hdl.RAM('RAMType', 'Dual port');
    fatram = hdl.RAM('RAMType', 'Dual port');
    ctr = uint8(0);
    s1_valid = false; s1_ctr = uint8(0);
    s1_xn = cast(zeros(4, 1), 'like', T.V); s1_tlr = cast(zeros(16, 1), 'like', T.V);
    s2_valid = false; s2_ctr = uint8(0);
    s2_V = cast(0, 'like', T.V); s2_fat = cast(0, 'like', T.fatigue);
    wacc = cast(zeros(5, 1), 'like', T.raw);
    inited = true;
  end

  % pesi in ROM (coder.const) indicizzati dal contatore neurone
  % pesi VARIATI (non-uniformi, non-po2) -> ROM reale + moltiplicatori reali (rappresentativo)
  fcw  = coder.const(cast(0.1  + 0.6 * reshape(mod(0:127, 11), 32, 4)  / 11, 'like', T.w));
  Uw   = coder.const(cast(-0.4 + 0.8 * reshape(mod(0:511, 13), 32, 16) / 13, 'like', T.w));
  bth  = coder.const(cast(0.5  + mod((0:31).', 7) / 14,  'like', T.V));
  tj   = coder.const(cast(0.05 + mod((0:31).', 5) / 50, 'like', T.fatigue));
  Wout = coder.const(cast(-0.3 + 0.6 * reshape(mod(0:159, 9), 5, 32) / 9, 'like', T.raw));

  % --- RAM: scrivi il risultato dello stadio 2 (calcolato scorsa chiamata), leggi ctr ---
  wrEn = s2_valid;
  [~, Vread]   = Vram(s2_V,   s2_ctr, wrEn, ctr);
  [~, fatread] = fatram(s2_fat, s2_ctr, wrEn, ctr);
  % Vread/fatread = stato del neurone la cui lettura fu emessa la scorsa chiamata (s1_ctr)

  % --- STADIO 1: calcola il neurone s1_ctr con Vread/fatread ---
  if s1_valid
    i = double(s1_ctr) + 1;
    Ii = cast(0, 'like', T.accw);
    for j = 1:4
      Ii(:) = Ii + cast(fcw(i, j) * s1_xn(j), 'like', T.accw);
    end
    reci = cast(0, 'like', T.accw);
    for r = 1:16
      reci(:) = reci + cast(Uw(i, r) * s1_tlr(r), 'like', T.accw);
    end
    Vi  = cast(Vread - bitsra(Vread, sh), 'like', T.V) + cast(Ii + reci, 'like', T.V);
    eth = cast(bth(i), 'like', T.V) + cast(max(fatread, cast(0, 'like', T.fatigue)), 'like', T.V);
    si  = cast(Vi >= eth, 'like', T.V);
    fatn = cast(cast(fatread - bitsra(fatread, sh), 'like', T.fatigue) + cast(si, 'like', T.fatigue) * tj(i), 'like', T.fatigue);
    Vn   = cast(Vi - cast(si, 'like', T.V) * eth, 'like', T.V);
    for o = 1:5
      if si > 0
        wacc(o) = cast(wacc(o) + Wout(o, i), 'like', T.raw);
      end
    end
    s2_valid = true; s2_ctr = s1_ctr; s2_V = Vn; s2_fat = fatn;
  else
    s2_valid = false;
  end

  % --- STADIO 0: emetti lettura per ctr, latcha input per lo stadio 1 ---
  s1_valid = true; s1_ctr = ctr; s1_xn = xn; s1_tlr = tlr;

  if ctr >= uint8(31), ctr = uint8(0); else, ctr = ctr + uint8(1); end
  wout = wacc;
end
