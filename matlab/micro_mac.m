function y = micro_mac() %#codegen
%MICRO_MAC  1 MAC (moltiplica-accumula) per ciclo; operandi da LFSR interno (isola l'I/O).
%  Rappresenta la "sinapsi" ANN: moltiplicazione data x data -> DSP48. e_MAC = P_dyn / Fclk.
  persistent lfsr acc
  if isempty(lfsr)
    lfsr = uint16(4660);                               % 0x1234
    acc  = fi(0, 1, 48, 26);
  end
  t1 = bitand(bitshift(lfsr, -15), uint16(1));         % tap bit 16
  t2 = bitand(bitshift(lfsr, -13), uint16(1));         % tap bit 14
  t3 = bitand(bitshift(lfsr, -12), uint16(1));         % tap bit 13
  t4 = bitand(bitshift(lfsr, -10), uint16(1));         % tap bit 11
  fb   = bitxor(bitxor(t1, t2), bitxor(t3, t4));       % feedback uint16 (0/1)
  lfsr = bitor(bitshift(lfsr, 1), fb);                 % LFSR 16-bit full-word
  x    = reinterpretcast(lfsr,               numerictype(1, 16, 13));  % operando 1 (toggla)
  w    = reinterpretcast(bitshift(lfsr, -3), numerictype(1, 16, 13));  % operando 2 (decorrelato)
  acc  = fi(acc + fi(x * w, 1, 48, 26), 1, 48, 26);    % MAC: mult data x data -> DSP48
  y    = acc;
end
