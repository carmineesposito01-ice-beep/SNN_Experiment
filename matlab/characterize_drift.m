function M = characterize_drift(trajList)
%CHARACTERIZE_DRIFT  [Fase B2.0] Caratterizza la deriva del BLOCCO FISICO (local_normalize fixed +
%  pilotaggio a ingresso tenuto) vs il RIFERIMENTO/deployato (snn_normalize + forward serializzato)
%  sull'ACCEL, sul dataset. Da' la risposta "trascurabile o no": |Δaccel| confrontato col budget E_snn
%  (footprint in accel della quantizzazione GIA' accettata della rete, da acc_types.m). Se |Δaccel| e'
%  molto sotto E_snn, la deriva e' dominata dalla rete stessa -> trascurabile.
%
%  Blocco     = acciidm_m_traj (local_normalize, ingresso tenuto)   -- cio' che valida Harness A/B.
%  Riferimento= snn_traj_b2 (snn_normalize, serializzato) -> decode -> collect_step (IIDM)  -- il deployato.
  if nargin < 1 || isempty(trajList), trajList = 1:20; end
  here = fileparts(mfilename('fullpath'));
  build_acciidm_m_golden();                                   % controllore fedele al blocco (local_normalize)
  d = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),ch),1));
  W = champ_weights(c); nrm = double(c.norm(:)); Tp = numerictype(1,21,13);
  % forward di riferimento (snn_normalize) ricompilato per Donatello (bake ROM, come run_b2_parity_dataset)
  gen_b2_rom('Donatello'); clear snn_traj_b2_mex; rehash;
  valt = coder.typeof(zeros(4,1000),[4 Inf],[false true]);
  evalc("codegen('snn_traj_b2','-args',{valt,coder.typeof(zeros(4,1))},'-o','snn_traj_b2_mex')");
  assert(~isempty(which('collect_step_mex')), 'MEX mancante: build_acc_iidm_fsm_mex');
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;

  err = [];
  for t = trajList(:).'
    val = double(fi(double(tr{t}.val),1,32,20));
    clear acciidm_m_traj_mex; A_blk = acciidm_m_traj_mex(tr{t}.val, 500);    % blocco (local_normalize)
    clear snn_traj_b2_mex;    R = double(snn_traj_b2_mex(tr{t}.val, nrm));    % riferimento (snn_normalize)
    clear collect_step_mex;
    A_ref = zeros(numel(A_blk),1);
    for k = 1:numel(A_blk)
      p = double(snn_decode_lut(fi(R(k,:).',Tp),64));
      A_ref(k) = collect_step_mex(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1);
    end
    err = [err; abs(A_blk(:) - A_ref(:))]; %#ok<AGROW>
  end
  M = struct('max',max(err),'p99',prctile(err,99),'p50',median(err),'mean',mean(err),'n',numel(err));
  E_snn_p99 = 0.272054; E_snn_max = 1.48433;                  % budget E_snn (acc_types.m, 60k campioni)
  fprintf(['\nDERIVA blocco-fisico vs riferimento/deployato sull''ACCEL (%d control-step, %d traj):\n' ...
           '  |Δaccel|   max=%.4g   p99=%.4g   mediana=%.4g   media=%.4g   [m/s^2]\n' ...
           '  budget E_snn (quantizzazione rete):  p99=%.4g   max=%.4g\n' ...
           '  deriva / budget:  p99 = %.1f%%   max = %.1f%%\n'], ...
    M.n, numel(trajList), M.max, M.p99, M.p50, M.mean, E_snn_p99, E_snn_max, ...
    100*M.p99/E_snn_p99, 100*M.max/E_snn_max);
end
