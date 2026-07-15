function [params, done] = snn_top_b2(xn, start) %#codegen
%SNN_TOP_B2  [B2] Top Donatello deployabile: SNN(FSM B2) -> decode.
%  xn[4] normalizzato (fi Q5.13, il PS fa il normalize in SW float) + start
%  -> params[5] fisici IDM + done. Streaming: start=1 avvia una control-step;
%  done=1 quando params e' pronto (~340 clock dopo). decode combinatorio (LUT sigma).
%  Nota: normalize NON in HDL (1 LSB di xn flippa spike -> errore amplificato; il PS
%  normalizza in float e passa xn quantizzato Q5.13, come il riferimento).
  [raw, valid] = snn_b2_fsm(xn, start);
  % DECODE = sigma-LUT a **64 punti** (era 256 fino al 2026-07-14). Scelta dallo studio
  % DECODE_LUT_SWEEP.md: 64 e' la LUT piu' piccola il cui errore d'approssimazione su v0 (0.0114)
  % resta SOTTO l'errore di quantizzazione fixed gia' accettato (0.028) -> il decode non diventa la
  % fonte d'errore dominante. Accuratezza identica (83.98 vs 83.97), top 4630 -> 4342 LUT (-6.2%).
  % `snn_decode_lut(.,256)` e' bit-identico al vecchio `snn_decode_hdl` (verificato) -> sostituzione provata.
  params = snn_decode_lut(raw, 64);
  done = valid;
end
