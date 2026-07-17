function th = iidm_tanh(st) %#codegen
%IIDM_TANH  [SP4-M-FSM #2a] Stadio a se' del `tanh`: th = tanh(dd). UNICA implementazione, chiamata sia dal
%  model (acc_iidm_fsm) sia dalla chart del blocco M (stato TANH, prima di FINAL).
%
%  PERCHE' uno stadio separato: misurato in OOC che il path critico di #2a NON era la divisione (~172
%  livelli) ma `iidm_final`, cioe' proprio il tanh fixed: CRITPATH st_dd -> acc_3, 237 livelli, Fmax 7,35.
%  Spezzandolo, il ciclo piu' lungo torna a essere la divisione.
%
%  ⚠️ NESSUN cast del risultato: `tanh` vive in [-1,1] e il suo tipo nativo ha piu' bit frazionari di
%     T.acc (Q10.8). Castarlo qui a T.acc butterebbe quei bit PRIMA della moltiplicazione per `bf` in
%     iidm_final -> e' esattamente il meccanismo del bug §2.1 (cast prematuro prima dell'uso), che su
%     snn_b2_fsm costo' l'82,4% dei control-step. Il tipo lo deduce il codegen; chi latcha il valore
%     (la chart) deve dichiarare il persistent con lo STESSO tipo: `thl = tanh(cast(0,'like',T.acc))`.
%     Che non si perda nulla non e' un'opinione: lo provano G2 (0/60000) e G3 (vs SP3).
  th = tanh(st.dd);
end
