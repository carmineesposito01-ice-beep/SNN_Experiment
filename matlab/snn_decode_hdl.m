function p = snn_decode_hdl(raw) %#codegen
%SNN_DECODE_HDL  [decode] raw[5x1] (fi Q7.13) -> params[5x1] (fi). Stadio HDL separato.
%  p = lo + (hi-lo).*sigma((raw-offset).*inv_tau).  sigma via LUT 256pt lineare su [-8,8).
%  Costanti Donatello baked. Indice LUT via *16 (shift): 16 punti/unita' su [-8,8).
  Traw = numerictype(1, 21, 13);   % T.raw  Q7.13
  Tadj = numerictype(1, 18, 13);   % adj    Q4.13 (range [-8,8])
  Titau = numerictype(1, 18, 16);  % inv_tau Q1.16
  Ts   = numerictype(1, 16, 14);   % sigma  Q1.14 in [0,1]
  Tp   = numerictype(1, 21, 13);   % param  Q7.13 (<=45)
  Tsc  = numerictype(0, 22, 13);   % scaled [0,256] Q9.13

  offset = coder.const(fi([-0.40404 -0.39012 1.7718 2.6884 -0.95578].', Traw));
  invtau = coder.const(fi([0.1 1/3 0.1 1/3 1/3].', Titau));
  lo     = coder.const(fi([8 0.5 1 0.3 0.5].', Tp));
  hilo   = coder.const(fi([37 2 4 2.2 2.5].', Tp));
  N = 256;
  sgtab = coder.const(fi(1 ./ (1 + exp(-(-8 + (0:N-1) / 16))), Ts));  % 1xN

  p = fi(zeros(5, 1), Tp);
  for i = 1:5
    adj = fi((raw(i) - offset(i)) * invtau(i), Tadj);
    scaled = fi((adj + fi(8, Tadj)) * fi(16, numerictype(0, 6, 0)), Tsc);  % (adj+8)*16 in [0,256]
    k = int32(floor(scaled));
    if k < int32(0),      k = int32(0);      end
    if k > int32(N - 2),  k = int32(N - 2);  end
    frac = fi(scaled - fi(double(k), Tsc), Ts);            % parte frazionaria [0,1)
    s0 = sgtab(k + 1);
    s1 = sgtab(k + 2);
    s  = fi(s0 + frac * fi(s1 - s0, Ts), Ts);              % interp lineare
    p(i) = fi(lo(i) + hilo(i) * s, Tp);
  end
end
