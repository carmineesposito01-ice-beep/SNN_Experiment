function y = micro_mac() %#codegen
%MICRO_MAC  1 MAC (moltiplica-accumula) per ciclo; operandi da LFSR interno (isola l'I/O).
%  Rappresenta la "sinapsi" ANN: moltiplicazione data x data -> DSP48. e_MAC = P_dyn / Fclk.
  persistent lfsr acc
  if isempty(lfsr)
    lfsr = uint16(4660);                               % 0x1234
    acc  = fi(0, 1, 48, 26);
  end
  nb   = bitxor(bitxor(bitget(lfsr,16), bitget(lfsr,14)), bitxor(bitget(lfsr,13), bitget(lfsr,11)));
  lfsr = bitor(bitshift(lfsr, 1), uint16(nb));         % LFSR 16-bit
  x    = reinterpretcast(lfsr,               numerictype(1, 16, 13));  % operando 1 (toggla)
  w    = reinterpretcast(bitshift(lfsr, -3), numerictype(1, 16, 13));  % operando 2 (decorrelato)
  acc  = fi(acc + fi(x * w, 1, 48, 26), 1, 48, 26);    % MAC: mult data x data -> DSP48
  y    = acc;
end
