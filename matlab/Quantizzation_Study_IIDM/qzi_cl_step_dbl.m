function [p, accel] = qzi_cl_step_dbl(x_phys, W, rst) %#codegen
%QZI_CL_STEP_DBL  [Quantizzation_Study_IIDM] Come qzi_cl_step ma con l'IIDM in DOUBLE (riferimento).
%  SNN congelata @13 (fixed) -> decode LUT-64 -> acc_iidm_open in DOUBLE. Serve al riferimento dello
%  sweep open-loop: accel(IIDM@nfrac) vs accel(IIDM double) a PARITA' di params (SNN@13). MEX per velocita'.
  T = snn_types('fixed', 13);
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), ...
                               p, rst, acc_types('double')));
end
