function [accel, pairs] = acc_iidm_open(s, v, dv, v_l, p, rst, T) %#codegen
%ACC_IIDM_OPEN  ACC-IIDM **open-loop**: accel = f(stato, parametri). NON integra v ne' s.
%  s, v, dv, v_l : stato fornito DA FUORI (il loop lo chiude il sistema che testa)
%  p             : [v0; T; s0; a; b]
%  rst           : true -> azzera lo stato del filtro OU (inizio di una nuova traiettoria)
%  T (opz.)      : prototipi di tipo (acc_types). Assente/vuoto -> DOUBLE (riferimento + plant
%                  cf_plant_lib/ACC_IIDM); popolato -> FIXED (blocco HDL-ready Donatello_ACC_IIDM).
%                  Type-parametrico come snn_core: UNICA fonte, perche' due implementazioni della
%                  stessa matematica divergerebbero in silenzio (lezione di HDL_PHASE §2.1).
%
%  E' l'UNICA fonte della matematica ACC-IIDM del progetto: la usa sia il blocco SP2
%  `Donatello_ACC_IIDM` sia il plant closed-loop `cf_plant_lib/ACC_IIDM` (che aggiunge solo
%  l'integrazione). Cancello che verifica entrambi: `run_plant_parity` (vs golden Python).
%
%  ⚠️ DA CHIAMARE **UNA VOLTA PER CONTROL-STEP** (DT = 0.1 s): il filtro OU stima a_l da Δv_l/DT.
%     Chiamarla a ogni clock farebbe vedere Δv_l = 0 per 340 campioni su 341 -> a_l ~ 0, in silenzio.
%     Vedi docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md §5.
%
%  NOTA sul path FIXED (SP3): niente LUT e niente Newton-Raphson. HDL Coder genera `sqrt`, `tanh` e
%  `x^4` NATIVAMENTE; la divisione la accetta **solo** con RoundingMethod 'Zero' (con 'Nearest' la
%  rifiuta). `exp` e' l'unica non generabile -- ed e' il motivo per cui la sigmoide richiese una LUT
%  mentre `tanh` no: qui compare solo in ALPHA, che ha argomento COSTANTE e viene ripiegata a
%  build-time. Tutto misurato il 2026-07-15, spec SP3 §2.
  if nargin < 7 || isempty(T), T = acc_types('double'); end
  isFx = ~isa(T.out, 'double');
  DT = 0.1; ALPHA = exp(-DT/1.0); COOL = 0.99;
  % `T_` (time headway IDM) e NON `T`: `T` e' il parametro dei tipi. Ombreggiarlo romperebbe il path
  % fixed, che usa T.st/T.par/T.acc/T.out DOPO questa riga.
  v0 = max(p(1), 1e-3); T_ = max(p(2), 1e-3); s0 = p(3); a = max(p(4), 1e-3); b = max(p(5), 1e-3);

  % Init con guardia `isempty` PER VARIABILE (idioma codegen-safe del progetto, come snn_core.m:15-19):
  % il codegen riconosce letteralmente isempty(<persistent>) come prova di definizione, e senza fallisce
  % con "Persistent variable 'alf' is undefined on some execution paths". `rst` azzera il filtro OU
  % a inizio traiettoria; al primo giro ci pensa gia' isempty, quindi non serve un flag `started`.
  persistent alf vlp
  if isempty(alf) || rst, alf = cast(0, 'like', T.acc);   end
  if isempty(vlp) || rst, vlp = cast(v_l, 'like', T.st); end

  % Niente `setfimath` e niente ramo isFx qui: la fimath ('Zero' per le divisioni) e' gia' nei
  % prototipi di acc_types, quindi ogni cast se la porta dietro e tutto combacia. In DOUBLE questi
  % cast sono no-op -> il riferimento resta bit-identico (lo prova run_plant_parity).
  % NOMI NUOVI (v0f/Tf_/...) e non riassegnazione: `v0 = cast(v0,'like',T.par)` cambierebbe il tipo
  % di v0 (da sfix21_En13, il tipo del decode, a sfix15_En8) e il codegen lo rifiuta -- "Variable
  % types are incompatible". Una variabile non puo' cambiare ne' TIPO ne' FIMATH (HDL_PHASE §9).
  sq = cast(s,  'like', T.st);   vq = cast(v,   'like', T.st);
  dq = cast(dv, 'like', T.st);   lq = cast(v_l, 'like', T.st);
  v0f = cast(v0, 'like', T.par); Tf_ = cast(T_, 'like', T.par); s0f = cast(s0, 'like', T.par);
  af  = cast(a,  'like', T.par); bf  = cast(b,  'like', T.par);

  % stima a_l (filtro OU su differenze finite del leader)
  alf = cast(ALPHA*alf + (1-ALPHA)*acc_div(T, isFx, lq - vlp, DT), 'like', T.acc);
  vlp = cast(lq, 'like', T.st);

  % --- acc_iidm_accel: IIDM base + CAH + blend ACC (verbatim da build_plant_lib:plant_code) ---
  sab = cast(max(sqrt(af*bf), 1e-6), 'like', T.par);
  s_star = cast(s0f + max(vq*Tf_ + acc_div(T, isFx, vq*dq, 2*sab, 1.74, 2.64), 0), 'like', T.st);
  s_safe = cast(max(sq, 2.0), 'like', T.st);
  v_free = cast(af*(1 - min(acc_div(T, isFx, vq, v0f, 8, 45), 10)^4), 'like', T.acc);
  z = cast(min(acc_div(T, isFx, s_star, s_safe, 2, 150), 20), 'like', T.acc);
  below = (vq <= v0f);
  a_z = cast(af*(1 - z^2), 'like', T.acc);
  if z < 1
    if below, a_iidm = cast(v_free*(1 - z^2), 'like', T.acc); else, a_iidm = cast(v_free, 'like', T.acc); end
  else
    if below, a_iidm = cast(a_z, 'like', T.acc); else, a_iidm = cast(v_free + a_z, 'like', T.acc); end
  end
  a_l_bar = cast(min(alf, af), 'like', T.acc);
  a_cah = cast(a_l_bar - acc_div(T, isFx, max(dq,0)^2, 2*s_safe + 1e-6, 4, 300), 'like', T.acc);
  a_cah = cast(min(max(a_cah, -9), af), 'like', T.acc);
  dd = cast(acc_div(T, isFx, a_iidm - a_cah, bf + 1e-6, 0.5, 3), 'like', T.acc);
  a_blend = cast((1-COOL)*a_iidm + COOL*(a_cah + bf*tanh(dd)), 'like', T.acc);
  if a_iidm >= a_cah, ac = a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), af), 'like', T.out);

  % [SP4-M-FSM G1] Coppie (num,den) REALI delle 5 divisioni variabili, per il gate di bit-identita' del
  % blocco Divide (probe_divide_bitexact). Ramo nargout-gated: nargout e' coder.const -> il path HDL a 1
  % output (il blocco) NON genera questo ramo, quindi SP3 resta invariato. Cast a T.acc = LOSSLESS: tutti i
  % tipi (st/par/acc/out) hanno f=8 frazionari e T.acc ha il MAX di bit interi (10) -> il valore non cambia
  % (G2 lo ri-verifica sul dataset). Niente double() qui (vietato nel datapath, HDL_PHASE §9): restano fi.
  if nargout >= 2
    pairs = [cast(vq*dq,'like',T.acc),          cast(2*sab,'like',T.acc); ...
             cast(vq,'like',T.acc),             cast(v0f,'like',T.acc); ...
             cast(s_star,'like',T.acc),         cast(s_safe,'like',T.acc); ...
             cast(max(dq,0)^2,'like',T.acc),    cast(2*s_safe + 1e-6,'like',T.acc); ...
             cast(a_iidm - a_cah,'like',T.acc),  cast(bf + 1e-6,'like',T.acc)];
  end
end


function q = acc_div(T, isFx, num, den, lo, hi)
%ACC_DIV  num/den type-parametrica. Fixed: T.recipN==0 -> divide() (SP3); T.recipN>0 -> reciproco-LUT
%  (SP4 var. L) SOLO per divisori VARIABILI (chiamata a 6 arg, con range lo,hi).
%  Un divisore COSTANTE (es. DT nel filtro OU) si chiama a 4 arg (senza lo,hi): resta divide(), che
%  per una costante HDL Coder ripiega in un moltiplicatore shallow -- non e' il problema di profondita'
%  delle 5 divisioni a divisore variabile. `nargin` e' coder.const per specializzazione -> HDL-safe.
  if isFx
    if T.recipN > 0 && nargin >= 6
      q = cast(num * acc_recip_lut(den, lo, hi, T.recipN), 'like', T.acc);
    else
      q = divide(numerictype(T.acc), num, den);
    end
  else
    q = num / den;
  end
end
