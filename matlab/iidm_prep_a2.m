function alf = iidm_prep_a2(d, alf) %#codegen
%IIDM_PREP_A2  [R9] Seconda meta' del filtro OU: il passo esponenziale.
%  Era il collo a 46,3 MHz (alf_7, 21 livelli): differenza finita e filtro stavano nello stesso clock.
%  Espressione VERBATIM da iidm_prep, con (lq-vlp)*INV_DT gia' calcolato in `d`.
  T = acc_types('fixed');
  DT = 0.1; ALPHA = exp(-DT/1.0);
  alf = cast(ALPHA*alf + (1-ALPHA)*d, 'like', T.acc);
end
