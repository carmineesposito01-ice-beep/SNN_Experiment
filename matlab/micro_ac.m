function y = micro_ac() %#codegen
%MICRO_AC  1 accumulo po2 shift-add per ciclo; operando da LFSR interno (isola l'I/O).
%  Rappresenta la "sinapsi" SNN: operando << esponente po2 (moltiplicazione po2 = shift), poi somma.
%  Atteso: 0 DSP (barrel-shifter + adder su LUT). e_AC = P_dyn / Fclk (1 op/ciclo).
  persistent lfsr acc cnt
  if isempty(lfsr)
    lfsr = uint16(43981);                              % 0xABCD
    acc  = fi(0, 1, 32, 13);
    cnt  = uint8(0);
  end
  nb   = bitxor(bitxor(bitget(lfsr,16), bitget(lfsr,14)), bitxor(bitget(lfsr,13), bitget(lfsr,11)));
  lfsr = bitor(bitshift(lfsr, 1), uint16(nb));         % LFSR 16-bit (taps 16,14,13,11)
  x    = reinterpretcast(lfsr, numerictype(1, 16, 13)); % bits -> fi con segno, toggla ogni ciclo
  sh   = fi(bitsll(fi(x, 1, 32, 13), cnt), 1, 32, 13);  % x << cnt nel tipo largo (barrel shifter)
  acc  = fi(acc + sh, 1, 32, 13);                       % accumulo (AC)
  cnt  = bitand(cnt + uint8(1), uint8(7));              % esponente po2 in [0,7] (mod 8 = AND 7)
  y    = acc;
end
