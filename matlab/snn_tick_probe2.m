function raw5 = snn_tick_probe2(xn, tlr) %#codegen
%SNN_TICK_PROBE2  [B2 S2a] Probe serializzazione+RAM con IGIENE: pesi INTERNI (coder.const ROM,
%  non I/O) + init stato SCALARIZZATO (coder.nullcopy + loop, niente zeros whole-array) + loop
%  neuroni TOP-LEVEL. Domanda: l'auto-RAM-mapping di V/fatigue regge ora? (0 warning RAM = si').
  T = snn_types('fixed', 13);
  hidden = 32; sh = 3;

  % pesi come COSTANTI interne (ROM) - valori dummy: qui conta solo se V/fatigue mappano in RAM
  fcw  = coder.const(cast(0.5  * ones(32, 4),  'like', T.w));
  Uw   = coder.const(cast(0.25 * ones(32, 16), 'like', T.w));
  bth  = coder.const(cast(1.0  * ones(32, 1),  'like', T.V));
  tj   = coder.const(cast(0.1  * ones(32, 1),  'like', T.fatigue));
  Wout = coder.const(cast(0.3  * ones(5, 32),  'like', T.raw));

  persistent V fatigue inited
  if isempty(inited)
    V       = coder.nullcopy(zeros(hidden, 1, 'like', T.V));
    fatigue = coder.nullcopy(zeros(hidden, 1, 'like', T.fatigue));
    for i = 1:hidden                       % init SCALARE (evita non-scalar sub-matrix access)
      V(i)       = cast(0, 'like', T.V);
      fatigue(i) = cast(0, 'like', T.fatigue);
    end
    inited = true;
  end

  wacc = cast(0, 'like', T.raw);
  wacc = repmat(wacc, 5, 1);
  % (loopspec rimosso: test se la RAM sequenziale serializza da sola, senza conflitto)
  for i = 1:hidden
    Ii = cast(0, 'like', T.accw);
    for j = 1:4
      Ii(:) = Ii + cast(fcw(i, j) * xn(j), 'like', T.accw);
    end
    reci = cast(0, 'like', T.accw);
    for r = 1:16
      reci(:) = reci + cast(Uw(i, r) * tlr(r), 'like', T.accw);
    end
    Vi  = cast(V(i) - bitsra(V(i), sh), 'like', T.V) + cast(Ii + reci, 'like', T.V);
    eth = cast(bth(i), 'like', T.V) + cast(max(fatigue(i), cast(0, 'like', T.fatigue)), 'like', T.V);
    si  = cast(Vi >= eth, 'like', T.V);
    fatigue(i) = cast(fatigue(i) - bitsra(fatigue(i), sh), 'like', T.fatigue) + cast(si, 'like', T.fatigue) * tj(i);
    V(i) = Vi - cast(si, 'like', T.V) * eth;
    for o = 1:5
      if si > 0
        wacc(o) = wacc(o) + Wout(o, i);
      end
    end
  end
  raw5 = wacc;
end
