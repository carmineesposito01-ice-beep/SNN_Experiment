function [params, done] = snn_top_b2(xn, start) %#codegen
%SNN_TOP_B2  [B2] Top Donatello deployabile: SNN(FSM B2) -> decode.
%  xn[4] normalizzato (fi Q5.13, il PS fa il normalize in SW float) + start
%  -> params[5] fisici IDM + done. Streaming: start=1 avvia una control-step;
%  done=1 quando params e' pronto (~340 clock dopo). decode combinatorio (LUT sigma).
%  Nota: normalize NON in HDL (1 LSB di xn flippa spike -> errore amplificato; il PS
%  normalizza in float e passa xn quantizzato Q5.13, come il riferimento).
  [raw, valid] = snn_b2_fsm(xn, start);
  params = snn_decode_hdl(raw);
  done = valid;
end
