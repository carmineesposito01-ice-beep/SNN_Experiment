function qz_cl_severity(levels)
%QZ_CL_SEVERITY  [Quantizzation_Study] Chiude il capitolo sicurezza: sulle traiettorie FISICAMENTE
%  INEVITABILI (l'oracolo collide), la rete quantizzata schianta PIU' FORTE al scendere dei bit?
%  Metrica: impact_dv = velocita' relativa al contatto [m/s] (piu' alto = crash piu' duro). Confronto vs
%  oracolo e su tutti gli nfrac. Se impact_dv(nfrac basso) ~ impact_dv(oracolo), la quantizzazione NON
%  aggiunge severita' nemmeno dove la collisione e' comunque inevitabile.
  if nargin < 1 || isempty(levels), levels = [13 12 11 10 9 8 7 6 5 4 3 2]; end
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories; nt = numel(tr);
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));

  % --- inevitabili + severita' oracolo ---
  inev = []; oimp = [];
  for i = 1:nt
    o = qz_cl_sim(tr{i}, oracle(tr{i}.gt_params));
    if o.collided, inev(end+1)=i; oimp(end+1)=o.impact_dv; end %#ok<AGROW>
  end
  fprintf('inevitabili (oracolo collide): %d\n', numel(inev));
  for j = 1:numel(inev)
    t = tr{inev(j)};
    fprintf('  #%2d %-18s %-8s  gt=[v0=%.1f T=%.2f s0=%.2f a=%.2f b=%.2f]  impact_oracolo=%.2f m/s\n', ...
      inev(j), t.name, t.regime, t.gt_params(1),t.gt_params(2),t.gt_params(3),t.gt_params(4),t.gt_params(5), oimp(j));
  end

  % --- impact_dv rete per (inevitabile, nfrac) ---
  IMP = zeros(numel(inev), numel(levels));
  for li = 1:numel(levels)
    f = levels(li); fun = str2func(sprintf('qz_snn_cl_step_n%d_mex', f));
    for j = 1:numel(inev)
      o = qz_cl_sim(tr{inev(j)}, @(x,rst) fun(x,W,rst,f));
      IMP(j,li) = o.impact_dv;
    end
  end

  fprintf('\nimpact_dv [m/s] al contatto (piu'' alto = crash piu'' duro):\n');
  fprintf('%-14s draw | oracolo |', 'scenario'); for f=levels, fprintf(' n%-2d', f); end; fprintf('\n');
  for j = 1:numel(inev)
    t = tr{inev(j)};
    fprintf('%-14s %-7s | %6.2f  |', t.name, t.regime, oimp(j));
    for li=1:numel(levels), fprintf(' %5.2f', IMP(j,li)); end; fprintf('\n');
  end
  fprintf('\nmax impact_dv sugli inevitabili — oracolo=%.2f m/s\n', max(oimp));
  fprintf('nfrac | max_impact | delta_vs_oracolo\n');
  fid = fopen(fullfile(here,'sev_sweep.tsv'),'w'); fprintf(fid,'nfrac\tmax_impact_dv\toracle_max\n');
  for li = 1:numel(levels)
    mx = max(IMP(:,li));
    fprintf('%5d | %10.2f | %+.2f\n', levels(li), mx, mx - max(oimp));
    fprintf(fid,'%d\t%.4f\t%.4f\n', levels(li), mx, max(oimp));
  end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'sev_sweep.tsv'));
end
