function [st, alf, vlp] = iidm_prep(s, v, dv, v_l, p, rst, alf, vlp, sabin) %#codegen
%IIDM_PREP  [SP4-M-FSM] Fase 0 della FSM: guardie, cast, filtro OU, sab, s_safe -> stato `st`.
%
%  ⚠️ `sabin` (R2, 2026-07-19) = sqrt(af*bf) GIA' CALCOLATA dal chiamante, non piu' qui dentro.
%  Motivo: la radice era il COLLO (17,5 MHz, tutti i 400 path peggiori finivano su st_sab) e per
%  sequenzializzarla serve piu' di un clock -- impossibile dentro una funzione-fase che gira in UNO.
%  Chi chiama la calcola come sa: il model in un colpo (`sqrt_seq`), la chart in 10 stadi con la STESSA
%  ricorrenza (sqrt_seq_step). Vedi iidm_sabx per l'ingresso, che e' a fonte unica.
%  Matematica VERBATIM da acc_iidm_open (righe 24-57): stesse espressioni, stessi cast, stesso ordine.
%
%  UNICA implementazione, chiamata SIA dal model (acc_iidm_fsm, per G2 sul dataset) SIA dalla chart del
%  blocco `Donatello_ACC_IIDM_M` -> la matematica non puo' divergere fra i due (e' il buco §2.1 che
%  costo' l'82,4% dei control-step su snn_b2_fsm: due implementazioni della stessa matematica).
%
%  `st` esce con TUTTI i campi gia' tipizzati (i parziali a zero): da qui in poi i campi non cambiano
%  piu' tipo -- gli aggiornamenti usano `st.campo(:) = ...` (HDL_PHASE §9: una variabile non puo'
%  cambiare ne' tipo ne' fimath).
%
%  ⚠️ Una chiamata per CONTROL-STEP (DT=0.1): il filtro OU stima a_l da Δv_l/DT. Chiamarla a ogni clock
%     farebbe vedere Δv_l=0 per 340 campioni su 341 -> a_l~0, in silenzio (spec SP2 §5).
  % T COSTRUITO DENTRO (non ricevuto): HDL Coder rifiuta uno struct di prototipi che attraversa le
  % funzioni -- "Struct in expression 'T' has an empty-typed field ... MATLAB-to-dataflow conversion"
  % (acc_types usa fi([],...), campi VUOTI). Con argomento letterale e' coder.const -> ripiegata.
%
%  ⚠️ SINGLE SOURCE (R8, 2026-07-19): composizione di iidm_prep_a (SOLO il filtro OU) e
%  iidm_prep_b (cast + costruzione dello struct), che la chart esegue in DUE clock -- il filtro OU
%  era il collo (alf -> a_l_bar, gradini 8 e 9 della scala). G2 prova sui 60000 control-step che il
%  taglio e' bit-neutro.
  [d, alf, vlp] = iidm_prep_a(v_l, rst, alf, vlp);   % R9: differenza finita
  alf           = iidm_prep_a2(d, alf);              % R9: passo esponenziale
  st         = iidm_prep_b(s, v, dv, v_l, p, alf, sabin);
end
