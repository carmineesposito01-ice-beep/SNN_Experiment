function probe_golden_cost()
%PROBE_GOLDEN_COST  Misura il tempo del golden-da-blocco su 1 traiettoria (1000 step) -> stima i 60.
%  Decide se il full-60 e' fattibile col golden-da-blocco (background) o serve l'estrazione-MEX.
  addpath(fullfile(fileparts(mfilename('fullpath')),'..','..','matlab'));
  t0 = tic; tier_block_params(1, 500); dt = toc(t0);
  fprintf('golden 1 traj (1000 control-step): %.1f s -> stima 60 traj = %.1f min\n', dt, dt*60/60);
  fprintf('DECISIONE: stima <= ~30 min -> full-60 background; altrimenti estrazione-MEX.\n');
end
