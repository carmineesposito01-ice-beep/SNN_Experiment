function qz_cl_validate(levels, trajList)
%QZ_CL_VALIDATE  [Quantizzation_Study] Validazione car-following della quantizzazione in ANELLO CHIUSO
%  FEDELE (qz_cl_sim, port di utils/closed_loop_eval.simulate()), sul dataset ESAUSTIVO (9 scenari
%  canonici, con i 3 cut-in a teletrasporto di gap). Per ogni nfrac, su tutte le traiettorie:
%   - SICUREZZA vs BASELINE ORACOLO per-traiettoria (params veri = cosa e' FISICAMENTE evitabile):
%       coll_extra = collisioni che l'oracolo EVITA ma la rete no  ->  COSTO REALE della quantizzazione.
%       oltre a: coll_total, min_gap e brake_margin sui casi evitabili, max_DRAC.
%   - RETE: NRMSE per-parametro (v0,T,s0,a,b) vs riferimento nfrac=13.
%  Anello provato fedele: qz_cl_parity_gate (max|Δs| ~2e-6 m vs simulate() Python). Ingressi NON quantizzati
%  (come simulate): lo studio varia il SOLO nfrac del core.
  if nargin < 1 || isempty(levels),   levels   = [2 3 4 5 6 7 8 9 10 11 12 13]; end
  if nargin < 2 || isempty(trajList), trajList = []; end
  here  = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories;
  if isempty(trajList), trajList = 1:numel(tr); end
  T = tr(trajList); nt = numel(T);
  names = cellfun(@(x) x.name, T, 'UniformOutput', false);

  % --- 0) baseline ORACOLO: cosa e' fisicamente evitabile (per-traiettoria) ---
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));
  Bcoll = false(1,nt);
  for i = 1:nt
    o = qz_cl_sim(T{i}, oracle(T{i}.gt_params)); Bcoll(i) = o.collided;
  end
  avoid = ~Bcoll;
  fprintf('baseline oracolo: %d/%d traiettorie inevitabili (collidono anche con params veri)\n', sum(Bcoll), nt);

  % --- 1) MEX per ogni livello (se manca) ---
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
  for f = levels
    mx = sprintf('qz_snn_cl_step_n%d_mex', f);
    if isempty(which(mx))
      fprintf('build %s ...\n', mx);
      codegen('qz_snn_cl_step','-config',cfg, ...
              '-args',{zeros(4,1),coder.typeof(W),true,coder.Constant(f)}, ...
              '-o',mx,'-d',['codegen_n' num2str(f)]);
    end
  end

  % --- 2) riferimento nfrac=13 (params per NRMSE) ---
  assert(ismember(13,levels), 'serve nfrac=13 come riferimento NRMSE');
  fun13 = str2func('qz_snn_cl_step_n13_mex');
  Pref = cell(1,nt);
  for i = 1:nt, o = qz_cl_sim(T{i}, @(x,rst) fun13(x,W,rst,13)); Pref{i} = o.params; end
  allP = cell2mat(Pref(:)); prng = max(allP,[],1) - min(allP,[],1); prng(prng==0) = 1;

  % --- 3) sweep livelli ---
  rows = [];
  extraNamesByLevel = containers.Map('KeyType','double','ValueType','any');
  for f = levels
    fun = str2func(sprintf('qz_snn_cl_step_n%d_mex', f));
    coll = false(1,nt); mg = zeros(1,nt); bm = zeros(1,nt); dr = zeros(1,nt);
    num = zeros(1,5); den = 0;
    for i = 1:nt
      o = qz_cl_sim(T{i}, @(x,rst) fun(x,W,rst,f));
      m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
      coll(i)=m.collided; mg(i)=m.min_gap; bm(i)=m.brake_margin_min; dr(i)=m.max_DRAC;
      Pf = o.params; Pr = Pref{i}; n = min(size(Pf,1), size(Pr,1));
      num = num + sum((Pf(1:n,:) - Pr(1:n,:)).^2, 1); den = den + n;
    end
    nrmse = sqrt(num/den) ./ prng;
    extra = coll & ~Bcoll;
    mgA = mg(avoid); bmA = bm(avoid);
    rows(end+1,:) = [f, sum(coll), sum(extra), ...
                     min([mgA, inf]), min([bmA, inf]), max([dr,0]), nrmse, mean(nrmse)]; %#ok<AGROW>
    extraNamesByLevel(f) = names(extra);
    fprintf('nfrac=%2d: coll_tot=%d coll_extra=%d\n', f, sum(coll), sum(extra));
  end

  % --- 4) tabella + TSV ---
  rows = sortrows(rows, 1);
  fid = fopen(fullfile(here,'cl_sweep.tsv'),'w');
  fprintf(fid,['nfrac\tcoll_total\tcoll_extra\tmin_gap_avoid\tbrake_margin_avoid\tmax_DRAC\t' ...
               'NRMSE_v0\tNRMSE_T\tNRMSE_s0\tNRMSE_a\tNRMSE_b\tNRMSE_mean\n']);
  fprintf('\n=== SWEEP QUANTIZZAZIONE  anello fedele, dataset esaustivo (%d traj, %d inevitabili x oracolo) ===\n', nt, sum(Bcoll));
  fprintf('nfrac | coll_tot | coll_EXTRA | min_gap(ev) | brake_marg(ev) | max_DRAC || NRMSE mean\n');
  fprintf('%s\n', repmat('-',1,92));
  for r = 1:size(rows,1)
    v = rows(r,:);
    fprintf('%5d | %8d | %10d | %11.3f | %14.3f | %8.2f || %8.4f\n', v(1),v(2),v(3),v(4),v(5),v(6),v(12));
    fprintf(fid,'%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.6g\t%.6g\t%.6g\t%.6g\t%.6g\t%.6g\n', ...
            v(1),v(2),v(3),v(4),v(5),v(6),v(7),v(8),v(9),v(10),v(11),v(12));
  end
  fclose(fid);
  % quali scenari rompono (collisione EXTRA rispetto all'oracolo), per livello
  fprintf('\nscenari con collisione EXTRA (rete collide, oracolo no):\n');
  for r = 1:size(rows,1)
    f = rows(r,1); en = extraNamesByLevel(f);
    if ~isempty(en)
      u = unique(en); cnt = cellfun(@(s) sum(strcmp(en,s)), u);
      lst = strjoin(arrayfun(@(a,b) sprintf('%s×%d', a{1}, b), u, cnt, 'UniformOutput',false), ', ');
      fprintf('  nfrac=%2d: %s\n', f, lst);
    end
  end
  fprintf('\nscritto %s\n', fullfile(here,'cl_sweep.tsv'));
end
