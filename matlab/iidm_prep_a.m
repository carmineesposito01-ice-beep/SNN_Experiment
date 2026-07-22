function [d, alf, vlp] = iidm_prep_a(v_l, rst, alf, vlp) %#codegen
%IIDM_PREP_A  [R9] Prima meta' del filtro OU: la DIFFERENZA FINITA del leader, d = (lq - vlp)/DT.
%  `d` esce a LARGHEZZA PIENA e senza tipo dichiarato -- lo si lascia dedurre dall'espressione, come per
%  blv in R6: cosi' non si puo' sbagliare la larghezza, e stringerlo cambierebbe la matematica (§2.1).
%
%  ORDINE OBBLIGATO (verbatim da iidm_prep): d usa il vlp VECCHIO, e solo DOPO vlp viene aggiornato.
%  Con rst, vlp = v_l -> d = 0 e alf = 0: inizio traiettoria pulito.
  T = acc_types('fixed');
  DT = 0.1;
  if rst
    alf(:) = 0;
    vlp(:) = v_l;
  end
  lq = cast(v_l, 'like', T.st);
  % Moltiplicazione per 1/DT invece di divide(): vedi iidm_prep. Bit-identita' provata da G2.
  INV_DT = 1/DT;
  d   = (lq - vlp) * INV_DT;
  vlp = cast(lq, 'like', T.st);
end
