function pr = decode_c1(sv) %#codegen
%DECODE_C1  [A3] Prima meta' di decode_c: i SOLI PRODOTTI hilo.*sv.
%  Taglio dentro l'operazione, non fra le operazioni: il collo di Donatello e' `lo + hilo*sv`, dove i
%  DSP fanno la moltiplicazione ma la somma finisce in fabric come catena di 15 CARRY4 in serie
%  (misurato: 24,307 ns = logica 15,490 + routing 8,817, 23 livelli).
%  Registrare il prodotto separa DSP e addizionatore in due clock.
%
%  ⚠️ LARGHEZZA PIENA: il prodotto NON va stretto qui. Stringere un parziale prima dell'uso e' il bug
%  §2.1 di questo progetto — cambierebbe la matematica. Il tipo si lascia DEDURRE dall'espressione.
  Tp   = numerictype(1,21,13);
  hilo = coder.const(fi([37 2 4 2.2 2.5].', Tp));
  pr   = hilo .* sv;                  % tipo dedotto = precisione piena
end
