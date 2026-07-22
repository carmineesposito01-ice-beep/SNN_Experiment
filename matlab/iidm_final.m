function accel = iidm_final(st, th) %#codegen
%IIDM_FINAL  [SP4-M-FSM] Fase finale: blend ACC + clamp -> accel. UNICA implementazione: la chiamano sia
%  il model (acc_iidm_fsm) sia la chart del blocco M (stato FINAL, dopo lo stato TANH).
%  Espressioni VERBATIM da acc_iidm_open (righe 71-73), con `tanh(st.dd)` che arriva gia' calcolato in
%  `th` da iidm_tanh: e' uno stadio a se' perche' il tanh fixed era il path critico (237 livelli, 7,35).
%  `th` mantiene il suo TIPO NATIVO (nessun cast a T.acc: butterebbe i bit frazionari prima del prodotto
%  con bf -> bug §2.1).
%
%  ⚠️ SINGLE SOURCE (R6, 2026-07-19): composizione di iidm_final_a (a_cah + bf*th) e iidm_final_b
%  (blend + clamp), che la chart esegue in due clock -- `acc` era il collo (35 livelli, due
%  moltiplicatori in serie). G2 prova sui 60000 control-step che il taglio e' bit-neutro.
  accel = iidm_final_c(st, iidm_final_b(st, iidm_final_a(st, th)));   % R11: cast/select/clamp a se'
end
