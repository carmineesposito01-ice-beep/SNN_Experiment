function demo_test(champion, k)
%DEMO_TEST  Test turnkey di un blocco champion su test_trajectories.mat.
%  Alimenta UNA traiettoria (scalari [s,v,dv,v_l] che scorrono nel tempo, dt=0.1,
%  stato del blocco persistente) e confronta l'uscita del blocco con il riferimento
%  Python (ref_params) e la ground-truth (gt_params).
%
%  Uso:  demo_test                 % default: Donatello, traiettoria 1
%        demo_test('Raffaello', 3)
%
%  NB: fa addpath della cartella matlab/ -> risolve snn_*.m e <champion>_weights.m.
  if nargin < 1, champion = 'Donatello'; end
  if nargin < 2, k = 1; end
  here = fileparts(mfilename('fullpath'));
  addpath(here);                                   % risolve le funzioni helper dei blocchi

  S = load(fullfile(here, 'test_trajectories.mat')); T = S.trajectories;
  if iscell(T), T = [T{:}]; end
  c = T(k);
  val = c.val;                                     % (4 x N): righe [s;v;dv;v_l]
  N = size(val, 2);

  lib = 'snn_champions_lib';
  if ~bdIsLoaded(lib), load_system(fullfile(here, [lib '.slx'])); end
  mdl = 'demo_tb'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  clear snn_core                                   % reset stato di sessione

  new_system(mdl);
  add_block('simulink/Sources/From Workspace', [mdl '/FW'], 'VariableName', 'fw_data', ...
            'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/DM'], 'Outputs', '4');
  add_block([lib '/' champion], [mdl '/DUT']);
  add_block('simulink/Signal Routing/Mux', [mdl '/MX'], 'Inputs', '5');
  add_block('simulink/Sinks/To Workspace', [mdl '/TW'], 'VariableName', 'yo', 'SaveFormat', 'Array');
  add_line(mdl, 'FW/1', 'DM/1');
  for j = 1:4, add_line(mdl, ['DM/' num2str(j)], ['DUT/' num2str(j)]); end
  for j = 1:5, add_line(mdl, ['DUT/' num2str(j)], ['MX/' num2str(j)]); end
  add_line(mdl, 'MX/1', 'TW/1');
  set_param(mdl, 'SolverType', 'Fixed-step', 'FixedStep', '1', 'StopTime', num2str(N - 1));

  % From Workspace: colonna tempo + i 4 canali fisici (uno scalare per step)
  assignin('base', 'fw_data', [(0:N-1).', val.']);   % (N x 5)
  out = sim(mdl);
  y = squeeze(out.yo); if size(y, 1) == 5 && size(y, 2) == N, y = y.'; end   % (N x 5)
  blk = mean(y(floor(N/2):end, :), 1);               % media a regime (2a meta')
  close_system(mdl, 0);

  ci = find(strcmp(cellstr(c.champion_order), champion), 1);
  ref = c.ref_params(ci, :); gt = c.gt_params(:).';
  pn = {'v0', 'T', 's0', 'a', 'b'};
  fprintf('\nTraiettoria %d (%s) - blocco %s\n', k, char(string(c.scenario)), champion);
  fprintf('%-5s %10s %10s %10s\n', 'param', 'blocco', 'ref(py)', 'gt');
  for i = 1:5, fprintf('%-5s %10.3f %10.3f %10.3f\n', pn{i}, blk(i), ref(i), gt(i)); end
  fprintf('max|blocco - ref| = %.2e  (~0 => il blocco riproduce il modello validato)\n', ...
          max(abs(blk - ref)));
end
