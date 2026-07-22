function [Xn, Rn, Qn] = sqrt_seq_step(X, R, Q) %#codegen
%SQRT_SEQ_STEP  [IIDM R2] UN passo della radice quadrata digit-recurrence (restoring): produce UN bit.
%  SINGLE SOURCE: identica funzione chiamata (a) dalla chart una volta per ciclo nello stadio SQRT-STEP
%  e (b) dal wrapper `sqrt_seq`, iterata, che il cancello prova su TUTTO il dominio d'ingresso.
%
%  Ricorrenza classica: si consumano DUE bit del radicando per ogni bit di risultato, e si confronta col
%  "quadrato di prova" 4Q+1 -- e' esattamente cio' che HDL Coder chiama `ytempSquare` nel netlist.
%  Shift FISSI (cablaggio, non mux): niente indice variabile.
  two = bitsliceget(X, sqrt_seq_nb()*2, sqrt_seq_nb()*2 - 1);   % i 2 bit piu' alti di X
  Xn  = bitsll(X, 2);                                           % X <<= 2

  Rs = bitsll(R, 2);
  Rs(:) = Rs + cast(two, 'like', R);        % R = (R << 2) | due bit

  tr = bitsll(cast(Q, 'like', R), 2);
  tr(:) = tr + 1;                            % quadrato di prova: 4Q + 1

  Qs = bitsll(Q, 1);
  if Rs >= tr
    Rn = Rs; Rn(:) = Rs - tr;
    Qn = Qs; Qn(:) = Qs + 1;
  else
    Rn = Rs;
    Qn = Qs;
  end
end
