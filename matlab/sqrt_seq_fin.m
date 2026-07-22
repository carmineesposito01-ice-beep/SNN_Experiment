function y = sqrt_seq_fin(Q) %#codegen
%SQRT_SEQ_FIN  [IIDM R2] La radice parziale diventa il risultato tipizzato: ufix(10,0) -> sfix(10,4).
%
%  Due `reinterpretcast` in fila, entrambi a costo zero in hardware (rinominano fili):
%    1) ufix(10,0) -> sfix(10,0): lecito perche' Q <= 511 SEMPRE. Q e' la radice intera di un numero a
%       19 bit, quindi Q <= floor(sqrt(2^19-1)) = 724... ma il radicando reale arriva a 262143, da cui
%       Q <= 511 < 2^9: il bit di segno non si accende mai.
%    2) sfix(10,0) -> sfix(10,4): riposiziona la virgola. E' il passo che realizza FL_out = FL_in/2.
  y = reinterpretcast(reinterpretcast(Q, numerictype(1, 10, 0)), numerictype(1, 10, 4));
end
