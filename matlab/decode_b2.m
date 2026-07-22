function sv = decode_b2(s0v, delv, frac) %#codegen
%DECODE_B2  [R17] Interpolazione lineare: s = s0 + frac*del. Espressione VERBATIM da snn_decode_lut.
  Ts = numerictype(1,16,14);
  sv = fi(zeros(5,1), Ts);
  for i = 1:5
    sv(i) = fi(s0v(i) + frac(i) * delv(i), Ts);
  end
end
