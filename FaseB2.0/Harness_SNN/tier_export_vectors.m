function tier_export_vectors(trajList, tag, outdir)
%TIER_EXPORT_VECTORS  stim/gold .mem + meta per l'Harness_SNN, dal golden FEDELE AL BLOCCO (tier_block_params).
%  outdir = ROOT corta (D:/zbd_tier). stim = 4 val (fixdt(1,32,20), 8 hex); gold = 5 param Q7.13 (21b, 6 hex).
  here  = fileparts(mfilename('fullpath'));
  addpath(fullfile(here,'..','..','matlab'));   % tier_block_params, test_dataset
  addpath(fullfile(here,'..','common'));         % rtl_write_vectors
  ds = load(fullfile(here,'..','..','matlab','test_dataset.mat')); tr = ds.trajectories;
  Tp = numerictype(1,21,13); HOLD = 500;
  P = tier_golden_cache(trajList);                % golden dalla cache condivisa (stessi dati delle metriche)
  stimC = {}; goldC = {};
  for i = 1:numel(trajList)
    stimC{end+1} = fi(double(tr{trajList(i)}.val),1,32,20);  % 4 x Ni %#ok<AGROW>
    goldC{end+1} = fi(P{i}.', Tp);                            % 5 x Ni %#ok<AGROW>
  end
  stim = [stimC{:}]; gold = [goldC{:}];
  rtl_write_vectors(outdir, tag, stim, 32, gold, 21);
  K = size(stim,2);
  save(fullfile(outdir,['meta_' tag '.mat']), 'K', 'trajList');
  fprintf('tier_export_vectors: %d control-step su %d traiettorie -> %s\n', K, numel(trajList), outdir);
end
