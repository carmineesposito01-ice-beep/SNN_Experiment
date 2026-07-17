function accel = acc_iidm_fsm(s, v, dv, v_l, p, rst, T) %#codegen
%ACC_IIDM_FSM  [SP4-M-FSM] MODEL della FSM: stessa matematica di acc_iidm_open, con le 5 divisioni a
%  divisore VARIABILE esplicitate e sequenziate q1->q5 (num/den in variabili, quoziente latchato, poi
%  usato). E' il single-source della forma FSM: la chart del blocco `Donatello_ACC_IIDM_M` usera' le
%  STESSE espressioni sostituendo `fsm_div` con l'handshake verso il blocco Divide HDL -- G1
%  (probe_divide_bitexact) ha provato che HDLMathLib/Divide e' bit-identico a divide() su 300k coppie
%  reali (dmax=0), quindi il model e il blocco daranno gli stessi bit.
%
%  ⚠️ La matematica NON-divisione e' VERBATIM da acc_iidm_open (stesse espressioni, stessi cast, stesso
%     ordine): due implementazioni della stessa matematica divergono in silenzio (HDL_PHASE §2.1, il bug
%     che colpi' l'82,4% dei control-step). L'UNICA differenza ammessa: la divisione passa per fsm_div.
%  Cancello: G2 (run_acciidm_m_dataset) -> dmax = 0 vs acc_iidm_open sul dataset INTERO (60x1000).
%
%  Le 5 divisioni (ordine = dipendenze: q3 dopo q1 via s_star; q5 dopo q3/q4 via a_iidm/a_cah):
%    q1 = vq*dq / (2*sab)            -> s_star
%    q2 = vq / v0f                   -> v_free
%    q3 = s_star / s_safe            -> z
%    q4 = max(dq,0)^2 / (2*s_safe)   -> a_cah
%    q5 = (a_iidm-a_cah) / bf        -> dd
%  La divisione per DT (filtro OU) e' a divisore COSTANTE -> resta inline (moltiplicatore shallow),
%  non e' tra le 5 sequenziate (spec §5).
  if nargin < 7 || isempty(T), T = acc_types('double'); end
  isFx = ~isa(T.out, 'double');
  DT = 0.1; ALPHA = exp(-DT/1.0); COOL = 0.99;
  v0 = max(p(1), 1e-3); T_ = max(p(2), 1e-3); s0 = p(3); a = max(p(4), 1e-3); b = max(p(5), 1e-3);

  persistent alf vlp
  if isempty(alf) || rst, alf = cast(0, 'like', T.acc);   end
  if isempty(vlp) || rst, vlp = cast(v_l, 'like', T.st); end

  sq = cast(s,  'like', T.st);   vq = cast(v,   'like', T.st);
  dq = cast(dv, 'like', T.st);   lq = cast(v_l, 'like', T.st);
  v0f = cast(v0, 'like', T.par); Tf_ = cast(T_, 'like', T.par); s0f = cast(s0, 'like', T.par);
  af  = cast(a,  'like', T.par); bf  = cast(b,  'like', T.par);

  % stima a_l (filtro OU): divisore COSTANTE DT -> inline
  alf = cast(ALPHA*alf + (1-ALPHA)*fsm_div(T, isFx, lq - vlp, DT), 'like', T.acc);
  vlp = cast(lq, 'like', T.st);

  sab = cast(max(sqrt(af*bf), 1e-6), 'like', T.par);

  % --- q1 -> s_star ---
  n1 = vq*dq;            d1 = 2*sab;
  q1 = fsm_div(T, isFx, n1, d1);
  s_star = cast(s0f + max(vq*Tf_ + q1, 0), 'like', T.st);
  s_safe = cast(max(sq, 2.0), 'like', T.st);

  % --- q2 -> v_free ---
  n2 = vq;               d2 = v0f;
  q2 = fsm_div(T, isFx, n2, d2);
  v_free = cast(af*(1 - min(q2, 10)^4), 'like', T.acc);

  % --- q3 -> z ---
  n3 = s_star;           d3 = s_safe;
  q3 = fsm_div(T, isFx, n3, d3);
  z = cast(min(q3, 20), 'like', T.acc);

  below = (vq <= v0f);
  a_z = cast(af*(1 - z^2), 'like', T.acc);
  if z < 1
    if below, a_iidm = cast(v_free*(1 - z^2), 'like', T.acc); else, a_iidm = cast(v_free, 'like', T.acc); end
  else
    if below, a_iidm = cast(a_z, 'like', T.acc); else, a_iidm = cast(v_free + a_z, 'like', T.acc); end
  end
  a_l_bar = cast(min(alf, af), 'like', T.acc);

  % --- q4 -> a_cah ---
  n4 = max(dq,0)^2;      d4 = 2*s_safe + 1e-6;
  q4 = fsm_div(T, isFx, n4, d4);
  a_cah = cast(a_l_bar - q4, 'like', T.acc);
  a_cah = cast(min(max(a_cah, -9), af), 'like', T.acc);

  % --- q5 -> dd ---
  n5 = a_iidm - a_cah;   d5 = bf + 1e-6;
  q5 = fsm_div(T, isFx, n5, d5);
  dd = cast(q5, 'like', T.acc);

  a_blend = cast((1-COOL)*a_iidm + COOL*(a_cah + bf*tanh(dd)), 'like', T.acc);
  if a_iidm >= a_cah, ac = a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), af), 'like', T.out);
end


function q = fsm_div(T, isFx, num, den)
%FSM_DIV  La divisione della forma FSM. Nel model: divide() (identica a acc_div con recipN=0, cioe' SP3).
%  Nella chart del blocco: sostituita dall'handshake verso HDLMathLib/Divide, che G1 ha provato
%  bit-identico a divide() (ShiftAdd + RndMeth 'Zero' + OutType T.acc, dmax=0 su 300k coppie reali).
%  NB: il reciproco-LUT (acc_types.recipN>0, variante L) NON e' contemplato: M usa la divisione ESATTA.
  if isFx
    q = divide(numerictype(T.acc), num, den);
  else
    q = num / den;
  end
end
