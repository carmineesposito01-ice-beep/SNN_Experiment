function [s0v, delv] = decode_b1(k, N) %#codegen
%DECODE_B1  [R17] Letture della tabella + differenza: s0 = sgtab(k), del = sgtab(k+1) - sgtab(k).
%  Separata da decode_b2 perche' letture, sottrazione, moltiplicazione e somma erano tutte nello stesso
%  clock -- era il collo a 77,6 MHz (dsv, 14 livelli). Espressioni VERBATIM da snn_decode_lut.
  Ts    = numerictype(1,16,14);
  scale = coder.const(N / 16);
  sgtab = coder.const(fi(1 ./ (1 + exp(-(-8 + (0:N-1) / scale))), Ts));  % 1xN
  s0v  = fi(zeros(5,1), Ts);
  delv = fi(zeros(5,1), Ts);
  for i = 1:5
    s0 = sgtab(k(i) + 1); s1 = sgtab(k(i) + 2);
    s0v(i)  = s0;
    delv(i) = fi(s1 - s0, Ts);
  end
end
