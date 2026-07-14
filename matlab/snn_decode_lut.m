function p = snn_decode_lut(raw, N) %#codegen
%SNN_DECODE_LUT  Decode Donatello con sigmoide via LUT a N punti su [-8,8) + interp lineare.
%  Generalizza snn_decode_hdl (N=256). N = coder.const, potenza di 2 (scala indice = N/16).
%  Costanti Donatello baked (lo sweep e' Donatello-only). Bit-identico a snn_decode_hdl per N=256.
  Traw = numerictype(1,21,13); Tadj = numerictype(1,18,13); Titau = numerictype(1,18,16);
  Ts   = numerictype(1,16,14); Tp   = numerictype(1,21,13); Tsc  = numerictype(0,23,13);
  offset = coder.const(fi([-0.40404 -0.39012 1.7718 2.6884 -0.95578].', Traw));
  invtau = coder.const(fi([0.1 1/3 0.1 1/3 1/3].', Titau));
  lo     = coder.const(fi([8 0.5 1 0.3 0.5].', Tp));
  hilo   = coder.const(fi([37 2 4 2.2 2.5].', Tp));
  scale  = coder.const(N / 16);                                    % punti per unita' su [-8,8)
  sgtab  = coder.const(fi(1 ./ (1 + exp(-(-8 + (0:N-1) / scale))), Ts));  % 1xN
  Tsm    = numerictype(0, 8, 0);                                   % moltiplicatore scala (<=32)
  p = fi(zeros(5,1), Tp);
  for i = 1:5
    adj    = fi((raw(i) - offset(i)) * invtau(i), Tadj);
    scaled = fi((adj + fi(8, Tadj)) * fi(scale, Tsm), Tsc);        % (adj+8)*scale in [0,N)
    k = int32(floor(scaled));
    if k < int32(0),     k = int32(0);     end
    if k > int32(N - 2), k = int32(N - 2); end
    frac = fi(scaled - fi(double(k), Tsc), Ts);
    s0 = sgtab(k + 1); s1 = sgtab(k + 2);
    s  = fi(s0 + frac * fi(s1 - s0, Ts), Ts);
    p(i) = fi(lo(i) + hilo(i) * s, Tp);
  end
end
