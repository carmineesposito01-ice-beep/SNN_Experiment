function run_plant_parity()
%RUN_PLANT_PARITY  Parita' del blocco Simulink ACC_IIDM vs il plant Python (plant_golden.mat).
%  Per ogni caso: leader v_l streammato + params costanti -> blocco -> confronta s,v col golden.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'plant_golden.mat')); cases = d.cases;
  if iscell(cases), cases = [cases{:}]; end
  lib = 'cf_plant_lib';
  if ~bdIsLoaded(lib), load_system(fullfile(here, [lib '.slx'])); end
  tol = 1e-4; failed = false;

  for i = 1:numel(cases)
    c = cases(i); name = char(string(c.name)); N = numel(c.v_l); p = c.params(:).';
    clear PLANT
    mdl = ['pt_' name]; if bdIsLoaded(mdl), close_system(mdl, 0); end
    new_system(mdl);
    add_block('simulink/Sources/From Workspace', [mdl '/FW'], 'VariableName', 'vl_data', ...
              'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
    for j = 1:5, add_block('simulink/Sources/Constant', [mdl '/P' num2str(j)], 'Value', num2str(p(j), 17)); end
    add_block([lib '/ACC_IIDM'], [mdl '/DUT']);
    add_block('simulink/Signal Routing/Mux', [mdl '/MX'], 'Inputs', '3');
    add_block('simulink/Sinks/To Workspace', [mdl '/TW'], 'VariableName', 'yo', 'SaveFormat', 'Array');
    add_line(mdl, 'FW/1', 'DUT/1');                                  % v_l -> ingresso 1
    for j = 1:5, add_line(mdl, ['P' num2str(j) '/1'], ['DUT/' num2str(j+1)]); end  % v0,T,s0,a,b -> 2..6
    for j = 1:3, add_line(mdl, ['DUT/' num2str(j)], ['MX/' num2str(j)]); end
    add_line(mdl, 'MX/1', 'TW/1');
    set_param(mdl, 'SolverType', 'Fixed-step', 'FixedStep', '1', 'StopTime', num2str(N - 1));
    assignin('base', 'vl_data', [(0:N-1).', c.v_l(:)]);
    out = sim(mdl);
    y = squeeze(out.yo); if size(y, 1) == 3 && size(y, 2) == N, y = y.'; end   % (N x 3): s, v, accel
    es = max(abs(y(:, 1) - c.ref_s(:)));
    ev = max(abs(y(:, 2) - c.ref_v(:)));
    okc = es < tol && ev < tol;
    fprintf('%-14s  s|err|=%.2e  v|err|=%.2e  [%s]\n', name, es, ev, tern(okc));
    failed = failed || ~okc; close_system(mdl, 0);
  end
  close_system(lib, 0);
  if failed, error('run_plant_parity:FAIL', 'Parita'' plant fallita'); end
  disp('ALL PLANT PARITY PASS');
end

function s = tern(b)
  if b, s = 'PASS'; else, s = 'FAIL'; end
end
