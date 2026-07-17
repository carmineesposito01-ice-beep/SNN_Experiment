function accel = iidm_final(st, th) %#codegen
%IIDM_FINAL  [SP4-M-FSM] Fase finale: blend ACC + clamp -> accel. UNICA implementazione: la chiamano sia
%  il model (acc_iidm_fsm) sia la chart del blocco M (stato FINAL, dopo lo stato TANH).
%  Espressioni VERBATIM da acc_iidm_open (righe 71-73), con l'unica differenza che `tanh(st.dd)` arriva
%  gia' calcolato in `th` da iidm_tanh: e' uno stadio a se' perche' il tanh fixed era il path critico
%  (237 livelli, Fmax 7,35). `th` mantiene il suo TIPO NATIVO (nessun cast a T.acc: butterebbe i bit
%  frazionari del tanh prima del prodotto con bf -> bug §2.1). G2/G3 provano che non cambia un bit.
  T = acc_types('fixed');           % costruito DENTRO (vedi iidm_prep)
  COOL = 0.99;
  a_blend = cast((1-COOL)*st.a_iidm + COOL*(st.a_cah + st.bf*th), 'like', T.acc);
  if st.a_iidm >= st.a_cah, ac = st.a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), st.af), 'like', T.out);
end
