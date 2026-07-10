function raw5 = snn_tick_probe(xn, fcw_all, Uw_all, tlr, bth_all, tj_all, Wout_all) %#codegen
%SNN_TICK_PROBE  [B2 S1] Probe di SERIALIZZAZIONE: 1 tick con loop neuroni TOP-LEVEL
%  (NON annidato -> coder.hdl.loopspec('stream') puo' applicarsi) + stato V/fatigue in RAM.
%  Scopo: verificare se HDL Coder produce 1 LANE condivisa + RAM (serializzato) invece di
%  srotolare 32 lane. Metrica: Multipliers ~= 22 (serializzato) vs ~= 704 (unrolled).
%  Pesi passati come DATO (variante B2). NON bit-exact: test strutturale.
  T = snn_types('fixed', 13);
  hidden = 32; sh = 3;
  persistent V fatigue inited
  if isempty(inited)
    V = zeros(hidden, 1, 'like', T.V);
    fatigue = zeros(hidden, 1, 'like', T.fatigue);
    inited = true;
  end

  wacc = cast(zeros(5, 1), 'like', T.raw);
  coder.hdl.loopspec('stream');          % loop TOP-LEVEL -> streamabile
  for i = 1:hidden
    Ii = cast(0, 'like', T.accw);
    for j = 1:4
      Ii(:) = Ii + cast(fcw_all(i, j) * xn(j), 'like', T.accw);
    end
    reci = cast(0, 'like', T.accw);
    for r = 1:16
      reci(:) = reci + cast(Uw_all(i, r) * tlr(r), 'like', T.accw);
    end
    Vi  = cast(V(i) - bitsra(V(i), sh), 'like', T.V) + cast(Ii + reci, 'like', T.V);
    eth = cast(bth_all(i), 'like', T.V) + cast(max(fatigue(i), cast(0, 'like', T.fatigue)), 'like', T.V);
    si  = cast(Vi >= eth, 'like', T.V);
    fatigue(i) = cast(fatigue(i) - bitsra(fatigue(i), sh), 'like', T.fatigue) + cast(si, 'like', T.fatigue) * tj_all(i);
    V(i) = Vi - cast(si, 'like', T.V) * eth;
    for o = 1:5
      if si > 0
        wacc(o) = wacc(o) + Wout_all(o, i);
      end
    end
  end
  raw5 = wacc;
end
