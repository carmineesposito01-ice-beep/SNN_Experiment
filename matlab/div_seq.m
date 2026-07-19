function q = div_seq(num, den) %#codegen
%DIV_SEQ  [IIDM #2] Wrapper FUNZIONALE della divisione digit-recurrence: setup -> nb passi -> finalize.
%  Bit-identico a `fsm_div` = `divide(numerictype(T.acc), num, den)` con RoundingMethod 'Zero'.
%
%  ⚠️ SINGLE SOURCE INTEGRALE: setup, passo e finalize sono le TRE funzioni che la chart chiamera' nei
%  suoi stadi (DIV-INIT / DIV-STEP x nb / DIV-FIN). Qui sono composte in una chiamata sola per poterle
%  PROVARE su 300k coppie reali (probe_div_seq): cio' che e' provato E' cio' che gira, negli stessi tipi.
  NB = div_seq_nb();
  NR = 20;

  [A, B, sq] = div_seq_setup(num, den);          % DIV-INIT
  R = fi(0, 0, NR, 0);
  Q = fi(0, 0, NB, 0);

  if B > 0
    for k = 1:NB                                  % DIV-STEP: in HW UN passo per ciclo (kbit e' STATO)
      [A, R, Q] = div_seq_step(A, R, Q, B);
    end
  end

  ns = 0;                                         % segno del dividendo (serve solo alla guardia den=0)
  if num > 0
    ns = 1;
  elseif num < 0
    ns = -1;
  end
  q = div_seq_fin(Q, sq, B == 0, ns);             % DIV-FIN
end
