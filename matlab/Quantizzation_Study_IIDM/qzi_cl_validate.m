function qzi_cl_validate(levels, trajList)
%QZI_CL_VALIDATE  [Quantizzation_Study_IIDM] Studio SPECCHIATO in anello chiuso fedele (qz_cl_sim),
%  SNN congelata @13, IIDM a nfrac. Su dataset esaustivo, per ogni nfrac:
%   - SICUREZZA vs baseline ORACOLO per-traiettoria (gt_params): coll_extra = collisioni che
%     l'oracolo evita ma la rete+IIDM-quantizzato no -> costo reale della quantizzazione IIDM.
%   - FEDELTA': NRMSE dell'ACCEL (uscita IIDM) vs riferimento IIDM nfrac=13.
%  Anello provato fedele (qz_cl_parity_gate). Ingressi NON quantizzati (come simulate).
  if nargin < 1 || isempty(levels),   levels   = [13 8 5 2]; end
  if nargin < 2 || isempty(trajList), trajList = []; end
  here  = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  qzdir = fullfile(mroot, 'Quantizzation_Study');           % dataset + funzioni condivise
  addpath(mroot); addpath(here); addpath(qzdir);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(qzdir,'test_dataset_exhaustive.mat')); tr = ds.trajectories;
  if isempty(trajList), trajList = 1:numel(tr); end
  T = tr(trajList); nt = numel(T);
  names = cellfun(@(x) x.name, T, 'UniformOutput', false);

  % --- 0) baseline ORACOLO: cosa e' fisicamente evitabile (gt_params + IIDM double) ---
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));
  Bcoll = false(1,nt);
  for i = 1:nt, o = qz_cl_sim(T{i}, oracle(T{i}.gt_params)); Bcoll(i) = o.collided; end
  avoid = ~Bcoll;
  fprintf('baseline oracolo: %d/%d traiettorie inevitabili\n', sum(Bcoll), nt);

  % --- 1) MEX per ogni livello IIDM (se manca) ---
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
  for f = levels
    mx = sprintf('qzi_cl_step_n%d_mex', f);
    if isempty(which(mx))
      fprintf('build %s ...\n', mx);
      codegen('qzi_cl_step','-config',cfg, ...
              '-args',{zeros(4,1),coder.typeof(W),true,coder.Constant(f)}, ...
              '-o',mx,'-d',['codegen_ni' num2str(f)]);
    end
  end

  % --- 2) riferimento IIDM nfrac=13 (accel per NRMSE) ---
  assert(ismember(13,levels), 'serve nfrac=13 come riferimento NRMSE');
  fun13 = str2func('qzi_cl_step_n13_mex');
  Aref = cell(1,nt);
  for i = 1:nt, o = qz_cl_sim(T{i}, @(x,rst) fun13(x,W,rst,13)); Aref{i} = o.series.a(:); end
  allA = cell2mat(Aref(:)); arng = max(allA) - min(allA); if arng==0, arng = 1; end

  % --- 3) sweep livelli ---
  rows = [];
  extraNamesByLevel = containers.Map('KeyType','double','ValueType','any');
  for f = levels
    fun = str2func(sprintf('qzi_cl_step_n%d_mex', f));
    coll = false(1,nt); mg = zeros(1,nt); bm = zeros(1,nt); dr = zeros(1,nt);
    num = 0; den = 0;
    for i = 1:nt
      o = qz_cl_sim(T{i}, @(x,rst) fun(x,W,rst,f));
      m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
      coll(i)=m.collided; mg(i)=m.min_gap; bm(i)=m.brake_margin_min; dr(i)=m.max_DRAC;
      Af = o.series.a(:); Ar = Aref{i}; n = min(numel(Af), numel(Ar));
      num = num + sum((Af(1:n) - Ar(1:n)).^2); den = den + n;
    end
    nrmse = sqrt(num/den) / arng;
    extra = coll & ~Bcoll;
    mgA = mg(avoid); bmA = bm(avoid);
    rows(end+1,:) = [f, sum(coll), sum(extra), min([mgA, inf]), min([bmA, inf]), max([dr,0]), nrmse]; %#ok<AGROW>
    extraNamesByLevel(f) = names(extra);
    fprintf('nfrac=%2d: coll_tot=%d coll_extra=%d NRMSE_accel=%.4f\n', f, sum(coll), sum(extra), nrmse);
  end

  % --- 4) tabella + TSV ---
  rows = sortrows(rows, 1);
  fid = fopen(fullfile(here,'qzi_cl_sweep.tsv'),'w');
  fprintf(fid,'nfrac\tcoll_total\tcoll_extra\tmin_gap_avoid\tbrake_margin_avoid\tmax_DRAC\tNRMSE_accel\n');
  for r = 1:size(rows,1)
    v = rows(r,:);
    fprintf(fid,'%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.6g\n', v(1),v(2),v(3),v(4),v(5),v(6),v(7));
  end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_cl_sweep.tsv'));
end
