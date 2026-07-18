function th = tanh_cordic(dd) %#codegen
% [B2.0-2b A2c] tanh via CORDIC IPERBOLICO: sinh/cosh via rotazioni, range-reduction su ln2, poi
%  tanh = sinh/cosh (una DIVISIONE finale). Approssimato (NON bit-exact): iterazioni finite + fixed-point.
%  CARATTERIZZAZIONE: la divisione finale e' l'operazione che SP4 ha eliminato -> variante pesante.
  T = numerictype(1, 40, 24);                 % largo: e^8 ~ 2981 non deve overfloware (15 bit interi)
  isneg = dd < 0;
  ax = fi(abs(dd), T);
  if ax >= fi(8, T)                            % oltre |x|>8 tanh ~ +-1 (saturazione)
    if isneg, th = fi(-1, 1, 19, 17); else, th = fi(1, 1, 19, 17); end
    return;
  end
  LN2 = fi(0.6931471805599453, T);
  ki  = int32(ax * fi(1.4426950408889634, T));   % round(ax/ln2): fi->int32 arrotonda
  r   = fi(ax - fi(ki, T) * LN2, T);             % |r| <= ln2/2 < 1.1182 -> CORDIC iperbolico converge
  atab = [fi(0.549306144,T) fi(0.255412812,T) fi(0.125657214,T) fi(0.062581571,T) ...
          fi(0.031259832,T) fi(0.015626272,T) fi(0.007812659,T) fi(0.003906323,T) ...
          fi(0.001953127,T) fi(0.000976563,T) fi(0.000488281,T) fi(0.000244141,T) fi(0.000122070,T)];
  reps = int32([1 2 3 4 4 5 6 7 8 9 10 11 12 13 13]);   % ripeti i=4,13 (convergenza iperbolica)
  ch = fi(1.205136364, T); sh = fi(0, T); z = r;        % x0 = 1/Kh (gain pre-compensato)
  for n = 1:15
    i = reps(n);
    if z < 0, d = fi(-1, T); else, d = fi(1, T); end
    sh2 = fi(sh + d * bitsra(ch, i), T);
    ch2 = fi(ch + d * bitsra(sh, i), T);
    z   = fi(z  - d * atab(i), T);
    sh = sh2; ch = ch2;
  end
  er  = fi(ch + sh, T);            % e^r
  enr = fi(ch - sh, T);            % e^-r
  ex  = fi(bitsll(er,  ki), T);    % 2^k  * e^r  = e^x
  enx = fi(bitsra(enr, ki), T);    % 2^-k * e^-r = e^-x
  num = fi(ex - enx, 1, 40, 24, 'RoundingMethod','Zero','OverflowAction','Saturate');   % 2 sinh(x)
  den = fi(ex + enx, 1, 40, 24, 'RoundingMethod','Zero','OverflowAction','Saturate');   % 2 cosh(x)
  tp  = divide(numerictype(1,19,17), num, den);   % tanh = sinh/cosh ('Zero' -> HDL ok)
  if isneg, th = fi(-tp, 1,19,17); else, th = fi(tp, 1,19,17); end
end
