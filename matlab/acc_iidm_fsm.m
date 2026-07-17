function accel = acc_iidm_fsm(s, v, dv, v_l, p, rst) %#codegen
%ACC_IIDM_FSM  [SP4-M-FSM] MODEL della forma FSM: chiama le funzioni-fase in sequenza, in UNA chiamata
%  (iidm_prep -> per k=1..5: iidm_nd / fsm_div / iidm_use -> iidm_final).
%
%  Le funzioni-fase (iidm_prep, iidm_nd, iidm_use, iidm_final, fsm_div) sono la **UNICA implementazione**
%  della matematica ACC-IIDM in forma FSM: la chart del blocco `Donatello_ACC_IIDM_M` chiama le STESSE,
%  sostituendo soltanto `fsm_div` con l'handshake verso HDLMathLib/Divide -- che G1 ha provato
%  bit-identico a divide() su 300.000 coppie reali (dmax=0). Percio' model e chart NON possono divergere
%  sulla matematica: il buco §2.1 (due implementazioni -> 82,4% dei control-step divergenti su
%  snn_b2_fsm) e' chiuso PER COSTRUZIONE.
%
%  FIXED-ONLY (niente argomento T): le fasi costruiscono acc_types('fixed') DENTRO, perche' HDL Coder
%  rifiuta uno struct di prototipi che attraversa le funzioni ("Struct in expression 'T' has an
%  empty-typed field ... MATLAB-to-dataflow conversion"). Il riferimento DOUBLE resta `acc_iidm_open`,
%  type-parametrico e invariato (lo prova run_plant_parity).
%
%  Differenza vs acc_iidm_open: solo la FORMA (divisioni esplicitate e sequenziate q1->q5, operandi in
%  T.acc). La matematica e' verbatim. Cancello: G2 (run_acciidm_m_dataset) -> dmax=0 vs acc_iidm_open
%  sul dataset INTERO (60x1000 control-step), provato sensibile (q2 al posto di q3 -> 1990/2000 diff).
  % Lo STORAGE del filtro OU sta qui (entry point): iidm_prep e' pura, perche' HDL Coder vieta i
  % persistent in una funzione non-entry-point chiamata in un condizionale (la chart la chiama in due rami).
  T = acc_types('fixed');
  persistent alf vlp
  if isempty(alf), alf = cast(0,   'like', T.acc); end
  if isempty(vlp), vlp = cast(v_l, 'like', T.st);  end
  [st, alf, vlp] = iidm_prep(s, v, dv, v_l, p, rst, alf, vlp);
  for k = 1:5                        % trip-count costante -> il codegen srotola: k e' coder.const
    [num, den] = iidm_nd(k, st);
    q = fsm_div(num, den);
    st = iidm_use(k, q, st);
  end
  th = iidm_tanh(st);                % stadio a se' nella chart (era il path critico: tanh fixed)
  accel = iidm_final(st, th);
end
