function p = decode_c2(pr) %#codegen
%DECODE_C2  [A3] Seconda meta' di decode_c: somma dell'offset + cast finale ai 5 parametri.
%  Riceve il prodotto a PRECISIONE PIENA da decode_c1 (registrato) e fa `lo + pr`, poi il cast a Q8.13.
%  Aritmetica IDENTICA a decode_c: stesso ordine, stesso singolo cast finale -> bit-exact per
%  costruzione. Ma "per costruzione" non e' un cancello: lo prova run_block_traj_test (dmax=0).
  Tp = numerictype(1,21,13);
  lo = coder.const(fi([8 0.5 1 0.3 0.5].', Tp));
  p  = fi(zeros(5,1), Tp);
  for i = 1:5
    p(i) = fi(lo(i) + pr(i), Tp);
  end
end
