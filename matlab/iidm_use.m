function st = iidm_use(k, q, st) %#codegen
%IIDM_USE  [SP4-M-FSM] Consuma il quoziente q della divisione k e aggiorna lo stato `st`. UNICA
%  implementazione: la chiamano sia il model (acc_iidm_fsm) sia la chart del blocco M.
%
%  ⚠️ SINGLE SOURCE (R5, 2026-07-19): il corpo e' ora la composizione di iidm_use_a (i quadrati) e
%  iidm_use_b (prodotti e selezioni), che la chart esegue in DUE clock distinti -- k=2 e k=3 erano le
%  due catene piu' profonde della legge (quattro e due moltiplicatori in serie). Composte qui in una
%  chiamata sola: il model resta a un passo e G2 prova sui 60000 control-step che il taglio e' bit-neutro.
  st = iidm_use_a(k, q, st);
  st = iidm_use_m(k, st);      % [R7/R16] primi quadrati
  st = iidm_use_m2(k, st);     % [R16] secondo quadrato / sottrazione
  st = iidm_use_b(k, q, st);
end
