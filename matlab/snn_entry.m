function p = snn_entry(dt, x_phys, W)
%SNN_ENTRY  Entry-point type-parametrizzato: cast ai bordi -> core -> decode.
%  dt: 'double'|'fixed'. x_phys [4x1] fisico. W: struct pesi/config del champion.
%  Ritorna p [5x1] parametri fisici. Lo stato persistente vive dentro snn_core.
  T   = snn_types(dt);
  xn  = snn_normalize(x_phys, W.norm);
  xn  = cast(xn, 'like', T.V);
  raw = snn_core(xn, W, T);                        % [5x1] potenziale LI (ultimo tick)
  p   = snn_decode(double(raw), W.param_lo, W.param_hi, W.decode_offset, W.logit_tau);
end
