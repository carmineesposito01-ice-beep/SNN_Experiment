function qzi_cl_severity(levels)
%QZI_CL_SEVERITY  [Quantizzation_Study_IIDM] Severita' specchiata: sugli inevitabili (l'oracolo collide),
%  l'IIDM quantizzato schianta piu' forte al scendere dei bit? Metrica impact_dv [m/s]. SNN congelata @13.
  if nargin < 1 || isempty(levels), levels = [13 8 5 2]; end
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  qzdir = fullfile(mroot,'Quantizzation_Study'); addpath(mroot); addpath(here); addpath(qzdir);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(qzdir,'test_dataset_exhaustive.mat')); tr = ds.trajectories; nt = numel(tr);
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));
  inev = []; oimp = [];
  for i = 1:nt
    o = qz_cl_sim(tr{i}, oracle(tr{i}.gt_params));
    if o.collided, inev(end+1)=i; oimp(end+1)=o.impact_dv; end %#ok<AGROW>
  end
  fprintf('inevitabili (oracolo collide): %d\n', numel(inev));

  IMP = zeros(numel(inev), numel(levels));
  for li = 1:numel(levels)
    f = levels(li); fun = str2func(sprintf('qzi_cl_step_n%d_mex', f));   % MEX gia' costruiti dal Task 1
    for j = 1:numel(inev)
      o = qz_cl_sim(tr{inev(j)}, @(x,rst) fun(x,W,rst,f));
      IMP(j,li) = o.impact_dv;
    end
  end
  fid = fopen(fullfile(here,'qzi_sev_sweep.tsv'),'w'); fprintf(fid,'nfrac\tmax_impact_dv\toracle_max\n');
  for li = 1:numel(levels)
    mx = max([IMP(:,li); 0]);
    fprintf('nfrac=%2d max_impact=%.2f (oracolo=%.2f)\n', levels(li), mx, max([oimp 0]));
    fprintf(fid,'%d\t%.4f\t%.4f\n', levels(li), mx, max([oimp 0]));
  end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_sev_sweep.tsv'));
end
