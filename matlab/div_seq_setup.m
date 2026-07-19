function [A, B, sq] = div_seq_setup(num, den) %#codegen
%DIV_SEQ_SETUP  [IIDM #2] Preparazione della ricorrenza: magnitudini + segno del quoziente.
%  SINGLE SOURCE con la chart (stadio DIV-INIT) e col wrapper provato `div_seq`.
%
%  ⚠️ NIENTE abs() di fi: abs() SATURA sul valore piu' negativo (-2^(WL-1) -> 2^(WL-1)-1), cioe' sbaglia
%     di 1 LSB proprio sull'estremo. Si passa per l'intero memorizzato in un tipo piu' LARGO, dove la
%     negazione non satura.
  T  = acc_types('fixed');
  nt = numerictype(T.acc);
  WL = nt.WordLength;                 % 19
  FL = nt.FractionLength;             % 8
  NB = div_seq_nb();                  % 27
  NR = 20;

  sq = (num < 0) ~= (den < 0);        % segno del quoziente

  sn = reinterpretcast(num, numerictype(1, WL, 0));      % intero memorizzato, sfix(WL)
  sd = reinterpretcast(den, numerictype(1, WL, 0));
  wn = cast(sn, 'like', fi(0, 1, WL+1, 0));              % sfix(WL+1): -(-2^(WL-1)) ci sta
  wd = cast(sd, 'like', fi(0, 1, WL+1, 0));
  if wn < 0, wn(:) = -wn; end                            % magnitudine, senza saturare
  if wd < 0, wd(:) = -wd; end

  A = bitsll(cast(wn, 'like', fi(0, 0, NB, 0)), FL);     % |N| << FL  (<= 2^26, sta in ufix27)
  B = cast(wd, 'like', fi(0, 0, NR, 0));                 % |D|
end
