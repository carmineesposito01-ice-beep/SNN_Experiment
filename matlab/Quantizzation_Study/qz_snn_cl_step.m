function [p, accel] = qz_snn_cl_step(x_phys, W, rst, nfrac) %#codegen
%QZ_SNN_CL_STEP  [Quantizzation_Study] Copia di snn_cl_step con nfrac PARAMETRICO (coder.Constant per il MEX).
%  UN control-step: normalize (float) -> snn_core (fixed a nfrac) -> decode LUT-64 -> acc_iidm_open (IIDM).
%  Identico a snn_cl_step salvo che il word-length frazionario e' un argomento, non il 13 hardcoded.
  T = snn_types('fixed', nfrac);
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('fixed')));
end
