function [p, accel] = qz_snn_cl_step_mp(x_phys, W, rst, nf) %#codegen
%QZ_SNN_CL_STEP_MP  [Quantizzation_Study] Copia di qz_snn_cl_step con tipi PER-CAMPO (qz_snn_types_mp).
%  nf = [nV nfat nacc naccw nraw nw], passato come coder.Constant per il MEX. Decode fisso En13.
  T = qz_snn_types_mp('fixed', nf);
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('fixed')));
end
