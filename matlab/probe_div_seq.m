function dmax = probe_div_seq(P, sabotage)
%PROBE_DIV_SEQ  [IIDM #2, T1 make-or-break] `div_seq` e' BIT-IDENTICA a `divide(numerictype(T.acc),..)`
%  sulle coppie REALI del dataset? P (Nx2) = [num den] da collect_div_pairs.
%
%  Gemello di probe_divide_bitexact (che provava il BLOCCO); qui si prova l'ALGORITMO scritto a mano --
%  cio' che #1 comprava da G1 e che #2 deve GUADAGNARE.
%
%  sabotage (opz.): prova di SENSIBILITA'. 'trunc-neg' rompe di proposito il caso dei NEGATIVI
%  (tronca verso -inf invece che verso zero) -> il cancello DEVE divergere. Un cancello che non puo'
%  fallire non e' un cancello: e i negativi sono esattamente dove i divisori a mano si rompono.
%
%    dmax = probe_div_seq(P)              -> atteso 0
%    dmax = probe_div_seq(P, 'trunc-neg') -> atteso > 0
  if nargin < 2, sabotage = ''; end
  T  = acc_types('fixed');
  A  = numerictype(T.acc);
  num = cast(P(:,1), 'like', T.acc);
  den = cast(P(:,2), 'like', T.acc);

  qref = divide(A, num, den);                 % RIFERIMENTO: la divide() di SP3 (= fsm_div)
  n    = numel(qref);
  qseq = zeros(n, 1);
  for k = 1:n
    if isempty(sabotage)
      q = div_seq(num(k), den(k));
    else
      q = div_seq_sabotaged(num(k), den(k));  % variante rotta apposta
    end
    qseq(k) = double(q);
  end

  d    = abs(qseq - double(qref));
  dmax = max(d);
  nbad = nnz(d > 0);
  fprintf('probe_div_seq: N=%d sabotage=%-10s -> dmax = %.6g   (divergenti: %d/%d)\n', ...
          n, ternary(isempty(sabotage),'(nessuno)',sabotage), dmax, nbad, n);

  if dmax > 0 && isempty(sabotage)
    ib = find(d > 0, 5);                      % le prime divergenze, per isolare il caso (segni? limiti?)
    fprintf('  prime divergenze [num den ref seq]:\n');
    for t = ib(:).'
      fprintf('    %12.6g %12.6g %12.6g %12.6g\n', ...
              double(num(t)), double(den(t)), double(qref(t)), qseq(t));
    end
  end
end


function q = div_seq_sabotaged(num, den)
%DIV_SEQ_SABOTAGED  Come div_seq ma con il TRONCAMENTO SBAGLIATO sui negativi (verso -inf invece che
%  verso zero): serve solo alla prova di sensibilita' del cancello.
  T  = acc_types('fixed');
  nt = numerictype(T.acc);
  WL = nt.WordLength; FL = nt.FractionLength;
  N = double(storedInteger(num)); D = double(storedInteger(den));
  lo = -2^(WL-1); hi = 2^(WL-1) - 1;
  if D == 0
    if N > 0, qs = hi; elseif N < 0, qs = lo; else, qs = 0; end
  else
    qs = floor((N * 2^FL) / D);               % <-- floor: verso -inf. Sui NEGATIVI differisce da 'Zero'.
    if qs > hi, qs = hi; elseif qs < lo, qs = lo; end
  end
  q = reinterpretcast(fi(qs, 1, WL, 0), nt);
end


function y = ternary(c, a, b)
  if c, y = a; else, y = b; end
end
