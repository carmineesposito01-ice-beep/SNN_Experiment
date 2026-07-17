function [st, alf, vlp] = iidm_prep(s, v, dv, v_l, p, rst, alf, vlp) %#codegen
%IIDM_PREP  [SP4-M-FSM] Fase 0 della FSM: guardie, cast, filtro OU, sab, s_safe -> stato `st`.
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
  T = acc_types('fixed');
  DT = 0.1; ALPHA = exp(-DT/1.0);
  v0 = max(p(1), 1e-3); T_ = max(p(2), 1e-3); s0 = p(3); a = max(p(4), 1e-3); b = max(p(5), 1e-3);

  % Lo stato del filtro OU (alf, vlp) ARRIVA e TORNA: qui NON c'e' persistent. Motivo: HDL Coder vieta i
  % persistent in una funzione non-entry-point chiamata piu' di una volta o dentro un condizionale
  % ("Non-top-level functions with persistent variables may be invoked only once") -- e la chart del
  % blocco M chiama iidm_prep in due rami (init e valid). Lo STORAGE vive quindi nel top-level (la chart
  % / il model acc_iidm_fsm); qui resta il CALCOLO, che e' l'unica fonte (single-source intatto).
  % `rst` azzera il filtro a inizio traiettoria; `x(:) =` per non cambiare il tipo (§9).
  if rst
    alf(:) = 0;
    vlp(:) = v_l;
  end

  sq = cast(s,  'like', T.st);   vq = cast(v,   'like', T.st);
  dq = cast(dv, 'like', T.st);   lq = cast(v_l, 'like', T.st);
  v0f = cast(v0, 'like', T.par); Tf_ = cast(T_, 'like', T.par); s0f = cast(s0, 'like', T.par);
  af  = cast(a,  'like', T.par); bf  = cast(b,  'like', T.par);

  % stima a_l (filtro OU su differenze finite del leader): divisore COSTANTE DT.
  % Moltiplicazione per 1/DT invece di divide(): HDL Coder rifiuta divide() nella conversione dataflow
  % della chart M ("Call to function 'divide' is not supported unless all of its input arguments are
  % constant") e per un divisore COSTANTE ripiegherebbe comunque in un moltiplicatore shallow.
  % Che sia bit-identico a divide(x, 0.1) NON e' assunto: lo prova G2 (dmax=0 vs acc_iidm_open, che qui
  % usa divide()). Se non lo fosse, G2 fallirebbe e servirebbe un'altra strada.
  INV_DT = 1/DT;
  alf = cast(ALPHA*alf + (1-ALPHA)*((lq - vlp) * INV_DT), 'like', T.acc);
  vlp = cast(lq, 'like', T.st);

  sab    = cast(max(sqrt(af*bf), 1e-6), 'like', T.par);
  s_safe = cast(max(sq, 2.0), 'like', T.st);

  st = struct( ...
    'vq',      vq, ...
    'dq',      dq, ...
    'v0f',     v0f, ...
    'Tf_',     Tf_, ...
    's0f',     s0f, ...
    'af',      af, ...
    'bf',      bf, ...
    'sab',     sab, ...
    's_safe',  s_safe, ...
    'a_l_bar', cast(min(alf, af), 'like', T.acc), ...
    's_star',  cast(0, 'like', T.st), ...
    'v_free',  cast(0, 'like', T.acc), ...
    'z',       cast(0, 'like', T.acc), ...
    'a_iidm',  cast(0, 'like', T.acc), ...
    'a_cah',   cast(0, 'like', T.acc), ...
    'dd',      cast(0, 'like', T.acc));
end
