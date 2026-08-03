function [Vnew, fat_new, si, wcontrib] = snn_neuron_b2(Vp, fatp, xtap, tlr, fcw, Uw, bth, tj, Wout) %#codegen
%SNN_NEURON_B2  [B2 SPIKE] Una lane-neurone della variante B2 (pesi = DATO da BRAM ->
%  MAC vero, NON shift baked). Prototipo STRUTTURALE per stimare l'area dell'unita'
%  ripetuta: rank=16 (Donatello), 4 tap sinaptici, 5 uscite readout. Tipi fixed reali
%  (snn_types f=13). NON bit-exact al champion: serve a misurare LUT/DSP di UNA lane,
%  da cui stimare il B2 completo = lane + BRAM(pesi/stato) + controllo.
  T  = snn_types('fixed', 13);
  sh = 3;                                          % leak bit-shift (leak_div = 8)

  % --- corrente sinaptica: MAC su 4 tap (peso = dato) ---
  Ii = cast(0, 'like', T.accw);
  for j = 1:4
    Ii(:) = Ii + cast(fcw(j) * xtap(j), 'like', T.accw);
  end
  % --- ricorrenza: MAC su rank = 16 ---
  reci = cast(0, 'like', T.accw);
  for r = 1:16
    reci(:) = reci + cast(Uw(r) * tlr(r), 'like', T.accw);
  end

  % --- membrana (leaky bit-shift) + input ---
  Vi = cast(Vp - bitsra(Vp, sh), 'like', T.V) + cast(Ii + reci, 'like', T.V);
  % --- soglia + spike hard >= + fatigue leaky + soft reset ---
  eth     = cast(bth, 'like', T.V) + cast(max(fatp, cast(0, 'like', T.fatigue)), 'like', T.V);
  si      = cast(Vi >= eth, 'like', T.V);
  fat_new = cast(fatp - bitsra(fatp, sh), 'like', T.fatigue) + cast(si, 'like', T.fatigue) * tj;
  Vnew    = Vi - cast(si, 'like', T.V) * eth;

  % --- readout gated (si in {0,1}) ---
  wcontrib = cast(zeros(5, 1), 'like', T.raw);
  for o = 1:5
    if si > 0
      wcontrib(o) = cast(Wout(o), 'like', T.raw);
    end
  end
end
