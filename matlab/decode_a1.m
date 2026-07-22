function adjv = decode_a1(raw) %#codegen
%DECODE_A1  [R12] Prima parte del decode: normalizzazione (raw - offset)*invtau.
%  Separata da decode_a2 perche' i due moltiplicatori (invtau e scale) erano in serie nello stesso
%  clock -- era il collo a 57,5 MHz (dfrv, 18 livelli). `adj` ha il tipo Tadj GIA' DICHIARATO
%  nell'originale, quindi qui non si stringe nulla (nessun rischio §2.1).
%  Espressione VERBATIM da snn_decode_lut.
  Traw  = numerictype(1,21,13); Tadj = numerictype(1,18,13); Titau = numerictype(1,18,16);
  offset = coder.const(fi([-0.40404 -0.39012 1.7718 2.6884 -0.95578].', Traw));
  invtau = coder.const(fi([0.1 1/3 0.1 1/3 1/3].', Titau));
  adjv = fi(zeros(5,1), Tadj);
  for i = 1:5
    adjv(i) = fi((raw(i) - offset(i)) * invtau(i), Tadj);
  end
end
