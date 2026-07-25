function qz_mp_gate_selftest()
%QZ_MP_GATE_SELFTEST  Il cancello ACCETTA il full-precision (Δgap=0) e RIFIUTA una config cattiva.
%  Provato NEI DUE SENSI: un cancello che non ha mai fallito non e' un cancello.
  a13 = qz_mp_gate([13 13 13 13 13 13], 1:99);
  assert(a13.maxdgap == 0 && a13.pass, 'il cancello non accetta il full-precision');
  a2  = qz_mp_gate([2 2 2 2 2 2], 1:99);   % nfrac unico n2: max|Δgap| ~31 m (studio unico) -> deve FALLIRE
  assert(~a2.pass && a2.maxdgap > 0.5, 'il cancello non rifiuta la config a 2 bit (maxdgap=%.3g)', a2.maxdgap);
  fprintf('GATE detector: accetta @13 (dgap=%.2g), rifiuta @2 (dgap=%.2g m) -> OK\n', a13.maxdgap, a2.maxdgap);
end
