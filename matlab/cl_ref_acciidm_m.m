function ref = cl_ref_acciidm_m(trajIdx, K, hold, dvMode)
%CL_REF_ACCIIDM_M  [Fase B2.0-2a-M2 B.2] Anello chiuso di RIFERIMENTO, block-faithful, per Harness B:
%  controllore = acciidm_m_traj (l'algoritmo ESATTO del blocco Donatello_ACC_IIDM_M, guidato clock-per-
%  clock, chiamato UN control-step alla volta con lo stato che persiste) + plant EGO IDENTICO a
%  run_block_closed_loop_test.cl_matlab. Produce la traiettoria golden (s,v,dv,accel) + il profilo del
%  leader + le costanti, che il testbench RTL closed-loop dovra' riprodurre.
%
%  ⚠️ Perche' non riuso cl_matlab: quello usa snn_cl_step_mex (controllore SP2 "generale"); qui serve il
%     controllore FEDELE al blocco M (stessa local_normalize + pilotaggio a ingresso tenuto, lezione M1).
%  dvMode: 'train' (convenzione dataset, v PRIMA dell'update) | 'inst' (fisica istantanea).
  if nargin < 1 || isempty(trajIdx), trajIdx = 1; end
  if nargin < 2 || isempty(K),       K = 200;     end
  if nargin < 3 || isempty(hold),    hold = 500;  end
  if nargin < 4 || isempty(dvMode),  dvMode = 'train'; end
  assert(~isempty(which('acciidm_m_traj_mex')), 'MEX golden mancante: esegui build_acciidm_m_golden');
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  t = tr{trajIdx}; val = double(t.val); gt = double(t.gt_params);
  assert(K <= size(val,2), 'K=%d > lunghezza traiettoria (%d)', K, size(val,2));

  % costanti dell'anello (identiche a cl_setup di run_block_closed_loop_test)
  DT = 0.1; S_MAX = 150; s_lo = 0.5*gt(3); v_cap = 1.2*gt(1);
  xe0 = -val(1,1); ve0 = val(2,1);
  vl = val(4,1:K).'; xl = zeros(K,1);
  for k = 2:K, xl(k) = xl(k-1) + vl(k)*DT; end             % leader integrato con la v_l NUOVA

  q = @(x) floor(x * 2^20) / 2^20;                          % Data Type Conversion a fixdt(1,32,20), Floor
  xe = xe0; ve = ve0; ve_prev = ve0;
  clear acciidm_m_traj_mex;                                 % stato ricorrente (SNN+OU) da zero
  ref.s = zeros(K,1); ref.v = zeros(K,1); ref.dv = zeros(K,1); ref.accel = zeros(K,1);
  for k = 1:K
    s = min(max(xl(k) - xe, s_lo), S_MAX);
    if strcmp(dvMode,'train'), dvk = ve_prev - vl(k); else, dvk = ve - vl(k); end
    xq  = q([s; ve; dvk; vl(k)]);                           % ingressi quantizzati (fixdt(1,32,20))
    acc = acciidm_m_traj_mex(xq, hold);                     % accel del blocco (1 control-step, stato persiste)
    ref.s(k)=xq(1); ref.v(k)=xq(2); ref.dv(k)=xq(3); ref.accel(k)=acc;
    xe_new  = xe + ve*DT;                                   % balistico: v VECCHIA
    ve_new  = min(max(ve + acc*DT, 0), v_cap);
    ve_prev = ve; xe = xe_new; ve = ve_new;
  end
  ref.vl=vl; ref.xl=xl; ref.s_lo=s_lo; ref.v_cap=v_cap; ref.xe0=xe0; ref.ve0=ve0; ref.DT=DT; ref.S_MAX=S_MAX;
  fprintf(['CL-REF traj=%-3d K=%-4d: gap=[%.2f %.2f] m  v_ego=[%.2f %.2f]  v_lead=[%.2f %.2f] m/s  ' ...
           'accel=[%.2f %.2f]\n'], trajIdx, K, min(ref.s),max(ref.s), min(ref.v),max(ref.v), ...
           min(vl),max(vl), min(ref.accel),max(ref.accel));
  assert(all(isfinite(ref.s)) && all(isfinite(ref.v)), 'anello divergente: stato non finito');
  assert(min(ref.s) > 0, 'COLLISIONE nell''anello di riferimento (gap minimo %.3f <= 0)', min(ref.s));
end
