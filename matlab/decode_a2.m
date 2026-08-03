function [k, frac] = decode_a2(adjv, N) %#codegen
%DECODE_A2  [R12] Seconda parte: scala su [0,N), indice di tabella e frazione.
%  Espressioni VERBATIM da snn_decode_lut, con `adj` gia' calcolato da decode_a1.
  Tadj = numerictype(1,18,13); Ts = numerictype(1,16,14); Tsc = numerictype(0,23,13);
  scale = coder.const(N / 16);                                    % punti per unita' su [-8,8)
  Tsm   = numerictype(0, 8, 0);                                   % moltiplicatore scala (<=32)
  k    = zeros(5, 1, 'int32');
  frac = fi(zeros(5,1), Ts);
  for i = 1:5
    scaled = fi((adjv(i) + fi(8, Tadj)) * fi(scale, Tsm), Tsc);    % (adj+8)*scale in [0,N)
    ki = int32(floor(scaled));
    if ki < int32(0),     ki = int32(0);     end
    if ki > int32(N - 2), ki = int32(N - 2); end
    k(i)    = ki;
    frac(i) = fi(scaled - fi(double(ki), Tsc), Ts);
  end
end
