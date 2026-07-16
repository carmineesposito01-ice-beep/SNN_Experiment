function [accel, pairs] = collect_step(s, v, dv, v_l, p, rst) %#codegen
%COLLECT_STEP  [SP4-M-FSM G1] Wrapper MEX-abile di acc_iidm_open con T=acc_types('fixed') COSTRUITO DENTRO
%  (coder.const) -> recipN=0 e' costante -> acc_div specializza al ramo divide() e il ramo reciproco-LUT
%  (variante L, acc_recip_lut) NON viene compilato (con T come arg lo era, e non si riduce a costante).
%  Serve a estrarre le coppie (num,den) VELOCE: 60000 chiamate MEX invece del fi interpretato (~47 min).
%  Stessa matematica di acc_iidm_open (single-source, nessuna duplicazione).
  T = acc_types('fixed');
  [accel, pairs] = acc_iidm_open(s, v, dv, v_l, p, rst, T);
end
