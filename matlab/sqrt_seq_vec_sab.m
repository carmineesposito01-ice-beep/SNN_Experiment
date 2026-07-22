function Y = sqrt_seq_vec_sab(X) %#codegen
%SQRT_SEQ_VEC_SAB  [SOLO PROVA] Gemello ROTTO DI PROPOSITO di sqrt_seq_vec: serve alla prova di
%  SENSIBILITA' del cancello. Un cancello che non puo' fallire non e' un cancello.
%
%  Il guasto iniettato e' l'off-by-one classico della digit-recurrence: `>` invece di `>=` nel
%  confronto col termine di prova. Quando il resto EGUAGLIA esattamente il termine (4Q+1) il passo
%  non sottrae e non alza il bit -> il risultato scende di 1 LSB. E' il bug piu' facile da scrivere
%  e il piu' difficile da vedere: sbaglia solo su una minoranza di valori.
%
%  ⚠️ Questo file NON entra in hardware. L'esemplare vero e' sqrt_seq_step.m.
  Y = zeros(numel(X), 1);
  for k = 1:numel(X)
    Y(k) = double(seq_sab(X(k)));
  end
end


function y = seq_sab(x)
  NB = sqrt_seq_nb();
  X  = fi(0, 0, NB*2, 0);  X(:) = storedInteger(x);
  R  = fi(0, 0, NB+2, 0);
  Q  = fi(0, 0, NB,   0);
  for k = 1:NB
    [X, R, Q] = step_sab(X, R, Q);
  end
  y = reinterpretcast(fi(double(Q), 1, 10, 0), numerictype(1, 10, 4));
end


function [Xn, Rn, Qn] = step_sab(X, R, Q)
  two = bitsliceget(X, sqrt_seq_nb()*2, sqrt_seq_nb()*2 - 1);
  Xn  = bitsll(X, 2);
  Rs  = bitsll(R, 2);  Rs(:) = Rs + cast(two, 'like', R);
  tr  = bitsll(cast(Q, 'like', R), 2);  tr(:) = tr + 1;
  Qs  = bitsll(Q, 1);
  if Rs > tr                                  % <-- GUASTO: `>` invece di `>=`
    Rn = Rs; Rn(:) = Rs - tr;
    Qn = Qs; Qn(:) = Qs + 1;
  else
    Rn = Rs;
    Qn = Qs;
  end
end
