function M = probe_dd_range(trajList)
%PROBE_DD_RANGE  [B2.0-2b Esp.A] Range EMPIRICO di st.dd (argomento del tanh) sul dataset, per
%  DIMENSIONARE la tanh-LUT. dd = divide(a_iidm - a_cah, bf+1e-6) in T.acc (sfix19_En8), NON clampato.
%  Riusa i forward SNN (snn_traj_b2, MEX) + le funzioni-fase FIXED single-source (iidm_prep/nd/use,
%  fsm_div) -- nessuna duplicazione di matematica. Registra st.dd per ogni control-step.
  if nargin < 1 || isempty(trajList), trajList = 1:20; end
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),ch),1));
  nrm = double(c.norm(:)); Tp = numerictype(1,21,13);
  gen_b2_rom('Donatello'); clear snn_traj_b2_mex; rehash;                  % ROM attiva = Donatello
  valt = coder.typeof(zeros(4,1000),[4 Inf],[false true]);
  evalc("codegen('snn_traj_b2','-args',{valt,coder.typeof(zeros(4,1))},'-o','snn_traj_b2_mex')");
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  T = acc_types('fixed');

  dd = [];
  for t = trajList(:).'
    valq = fi(double(tr{t}.val), 1, 32, 20);      % ingresso fisico come il blocco (fixdt(1,32,20))
    R = double(snn_traj_b2_mex(tr{t}.val, nrm));   % readout SNN per control-step
    K = size(R,1);
    alf = cast(0,'like',T.acc); vlp = cast(valq(4,1),'like',T.st);   % stato OU, reset per traiettoria
    ddt = zeros(K,1);
    for k = 1:K
      p = snn_decode_lut(fi(R(k,:).',Tp), 64);
      [st, alf, vlp] = iidm_prep(valq(1,k), valq(2,k), valq(3,k), valq(4,k), p(:), k==1, alf, vlp);
      for kk = 1:5
        [num,den] = iidm_nd(kk, st);
        q = fsm_div(num, den);
        st = iidm_use(kk, q, st);
      end
      ddt(k) = double(st.dd);
    end
    dd = [dd; ddt]; %#ok<AGROW>
    fprintf('  traj %-3d: %d step, |dd|max=%.4g\n', t, K, max(abs(ddt)));
  end

  % tanh satura bit-identico in sfix19_En17 quando 1-|tanh(x)| < 2^-18  ->  |x| > atanh(1-2^-18)
  xsat = atanh(1 - 2^-18);
  nz   = sum(abs(dd) < xsat);
  M = struct('min',min(dd),'max',max(dd),'absmax',max(abs(dd)), ...
             'p001',prctile(dd,0.1),'p999',prctile(dd,99.9),'n',numel(dd),'xsat',xsat, ...
             'frac_saturated',mean(abs(dd)>=xsat));
  fprintf(['\n==== RANGE st.dd (arg del tanh) su %d control-step (%d traj) ====\n' ...
           '  min=%.5g  max=%.5g  |dd|max=%.5g\n' ...
           '  p0.1=%.5g  p99.9=%.5g\n' ...
           '  tanh satura (bit-identico in sfix19_En17) per |dd| > %.4g\n' ...
           '  campioni SATURI: %.2f%%  (la LUT li copre con 2 costanti)\n' ...
           '  -> LUT non-satura: |dd| < %.4g a risoluzione 2^-8  =>  ~%d entry\n'], ...
    M.n, numel(trajList), M.min, M.max, M.absmax, M.p001, M.p999, xsat, ...
    100*M.frac_saturated, min(xsat,M.absmax), ceil(2*min(xsat,M.absmax)*256));
end
