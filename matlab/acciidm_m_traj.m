function A = acciidm_m_traj(val, hold) %#codegen
%ACCIIDM_M_TRAJ  Golden FEDELE al blocco Donatello_ACC_IIDM_M: guida l'algoritmo esatto della chart
%  (acciidm_m_algo, estratto verbatim) clock-per-clock, tenendo gli ingressi fisici `hold` clock per
%  control-step -- ESATTAMENTE come il blocco. Cattura l'accel a fine control-step. Gemello di
%  snn_traj_champion per il controllore (1 uscita accel invece di 5 param).
%
%  val  : 4 x N  ingressi FISICI [s; v; dv; v_l]   (quantizzati a fixdt(1,32,20))
%  hold : clock per control-step (>= latenza ~358; usare lo stesso HOLD del testbench RTL)
%  A    : N x 1  accel (Q4.8) per control-step
%
%  ⚠️ Stato ricorrente `persistent` (SNN + filtro OU) in acciidm_m_algo: `clear acciidm_m_traj_mex` a
%     inizio traiettoria. 1o control-step presentato dal primo clock (niente fase a ingresso 0).
  N  = size(val, 2);
  A  = zeros(N, 1);
  Ta = acc_types('fixed');                 % la fimath di accel ('Zero'/'fix') fa parte del tipo:
  for k = 1:N                              %   init con default 'nearest' -> mismatch al codegen (SP4 §gotcha)
    sk = fi(val(1,k), 1, 32, 20); vk = fi(val(2,k), 1, 32, 20);
    dk = fi(val(3,k), 1, 32, 20); lk = fi(val(4,k), 1, 32, 20);
    accel = cast(0, 'like', Ta.out);
    for cc = 1:hold
      accel = acciidm_m_algo(sk, vk, dk, lk);
    end
    A(k) = double(accel);
  end
end
