function nb = div_seq_nb() %#codegen
%DIV_SEQ_NB  Numero di bit di quoziente della ricorrenza (= cicli dello stadio DIV in HW).
%  T.acc = fixdt(1,19,8): il dividendo scalato e' |N|<<8 con |N| <= 2^18, quindi <= 2^26 -> 27 bit.
%  Costante condivisa fra `div_seq` (wrapper funzionale, provato) e la chart (stessa ricorrenza a stadi):
%  se cambia il tipo, cambia QUI e in un posto solo.
  nb = 27;
end
