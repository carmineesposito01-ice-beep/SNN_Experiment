function accel = acc_iidm_fsm(s, v, dv, v_l, p, rst, T) %#codegen
%ACC_IIDM_FSM  [SP4-M-FSM] MODEL della forma FSM: chiama le funzioni-fase in sequenza, in UNA chiamata
%  (iidm_prep -> per k=1..5: iidm_nd / fsm_div / iidm_use -> iidm_final).
%
%  Le funzioni-fase (iidm_prep, iidm_nd, iidm_use, iidm_final, fsm_div) sono la **UNICA implementazione**
%  della matematica ACC-IIDM in forma FSM: la chart del blocco `Donatello_ACC_IIDM_M` chiama le STESSE
%  funzioni, sostituendo soltanto `fsm_div` con l'handshake verso HDLMathLib/Divide -- che G1
%  (probe_divide_bitexact) ha provato bit-identico a divide() su 300.000 coppie reali (dmax=0).
%  Percio' model e chart NON possono divergere sulla matematica: il buco §2.1 (due implementazioni della
%  stessa matematica -> 82,4% dei control-step divergenti su snn_b2_fsm) e' chiuso PER COSTRUZIONE.
%
%  Differenza vs acc_iidm_open: solo la FORMA (divisioni esplicitate e sequenziate q1->q5, operandi in
%  T.acc). La matematica e' verbatim. Cancello: G2 (run_acciidm_m_dataset) -> dmax=0 vs acc_iidm_open
%  sul dataset INTERO (60x1000 control-step), provato sensibile (q2 al posto di q3 -> 1990/2000 diff).
  if nargin < 7 || isempty(T), T = acc_types('double'); end
  st = iidm_prep(s, v, dv, v_l, p, rst, T);
  for k = 1:5                        % trip-count costante -> il codegen srotola: k e' coder.const
    [num, den] = iidm_nd(k, st, T);
    q = fsm_div(T, num, den);
    st = iidm_use(k, q, st, T);
  end
  accel = iidm_final(st, T);
end
