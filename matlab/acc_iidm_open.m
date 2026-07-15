function accel = acc_iidm_open(s, v, dv, v_l, p, rst, T) %#codegen
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

  if isFx
    % fimath con RoundingMethod 'Zero': l'UNICA forma di divisione che HDL Coder genera per tipi
    % SIGNED ('Floor' vale solo per unsigned). Prodotti e somme a precisione FISSA (T.acc), se no i
    % word-length crescerebbero a ogni operazione.
    FM = fimath('RoundingMethod', 'Zero', 'OverflowAction', 'Saturate', ...
                'ProductMode', 'SpecifyPrecision', ...
                'ProductWordLength', T.acc.WordLength, 'ProductFractionLength', T.acc.FractionLength, ...
                'SumMode', 'SpecifyPrecision', ...
                'SumWordLength', T.acc.WordLength, 'SumFractionLength', T.acc.FractionLength);
    % NOMI NUOVI, non riassegnazione: `v0 = cast(v0, 'like', T.par)` cambierebbe il tipo di v0 (da
    % sfix21_En13, che e' il tipo del decode, a sfix15_En8) e il codegen lo rifiuta -- "Variable types
    % are incompatible". Una variabile NON puo' cambiare tipo (HDL_PHASE §9). Ne' serve `x(:)=`: qui
    % il tipo di destinazione e' diverso per progetto, quindi la variabile giusta e' un'altra.
    sq = setfimath(cast(s,  'like', T.st),  FM);
    vq = setfimath(cast(v,  'like', T.st),  FM);
    dq = setfimath(cast(dv, 'like', T.st),  FM);
    lq = setfimath(cast(v_l,'like', T.st),  FM);
    v0f = setfimath(cast(v0, 'like', T.par), FM);
    Tf_ = setfimath(cast(T_, 'like', T.par), FM);
    s0f = setfimath(cast(s0, 'like', T.par), FM);
    af  = setfimath(cast(a,  'like', T.par), FM);
    bf  = setfimath(cast(b,  'like', T.par), FM);
    alf = setfimath(alf, FM); vlp = setfimath(vlp, FM);
  else
    sq = s; vq = v; dq = dv; lq = v_l;
    v0f = v0; Tf_ = T_; s0f = s0; af = a; bf = b;
  end

  % stima a_l (filtro OU su differenze finite del leader)
  alf = cast(ALPHA*alf + (1-ALPHA)*acc_div(T, isFx, lq - vlp, DT), 'like', T.acc);
  vlp = cast(lq, 'like', T.st);

  % --- acc_iidm_accel: IIDM base + CAH + blend ACC (verbatim da build_plant_lib:plant_code) ---
  sab = cast(max(sqrt(af*bf), 1e-6), 'like', T.par);
  s_star = cast(s0f + max(vq*Tf_ + acc_div(T, isFx, vq*dq, 2*sab), 0), 'like', T.st);
  s_safe = cast(max(sq, 2.0), 'like', T.st);
  v_free = cast(af*(1 - min(acc_div(T, isFx, vq, v0f), 10)^4), 'like', T.acc);
  z = cast(min(acc_div(T, isFx, s_star, s_safe), 20), 'like', T.acc);
  below = (vq <= v0f);
  a_z = cast(af*(1 - z^2), 'like', T.acc);
  if z < 1
    if below, a_iidm = cast(v_free*(1 - z^2), 'like', T.acc); else, a_iidm = cast(v_free, 'like', T.acc); end
  else
    if below, a_iidm = cast(a_z, 'like', T.acc); else, a_iidm = cast(v_free + a_z, 'like', T.acc); end
  end
  a_l_bar = cast(min(alf, af), 'like', T.acc);
  a_cah = cast(a_l_bar - acc_div(T, isFx, max(dq,0)^2, 2*s_safe + 1e-6), 'like', T.acc);
  a_cah = cast(min(max(a_cah, -9), af), 'like', T.acc);
  dd = cast(acc_div(T, isFx, a_iidm - a_cah, bf + 1e-6), 'like', T.acc);
  a_blend = cast((1-COOL)*a_iidm + COOL*(a_cah + bf*tanh(dd)), 'like', T.acc);
  if a_iidm >= a_cah, ac = a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), af), 'like', T.out);
end


function q = acc_div(T, isFx, num, den)
%ACC_DIV  Divisione type-parametrica: in double e' `num/den`, in fixed e' `divide(numerictype,...)`.
%  ⚠️ In fixed l'operatore `/` NON va usato: non produce il tipo di quoziente che ci si aspetta.
%     Misurato il 2026-07-15 con fimath('RoundingMethod','Zero', Product/SumMode 'SpecifyPrecision'):
%        13.743 / 2.5625  -> 0        (atteso 5.36)
%         6.216 / 17.95   -> 0        (atteso 0.346)
%        11.552 / 10.2396 -> 1        (atteso 1.128)  <- troncato a INTERO
%     cioe' l'ACC-IIDM in fixed restituiva accel = 0 SEMPRE. `divide` impone il tipo del risultato
%     (qui T.acc) e toglie l'ambiguita'. HDL Coder genera VHDL da entrambe le forme (verificato),
%     quindi non costa l'HDL-readiness.
  if isFx
    q = divide(numerictype(T.acc), num, den);
  else
    q = num / den;
  end
end
