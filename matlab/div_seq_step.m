function [An, Rn, Qn] = div_seq_step(A, R, Q, B) %#codegen
%DIV_SEQ_STEP  [IIDM #2] UN passo della ricorrenza restoring: produce UN bit di quoziente.
%  SINGLE SOURCE: questa identica funzione e' chiamata (a) dalla chart, una volta per ciclo, nello stadio
%  DIV, e (b) dal wrapper funzionale `div_seq`, iterata nb volte, che il cancello prova su 300k coppie
%  REALI. Cosi' cio' che e' PROVATO e' esattamente cio' che GIRA in hardware (stesso principio delle
%  funzioni-fase iidm_*): non esistono due esemplari dell'algoritmo che possano divergere in silenzio.
%
%  Formulazione scelta per l'HW: si consuma A dal MSB e si spinge in R, invece di indicizzare il bit
%  i-esimo. Cosi' gli shift sono FISSI (cablaggio, non muxaggio) e non serve alcun indice variabile --
%  che in HDL diventerebbe un mux a nb vie su ogni passo.
%
%    A : dividendo residuo (consumato dal MSB)   ufix(NB)
%    R : resto parziale                          ufix(NR)
%    Q : quoziente parziale                      ufix(NB)
%    B : divisore (magnitudine)                  ufix(NR)
  abit = bitget(A, div_seq_nb());        % MSB di A (indice FISSO)
  An   = bitsll(A, 1);                   % A <<= 1  (il bit consumato esce)

  Rs = bitsll(R, 1);                     % R <<= 1
  Rs(:) = Rs + cast(abit, 'like', R);    % R = (R << 1) | abit   -- (:) per non cambiare il tipo

  Qs = bitsll(Q, 1);                     % Q <<= 1
  if Rs >= B                             % restoring: sottrai solo se ci sta
    Rn = Rs; Rn(:) = Rs - B;
    Qn = Qs; Qn(:) = Qs + 1;             % ...e il bit di quoziente vale 1
  else
    Rn = Rs;
    Qn = Qs;
  end
end
