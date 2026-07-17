function M = rtl_metrics(trajList)
%RTL_METRICS  [Fase B2.0-2a] Accuratezza di stima dei 5 param IDM del blocco Donatello_Champion vs i
%  gt_params del dataset. Poiche' A-1 prova RTL==blocco bit-exact, queste sono le metriche della versione
%  FPGA (blocco fisico), calcolate sul golden FEDELE (snn_traj_champion). Riporta max/p99/mean per param
%  (coda/picco, non solo media -- nella stima conta la coda). Veloce: solo MEX, niente xsim.
  if nargin < 1 || isempty(trajList), trajList = [1 7 23]; end
  here = fileparts(mfilename('fullpath'));
  build_champion_golden();
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  names = {'v0','T','s0','a','b'}; err = [];
  for t = trajList(:).'
    clear snn_traj_champion_mex;
    P  = snn_traj_champion_mex(tr{t}.val, 500);        % params del blocco per control-step (N x 5)
    gt = double(tr{t}.gt_params(:)).';                 % 5 param veri (osservato), costanti sulla traj
    err = [err; abs(P - gt)]; %#ok<AGROW>
  end
  M = struct();
  fprintf('Accuratezza stima param (blocco == RTL, %d control-step su %d traj):\n', size(err,1), numel(trajList));
  for i = 1:5
    M.(names{i}) = struct('max', max(err(:,i)), 'p99', prctile(err(:,i),99), 'mean', mean(err(:,i)));
    fprintf('  %-3s  max=%.4g  p99=%.4g  mean=%.4g\n', names{i}, M.(names{i}).max, M.(names{i}).p99, M.(names{i}).mean);
  end
  fprintf(['NB: l''errore su param vs gt_params (spec. v0) riflette l''IDENTIFICABILITA'' -- v0 e''\n' ...
           '    osservabile solo a flusso libero; in car-following vincolato la rete non la recupera\n' ...
           '    (tetto diagnosticato nel Dynamic_Study). NON e'' un problema RTL. La qualita'' SNN\n' ...
           '    significativa e'' il comportamento CLOSED-LOOP (Harness B), non il recupero dei param.\n']);
end
