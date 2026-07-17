function accel = iidm_final(st) %#codegen
%IIDM_FINAL  [SP4-M-FSM] Fase finale: blend ACC + clamp -> accel. UNICA implementazione: la chiamano sia
%  il model (acc_iidm_fsm) sia la chart del blocco M (nello stato DONE, dopo la 5a divisione).
%  Espressioni VERBATIM da acc_iidm_open (righe 71-73).
  T = acc_types('fixed');           % costruito DENTRO (vedi iidm_prep)
  COOL = 0.99;
  a_blend = cast((1-COOL)*st.a_iidm + COOL*(st.a_cah + st.bf*tanh(st.dd)), 'like', T.acc);
  if st.a_iidm >= st.a_cah, ac = st.a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), st.af), 'like', T.out);
end
