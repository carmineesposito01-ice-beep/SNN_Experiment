function p = snn_decode_lut(raw, N) %#codegen
%SNN_DECODE_LUT  Decode Donatello con sigmoide via LUT a N punti su [-8,8) + interp lineare.
%  Generalizza snn_decode_hdl (N=256). N = coder.const, potenza di 2 (scala indice = N/16).
%  Costanti Donatello baked (lo sweep e' Donatello-only). Bit-identico a snn_decode_hdl per N=256.
%
%  ⚠️ SINGLE SOURCE (R4, 2026-07-19): il corpo e' ora la composizione di decode_a + decode_b, che sono
%  le DUE FASI che la chart esegue in due clock distinti -- il decode era il collo (pv_3, 31 livelli:
%  quattro moltiplicatori in serie piu' la lettura di tabella, tutto in un clock).
%  Composte qui in una chiamata sola perche' (a) i chiamanti non cambiano (snn_top_b2, le varianti
%  Donatello_LUT16..512) e (b) i cancelli provano ESATTAMENTE il codice che gira in hardware, non un
%  suo gemello. Il taglio e' fra `frac` e la lettura di `sgtab`: espressioni invariate, solo separate.
  [k, frac] = decode_a(raw, N);
  sv        = decode_b(k, frac, N);
  p         = decode_c(sv);   % [R10] scalatura finale in una fase a se'
end
