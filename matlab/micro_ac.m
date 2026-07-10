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
  t1 = bitand(bitshift(lfsr, -15), uint16(1));         % tap bit 16
  t2 = bitand(bitshift(lfsr, -13), uint16(1));         % tap bit 14
  t3 = bitand(bitshift(lfsr, -12), uint16(1));         % tap bit 13
  t4 = bitand(bitshift(lfsr, -10), uint16(1));         % tap bit 11
  fb   = bitxor(bitxor(t1, t2), bitxor(t3, t4));       % feedback uint16 (0/1)
  lfsr = bitor(bitshift(lfsr, 1), fb);                 % LFSR 16-bit full-word (no cast single-bit)
  x    = reinterpretcast(lfsr, numerictype(1, 16, 13)); % bits -> fi con segno, toggla ogni ciclo
  sh   = fi(bitsll(fi(x, 1, 32, 13), cnt), 1, 32, 13);  % x << cnt nel tipo largo (barrel shifter)
  acc  = fi(acc + sh, 1, 32, 13);                       % accumulo (AC)
  cnt  = bitand(cnt + uint8(1), uint8(7));              % esponente po2 in [0,7] (mod 8 = AND 7)
  y    = acc;
end
