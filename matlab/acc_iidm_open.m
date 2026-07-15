function accel = acc_iidm_open(s, v, dv, v_l, p, rst) %#codegen
%ACC_IIDM_OPEN  ACC-IIDM **open-loop**: accel = f(stato, parametri). NON integra v ne' s.
%  s, v, dv, v_l : stato fornito DA FUORI (il loop lo chiude il sistema che testa)
%  p             : [v0; T; s0; a; b]
%  rst           : true -> azzera lo stato del filtro OU (inizio di una nuova traiettoria)
%
%  E' l'UNICA fonte della matematica ACC-IIDM del progetto: la usa sia il blocco SP2
%  `Donatello_ACC_IIDM` sia il plant closed-loop `cf_plant_lib/ACC_IIDM` (che aggiunge solo
%  l'integrazione). Cancello che verifica entrambi: `run_plant_parity` (vs golden Python).
%
%  ⚠️ DA CHIAMARE **UNA VOLTA PER CONTROL-STEP** (DT = 0.1 s): il filtro OU stima a_l da Δv_l/DT.
%     Chiamarla a ogni clock farebbe vedere Δv_l = 0 per 340 campioni su 341 -> a_l ~ 0, in silenzio.
%     Vedi docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md §5.
  DT = 0.1; ALPHA = exp(-DT/1.0); COOL = 0.99;
  v0 = max(p(1), 1e-3); T = max(p(2), 1e-3); s0 = p(3); a = max(p(4), 1e-3); b = max(p(5), 1e-3);

  % Init con guardia `isempty` PER VARIABILE (idioma codegen-safe del progetto, come snn_core.m:15-19):
  % il codegen riconosce letteralmente isempty(<persistent>) come prova di definizione, e senza fallisce
  % con "Persistent variable 'alf' is undefined on some execution paths". `rst` azzera il filtro OU
  % a inizio traiettoria; al primo giro ci pensa gia' isempty, quindi non serve un flag `started`.
  persistent alf vlp
  if isempty(alf) || rst, alf = 0;   end
  if isempty(vlp) || rst, vlp = v_l; end
  % stima a_l (filtro OU su differenze finite del leader)
  alf = ALPHA*alf + (1-ALPHA)*((v_l - vlp)/DT); vlp = v_l;

  % --- acc_iidm_accel: IIDM base + CAH + blend ACC (verbatim da build_plant_lib:plant_code) ---
  sab = max(sqrt(a*b), 1e-6);
  s_star = s0 + max(v*T + v*dv/(2*sab), 0);
  s_safe = max(s, 2.0);
  v_free = a*(1 - min(v/v0, 10)^4);
  z = min(s_star/s_safe, 20);
  below = (v <= v0);
  a_z = a*(1 - z^2);
  if z < 1
    if below, a_iidm = v_free*(1 - z^2); else, a_iidm = v_free; end
  else
    if below, a_iidm = a_z; else, a_iidm = v_free + a_z; end
  end
  a_l_bar = min(alf, a);
  a_cah = a_l_bar - max(dv,0)^2/(2*s_safe + 1e-6);
  a_cah = min(max(a_cah, -9), a);
  dd = (a_iidm - a_cah)/(b + 1e-6);
  a_blend = (1-COOL)*a_iidm + COOL*(a_cah + b*tanh(dd));
  if a_iidm >= a_cah, accel = a_iidm; else, accel = a_blend; end
  accel = min(max(accel, -9), a);
end
