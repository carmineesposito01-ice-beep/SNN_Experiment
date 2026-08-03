function W = gen_power_workloads(nStep, outdir)
%GEN_POWER_WORKLOADS  Stimoli per lo studio energetico (T6b/M3): 9 workload REALI + 1 worst sintetico.
%  I 9 = una traiettoria per ciascuna COMBINAZIONE scenario x profilo popolata del dataset dei 60 (sono 9,
%  non 8: conteggio verificato 2026-07-29). La fase ATTIVA dipende dal workload (tassi di spike diversi ->
%  commutazione diversa), quindi va misurata su tutti e 9; la fase IDLE non dipende dai dati (stato stazionario,
%  commuta solo l'albero del clock) -> una misura per stato di gating, non 9.
%  Il worst e' un limite superiore: gap minimo, dv molto negativo, v alta.
%  ⚠️ Il worst ALTERNA fra due valori vicini: ingressi bit-identici non generano fronte e il Tier non
%     rilancerebbe l'inferenza (edge-trigger, HDL_PHASE §3.1.4) -> misurerei un idle travestito da worst.
%  Scrive stim_pw_<i>.mem / gold_pw_<i>.mem (i=1..10) + meta_pw.mat con l'elenco dichiarato dei workload.
  if nargin<1||isempty(nStep),  nStep  = 50; end
  if nargin<2||isempty(outdir), outdir = 'D:/zbd_tier_hw'; end
  here = fileparts(mfilename('fullpath'));
  addpath(fullfile(here,'..','..','..','matlab'));      % tier_golden_cache, test_dataset
  addpath(fullfile(here,'..','..','common'));           % rtl_write_vectors
  ds = load(fullfile(here,'..','..','..','matlab','test_dataset.mat')); tr = ds.trajectories;
  N = numel(tr);

  % --- una traiettoria per combinazione scenario x profilo (le 9 popolate) ---
  key = strings(N,1);
  for t = 1:N, key(t) = string(tr{t}.scenario) + "|" + string(tr{t}.profile); end
  [uk, ia] = unique(key, 'stable');
  trajList = ia(:).';
  fprintf('gen_power_workloads: %d combinazioni scenario x profilo -> traj %s\n', numel(trajList), mat2str(trajList));

  P = tier_golden_cache(trajList);                       % stesso oracolo/cache di T6a e M1
  Tp = numerictype(1,21,13);
  W = struct('idx',{},'traj',{},'label',{});
  for i = 1:numel(trajList)
    K = min(nStep, size(tr{trajList(i)}.val,2));
    stim = fi(double(tr{trajList(i)}.val(:,1:K)), 1, 32, 20);
    gold = fi(P{i}(1:K,:).', Tp);
    rtl_write_vectors(outdir, sprintf('pw_%d', i), stim, 32, gold, 21);
    W(end+1) = struct('idx',i, 'traj',trajList(i), 'label',char(uk(i))); %#ok<AGROW>
  end

  % --- worst sintetico (limite superiore): alto firing, con alternanza per garantire il fronte ---
  iw = numel(trajList) + 1;
  s_w  = [2.0  2.1];  v_w = [35.0 34.9];  dv_w = [-15.0 -14.9];  vl_w = [20.0 20.1];
  raw = zeros(4, nStep);
  for k = 1:nStep
    j = mod(k-1,2) + 1;
    raw(:,k) = [s_w(j); v_w(j); dv_w(j); vl_w(j)];
  end
  stim = fi(raw, 1, 32, 20);
  gold = fi(zeros(5, nStep), Tp);        % la potenza non richiede golden: placeholder (il TB non lo usa qui)
  rtl_write_vectors(outdir, sprintf('pw_%d', iw), stim, 32, gold, 21);
  W(end+1) = struct('idx',iw, 'traj',0, 'label','WORST-sintetico(alto firing)');

  labels = {W.label}; trajs = [W.traj]; %#ok<NASGU>
  save(fullfile(outdir,'meta_pw.mat'), 'labels', 'trajs', 'nStep');
  fprintf('gen_power_workloads: %d workload x %d control-step -> %s\n', numel(W), nStep, outdir);
  for i=1:numel(W), fprintf('   pw_%-2d  traj %-3d  %s\n', W(i).idx, W(i).traj, W(i).label); end
end
