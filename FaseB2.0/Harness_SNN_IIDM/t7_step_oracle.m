function f = t7_step_oracle(gt_params)
%T7_STEP_ORACLE  stepFun per qz_cl_sim: controllore IDEALE (IIDM analitico coi parametri veri).
%  E' la BASELINE di qualita' di T7a: il controllore a conoscenza perfetta, contro cui si misura il
%  costo dell'usare la SNN come estimatore. Stessa forma usata da qz_cl_parity_gate, che ne prova la
%  parita' col simulate() canonico Python (rieseguito il 2026-07-30: max|ds| = 2,24e-06 m).
%
%  gt_params : 1x5 o 5x1  [v0 T s0 a b] veri dello scenario
%  f         : @(x_phys, rst) -> [params(5), accel]   (contratto stepFun di qz_cl_sim)
  p = gt_params(:);
  f = @(x, rst) deal(p, double(acc_iidm_open(x(1), x(2), x(3), x(4), p, rst, acc_types('double'))));
end
