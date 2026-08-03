function [p, accel] = qzi_cl_step(x_phys, W, rst, nfrac) %#codegen
%QZI_CL_STEP  [Quantizzation_Study_IIDM] UN control-step per lo studio SPECCHIATO:
%  la SNN e' CONGELATA a piena precisione (fixed nfrac=13) e varia SOLO l'nfrac dell'IIDM.
%  normalize (float) -> snn_core (fixed@13) -> decode LUT-64 -> acc_iidm_open (IIDM a nfrac).
%  Specchio di qz_snn_cl_step: li' l'nfrac pilotava la RETE (IIDM fisso@8); qui pilota l'IIDM
%  (RETE fissa@13). nfrac e' coder.Constant nel MEX.
  T = snn_types('fixed', 13);                          % SNN congelata: piena precisione
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), ...
                               p, rst, acc_types('fixed', nfrac)));   % IIDM a nfrac
end
