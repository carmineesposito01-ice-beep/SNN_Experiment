function [k, frac] = decode_a(raw, N) %#codegen
%DECODE_A  [R4/R12] Prima meta' del decode: dal readout grezzo all'INDICE di tabella + frazione.
%
%  ⚠️ SINGLE SOURCE: composizione di decode_a1 (normalizzazione) e decode_a2 (scala/indice/frazione),
%  che la chart esegue in DUE clock -- i due moltiplicatori erano in serie (collo a 57,5 MHz).
%  Composta qui per i chiamanti funzionali (snn_decode_lut) e perche' i cancelli provino il codice vero.
%
%  ⚠️ NON si time-multiplexano i 5 parametri (restano srotolati): sarebbe un'ottimizzazione di AREA, e
%  di area ce n'e' in abbondanza. Serve solo profondita'.
  adjv        = decode_a1(raw);
  [k, frac]   = decode_a2(adjv, N);
end
