function run_block_parity()
%RUN_BLOCK_PARITY  Parita' dei blocchi di snn_champions_lib vs golden (sequenza).
%  Ogni blocco e' guidato da un From Workspace con x_phys (N passi, dt=1); lo stato
%  del blocco (persistent in snn_core) persiste sulla sequenza. 'clear snn_core' tra
%  champion resetta lo stato di sessione. Confronto vs y_params (tol 1e-4).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  lib = 'snn_champions_lib';
  if ~bdIsLoaded(lib), load_system(fullfile(here, [lib '.slx'])); end
  tol = 1e-4; failed = false;

  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name)); N = size(c.x_phys, 1);
    clear snn_core                              % reset stato di sessione tra champion
    mdl = ['tb_' name]; if bdIsLoaded(mdl), close_system(mdl, 0); end
    new_system(mdl);
    add_block('simulink/Sources/From Workspace', [mdl '/FW'], ...
              'VariableName', 'fw_data', 'Interpolate', 'off', ...
              'OutputAfterFinalValue', 'Holding final value');
    add_block('simulink/Signal Routing/Demux', [mdl '/DM'], 'Outputs', '4');
    add_block([lib '/' name], [mdl '/DUT']);
    add_block('simulink/Signal Routing/Mux', [mdl '/MX'], 'Inputs', '5');
    add_block('simulink/Sinks/To Workspace', [mdl '/TW'], ...
              'VariableName', 'yo', 'SaveFormat', 'Array');
    add_line(mdl, 'FW/1', 'DM/1');
    for j = 1:4, add_line(mdl, ['DM/' num2str(j)], ['DUT/' num2str(j)]); end
    for j = 1:5, add_line(mdl, ['DUT/' num2str(j)], ['MX/' num2str(j)]); end
    add_line(mdl, 'MX/1', 'TW/1');
    set_param(mdl, 'SolverType', 'Fixed-step', 'FixedStep', '1', 'StopTime', num2str(N - 1));
    assignin('base', 'fw_data', [(0:N-1).', c.x_phys]);   % N x 5 (time + 4 feature)
    out = sim(mdl);
    y = squeeze(out.yo);                                  % rimuovi dim singleton (5x1xN -> 5xN)
    if size(y, 1) == 5 && size(y, 2) == N, y = y.'; end   % -> (N x 5)
    assert(isequal(size(y), [N, 5]), 'yo shape inatteso: [%s]', num2str(size(out.yo)));
    ey = max(abs(y(:) - c.y_params(:)));
    fprintf('%-13s  block|err|=%.2e [%s]\n', name, ey, tern(ey < tol));
    failed = failed || ey >= tol; close_system(mdl, 0);
  end
  close_system(lib, 0);
  if failed, error('run_block_parity:FAIL', 'Parita'' di blocco fallita'); end
  disp('ALL BLOCK PARITY PASS');
end

function s = tern(b)
  if b, s = 'PASS'; else, s = 'FAIL'; end
end
