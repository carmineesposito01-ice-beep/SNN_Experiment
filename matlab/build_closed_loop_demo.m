function build_closed_loop_demo(champion, k)
%BUILD_CLOSED_LOOP_DEMO  Modello closed-loop: champion guida il plant ACC_IIDM
%  (network-in-the-loop). Wiring CORRETTO di riferimento:
%    leader -> champion.v_l & plant.v_l
%    champion [v0,T,s0,a,b] -> plant [v0,T,s0,a,b]   (STESSO ORDINE)
%    plant.s -> UnitDelay -> champion.s
%    plant.v -> UnitDelay -> champion.v
%    (plant.v - v_l) -> UnitDelay -> champion.dv
%  I Unit Delay rompono l'algebraic loop; IC = stato osservato iniziale.
%  Uso: build_closed_loop_demo            % Donatello, traj 1
%       build_closed_loop_demo('Raffaello', 5)
  if nargin < 1, champion = 'Donatello'; end
  if nargin < 2, k = 1; end
  here = fileparts(mfilename('fullpath'));
  addpath(here);

  S = load(fullfile(here, 'test_dataset.mat')); Tr = S.trajectories;
  if iscell(Tr), Tr = [Tr{:}]; end
  c = Tr(k); val = c.val; N = size(val, 2);
  v_l = val(4, :).'; s0i = val(1, 1); v0i = val(2, 1); dv0i = val(3, 1);

  cl = 'snn_champions_lib'; pl = 'cf_plant_lib';
  if ~bdIsLoaded(cl), load_system(fullfile(here, [cl '.slx'])); end
  if ~bdIsLoaded(pl), load_system(fullfile(here, [pl '.slx'])); end
  mdl = 'closed_loop_demo'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl);

  add_block('simulink/Sources/From Workspace', [mdl '/LEADER'], 'VariableName', 'vl_data', ...
            'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
  add_block([cl '/' champion], [mdl '/CHAMP']);       % in: s,v,dv,v_l  out: v0,T,s0,a,b
  add_block([pl '/ACC_IIDM'],  [mdl '/PLANT']);        % in: v_l,v0,T,s0,a,b  out: s,v,accel
  add_block('simulink/Discrete/Unit Delay', [mdl '/Ds'],  'InitialCondition', num2str(s0i, 17));
  add_block('simulink/Discrete/Unit Delay', [mdl '/Dv'],  'InitialCondition', num2str(v0i, 17));
  add_block('simulink/Discrete/Unit Delay', [mdl '/Ddv'], 'InitialCondition', num2str(dv0i, 17));
  add_block('simulink/Math Operations/Subtract', [mdl '/SUBdv']);   % v - v_l
  add_block('simulink/Sinks/To Workspace', [mdl '/OUT_v'],  'VariableName', 'v_ego',  'SaveFormat', 'Array');
  add_block('simulink/Sinks/To Workspace', [mdl '/OUT_vl'], 'VariableName', 'v_lead', 'SaveFormat', 'Array');

  add_line(mdl, 'LEADER/1', 'CHAMP/4'); add_line(mdl, 'LEADER/1', 'PLANT/1');
  for j = 1:5, add_line(mdl, ['CHAMP/' num2str(j)], ['PLANT/' num2str(j+1)]); end   % v0..b -> plant 2..6
  add_line(mdl, 'PLANT/1', 'Ds/1');  add_line(mdl, 'Ds/1',  'CHAMP/1');             % s  feedback
  add_line(mdl, 'PLANT/2', 'Dv/1');  add_line(mdl, 'Dv/1',  'CHAMP/2');             % v  feedback
  add_line(mdl, 'PLANT/2', 'SUBdv/1'); add_line(mdl, 'LEADER/1', 'SUBdv/2');        % dv = v - v_l
  add_line(mdl, 'SUBdv/1', 'Ddv/1'); add_line(mdl, 'Ddv/1', 'CHAMP/3');
  add_line(mdl, 'PLANT/2', 'OUT_v/1'); add_line(mdl, 'LEADER/1', 'OUT_vl/1');

  set_param(mdl, 'SolverType', 'Fixed-step', 'FixedStep', '1', 'StopTime', num2str(N-1));
  assignin('base', 'vl_data', [(0:N-1).', v_l]);
  out = sim(mdl);
  ve = squeeze(out.v_ego); vl = squeeze(out.v_lead);
  fprintf('%s traj %d (%s): leader mean=%.2f | ego closed-loop start=%.2f min=%.2f max=%.2f end=%.2f\n', ...
          champion, k, char(string(c.scenario)), mean(vl), ve(1), min(ve), max(ve), ve(end));
  save_system(mdl, fullfile(here, [mdl '.slx']));
  fprintf('Saved %s.slx (apri e ispeziona il wiring)\n', mdl);
end
