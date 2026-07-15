function [p, accel] = snn_cl_step(x_phys, W, rst) %#codegen
%SNN_CL_STEP  UN control-step della catena di riferimento, compilabile (-> snn_cl_step_mex):
%  normalize (float, come il PS) -> snn_core (fixed) -> decode LUT-64 -> acc_iidm_open (double).
%    x_phys : [s; v; dv; v_l] fisici (4x1 double)
%    W      : struct pesi del champion (champ_weights)
%    rst    : true al primo passo -> azzera lo stato di snn_core e del filtro OU
%    p      : [v0;T;s0;a;b] stimati (5x1) · accel : [m/s^2]
%
%  Perche' non basta `snn_traj_fixed`: quello macina una traiettoria GIA' NOTA. In anello CHIUSO
%  l'ingresso del passo k+1 dipende dall'uscita del passo k, quindi serve passo-passo. E in fi
%  interpretato un passo costa ~6 s (il loop fi e' il collo di bottiglia, vedi snn_traj_fixed):
%  senza MEX un anello da 200 passi non e' eseguibile.
%
%  E' il riferimento SW dell'anello: il blocco Simulink `Donatello_ACC_IIDM` deve riprodurlo.
  T = snn_types('fixed', 13);
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);   % reset (flag logico, come snn_traj_fixed:11)
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);                            % 64 = decode del campione
  p   = double(pf(:));
  % IIDM in FIXED: e' il riferimento del BLOCCO, che dal 2026-07-16 (SP3) e' fixed e HDL-ready.
  % La distanza fixed-vs-double NON si misura qui: e' un cancello a se', `run_acc_fixed_sweep`.
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('fixed')));
end
