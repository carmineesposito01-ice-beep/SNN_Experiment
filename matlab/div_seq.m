function q = div_seq(num, den) %#codegen
%DIV_SEQ  [IIDM #2] Wrapper FUNZIONALE della ricorrenza restoring: setup -> nb passi -> finalizzazione.
%  Bit-identico a `fsm_div`, cioe' a `divide(numerictype(T.acc), num, den)` con RoundingMethod 'Zero'.
%
%  ⚠️ SINGLE SOURCE: i passi li fa `div_seq_step`, la STESSA funzione che la chart chiama una volta per
%  ciclo nello stadio DIV. Qui e' iterata nb volte per poterla PROVARE su 300k coppie reali
%  (probe_div_seq) -> cio' che e' provato e' cio' che gira in hardware, negli STESSI tipi fixed-point.
%
%  Semantica (spec §5): dividere le MAGNITUDINI e applicare il segno alla fine E' il troncamento verso
%  zero -- non una sua approssimazione.
  T  = acc_types('fixed');
  nt = numerictype(T.acc);
  WL = nt.WordLength;                  % 19
  FL = nt.FractionLength;              % 8
  NB = div_seq_nb();                   % 27 bit di quoziente
  NR = 20;                             % resto: R<<1|bit < 2*B <= 2^19 -> 20 bit con margine

  Ni = double(storedInteger(num));
  Di = double(storedInteger(den));
  lo = -2^(WL-1);  hi = 2^(WL-1) - 1;

  if Di == 0                           % guardia: den=0 non lo produce il controllore (iidm_prep guarda
    if Ni > 0                          % i denominatori), ma la funzione non deve esplodere.
      qs = hi;
    elseif Ni < 0
      qs = lo;
    else
      qs = 0;
    end
  else
    sq = (Ni < 0) ~= (Di < 0);
    A = fi(abs(Ni) * 2^FL, 0, NB, 0);  % dividendo scalato, consumato dal MSB
    B = fi(abs(Di),        0, NR, 0);
    R = fi(0, 0, NR, 0);
    Q = fi(0, 0, NB, 0);
    for k = 1:NB                       % in HW: UN passo per ciclo (kbit e' STATO, non indice srotolato)
      [A, R, Q] = div_seq_step(A, R, Q, B);
    end
    qs = double(Q);
    if sq, qs = -qs; end
    if qs > hi, qs = hi; elseif qs < lo, qs = lo; end
  end

  q = reinterpretcast(fi(qs, 1, WL, 0), nt);
end
