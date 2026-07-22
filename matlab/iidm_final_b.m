function ab = iidm_final_b(st, bl) %#codegen
%IIDM_FINAL_B  [R6/R11] Seconda fase della finale: il blend esponenziale ACC, a LARGHEZZA PIENA.
%  Il cast a T.acc, la selezione e il clamp stanno in iidm_final_c: erano tutti nello stesso clock.
%  `ab` non ha tipo dichiarato -- lo si lascia dedurre dall'espressione (come blv in R6), cosi' non si
%  puo' sbagliare la larghezza e non si stringe nulla prima dell'uso (§2.1).
%  Espressione VERBATIM da iidm_final.
  COOL = 0.99;
  ab = (1-COOL)*st.a_iidm + COOL*bl;
end
