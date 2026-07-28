function M = tier_rtl_metrics(trajList)
%TIER_RTL_METRICS  Accuratezza stima 5 param (blocco Tier@BAL vs gt_params). Poiche' T6-EXACT prova RTL==blocco,
%  sono le metriche della versione FPGA. max/p99 (coda). NOTA: v0 = identificabilita (flusso libero), non RTL.
  if nargin<1||isempty(trajList), trajList = 1:60; end
  here = fileparts(mfilename('fullpath')); mroot = fullfile(here,'..','..','matlab'); addpath(mroot);
  ds = load(fullfile(mroot,'test_dataset.mat')); tr = ds.trajectories;
  P = tier_block_params(trajList, 500);
  names = {'v0','T','s0','a','b'}; err = [];
  for i = 1:numel(trajList)
    gt = double(tr{trajList(i)}.gt_params(:)).';
    err = [err; abs(P{i} - gt)]; %#ok<AGROW>
  end
  M = struct();
  fprintf('Accuratezza stima param (versione FPGA == blocco, %d control-step):\n', size(err,1));
  for i=1:5
    M.(names{i}) = struct('max',max(err(:,i)),'p99',prctile(err(:,i),99));
    fprintf('  %-3s  max=%.4g  p99=%.4g\n', names{i}, M.(names{i}).max, M.(names{i}).p99);
  end
  fprintf('NOTA: v0 alto = identificabilita (v0 osservabile a flusso libero), non difetto RTL.\n');
end
