function q = div_seq_fin(Q, sq, den_is_zero, num_sign) %#codegen
%DIV_SEQ_FIN  [IIDM #2] Finalizzazione: applica il segno al quoziente e satura al range di T.acc.
%  SINGLE SOURCE con la chart (stadio DIV-FIN) e col wrapper provato `div_seq`.
%  den_is_zero/num_sign gestiscono la guardia den=0 (che il controllore non produce -- iidm_prep guarda
%  i denominatori -- ma la funzione non deve esplodere).
  T  = acc_types('fixed');
  nt = numerictype(T.acc);
  WL = nt.WordLength;
  NB = div_seq_nb();

  qw = cast(Q, 'like', fi(0, 1, NB+1, 0));      % sfix(NB+1): ospita il segno senza saturare
  if sq, qw(:) = -qw; end

  if den_is_zero                                 % saturazione al segno del dividendo
    if num_sign > 0
      qw(:) = 2^(WL-1) - 1;
    elseif num_sign < 0
      qw(:) = -2^(WL-1);
    else
      qw(:) = 0;
    end
  end

  qs = fi(qw, 1, WL, 0, fimath('OverflowAction','Saturate','RoundingMethod','Zero'));  % satura a T.acc
  q  = reinterpretcast(removefimath(qs), nt);
end
