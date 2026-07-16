function y = acc_recip_lut(x, lo, hi, N) %#codegen
%ACC_RECIP_LUT  1/x via LUT 1-D a N punti su [lo,hi) + interpolazione lineare. Modello: snn_decode_lut.
%  Per l'ACC-IIDM fixed (SP4 variante L): i divisori sono LIMITATI lontano da zero, quindi 1/x e' liscio
%  e limitato -> una LUT piccola basta. lo,hi,N sono coder.const (il chiamante passa letterali) e la
%  tabella e' coder.const -> HDL Coder la ripiega (nessuna divisione in hardware).
%  x fuori [lo,hi] viene saturato agli estremi (i range sono garantiti dai clamp dell'IIDM).
  Tx = numerictype(1, 24, 13);      % ingresso reciproco
  Ty = numerictype(1, 24, 20);      % 1/x <= 1/0.5 = 2 -> pochi bit interi, molti frazionari
  lo_ = coder.const(fi(lo, Tx)); hi_ = coder.const(fi(hi, Tx));
  step  = coder.const((hi - lo) / (N - 1));
  invst = coder.const(1 / step);                                  % punti per unita'
  tab   = coder.const(fi(1 ./ (lo + (0:N-1) * step), Ty));        % 1xN: 1/x_i
  Tsm   = numerictype(0, 24, 13);                                 % moltiplicatore scala
  xs = fi(x, Tx);
  if xs < lo_, xs(:) = lo_; end
  if xs > hi_, xs(:) = hi_; end
  pos = fi((xs - lo_) * fi(invst, Tsm), numerictype(0, 32, 13));  % (x-lo)/step in [0,N-1)
  k = int32(floor(pos));
  if k < int32(0),     k = int32(0);     end
  if k > int32(N - 2), k = int32(N - 2); end
  frac = fi(pos - fi(double(k), numerictype(0, 32, 13)), Ty);
  y0 = tab(k + 1); y1 = tab(k + 2);
  y = fi(y0 + frac * fi(y1 - y0, Ty), Ty);
end
