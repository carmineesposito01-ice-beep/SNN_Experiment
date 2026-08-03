function nb = sqrt_seq_nb() %#codegen
%SQRT_SEQ_NB  Bit di risultato della radice (= cicli dello stadio SQRT in HW).
%  Ingresso af*bf = numerictype(1,19,8) -> intero memorizzato fino a 2^18-1; la radice intera sta in
%  9 bit (max 511), e servono 10 iterazioni (2 bit di radicando ciascuna, 20 >= 19).
  nb = 10;
end
