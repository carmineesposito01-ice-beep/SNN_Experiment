function th = iidm_tanh(st) %#codegen
%IIDM_TANH  [SP4-M-FSM #2a] Stadio a se' del `tanh`: th = tanh(dd). UNICA implementazione, chiamata sia dal
%  model (acc_iidm_fsm) sia dalla chart del blocco M (stato TANH, prima di FINAL).
%
%  PERCHE' uno stadio separato: misurato in OOC che il path critico di #2a NON era la divisione (~172
%  livelli) ma `iidm_final`, cioe' proprio il tanh fixed. Isolandolo: 237 -> 207 livelli, 7,35 -> 9,30 MHz,
%  timing CHIUSO. Ora il collo E' questo stadio (207 liv).
%
%  ⚠️ NESSUN cast del risultato: `tanh` vive in [-1,1] e il suo tipo nativo ha piu' bit frazionari di
%     T.acc (Q10.8). Castarlo qui a T.acc butterebbe quei bit PRIMA della moltiplicazione per `bf` in
%     iidm_final -> e' esattamente il meccanismo del bug §2.1 (cast prematuro prima dell'uso), che su
%     snn_b2_fsm costo' l'82,4% dei control-step. Il tipo lo deduce il codegen; chi latcha il valore
%     (la chart) deve dichiarare il persistent con lo STESSO tipo: `thl = tanh(cast(0,'like',T.acc))`.
%     Che non si perda nulla non e' un'opinione: lo provano G2 (0/60000) e G3 (vs SP3).
%
%  ESITO DEL PROBE #2c (2026-07-17): e' stato misurato in OOC quanto varrebbe togliere del tutto il tanh
%  (probe con il solo tipo, valore volutamente sbagliato, poi ripristinato):
%    RESULT probe_no_tanh  LUT=6643  Fmax=10.58   CRITPATH pR_idx -> pv_3  (172 liv)
%  Cioe': anche con un tanh a COSTO ZERO il tetto e' 10,58 MHz (non 11,65), e il collo successivo NON e' la
%  divisione ma **SNN readout -> decode LUT-64**, cioe' fuori dall'IIDM, dentro il deployato.
%  => #2c (tanh CORDIC sequenziale a mano) varrebbe al massimo +14% (9,30 -> 10,58) al prezzo di riscrivere
%     a mano l'aritmetica del tanh (rischio §2.1), senza comunque raggiungere 11,65: NON perseguito.
%  => #2b (divisore sequenziale) e' inutile in entrambi gli scenari: la divisione non compare in nessuno
%     dei due path critici misurati.
%  Dettaglio e decisione: document/SP4_ACC_IIDM_FAST.md §Variante M-FSM #2a.
  th = tanh(st.dd);
end
