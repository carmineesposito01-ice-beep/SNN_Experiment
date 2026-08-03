function p = decode_c(sv) %#codegen
%DECODE_C  Scalatura finale -> i 5 parametri. [R10] fase a se' nel controllore.
%  [A3] Ora e' la COMPOSIZIONE di decode_c1 (i prodotti, a precisione piena) + decode_c2 (somma
%  dell'offset + cast). Composta qui perche' (a) i chiamanti non cambiano e (b) i cancelli provano
%  ESATTAMENTE il codice che gira in hardware, non un suo gemello.
%  La chart nella variante `p6` chiama le due meta' in due fasi distinte: e' li' che il taglio serve,
%  perche' separa i DSP dalla catena di CARRY4 che domina il path critico.
  pr = decode_c1(sv);
  p  = decode_c2(pr);
end
