function [P, lat] = tier_block_params(trajList, hold, nfrac)
%TIER_BLOCK_PARAMS  Oracolo T6: gira Donatello_Tier@BALANCED (nfrac Base 13) in Simulink su ogni traiettoria
%  di test_dataset.mat, campiona i 5 param [v0 T s0 a b] a fine control-step. Fedele al blocco PER COSTRUZIONE.
%  P{i} = N_i x 5 (double); lat = latenza misurata. hold >= latenza (~364 BAL splitpipe); default 500 (== TB).
%  nfrac = bit frazionari ingresso (default 20 = bit-exact; <20 = controllo negativo, HDL_PHASE §3.1.3).
  if nargin<2 || isempty(hold),  hold  = 500; end
  if nargin<3 || isempty(nfrac), nfrac = 20;  end
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  v1 = double(tr{trajList(1)}.val); v1 = v1(:,1);
  Plog = drive_tier(v1*ones(1,3), 700, 700, nfrac);           % ingresso costante -> 1 sola inferenza
  chg  = find(any(abs(diff(Plog,1,1))>0, 2));
  assert(~isempty(chg), 'il blocco non produce output (FSM ferma?)');
  assert(numel(chg)==1, 'ingresso costante -> %d inferenze: non e'' edge-triggered', numel(chg));
  lat = chg(1);
  assert(hold >= lat, 'hold=%d < latenza=%d', hold, lat);
  fprintf('tier_block_params: latenza BAL misurata = %d clock (edge-trigger OK)\n', lat);
  P = cell(numel(trajList),1);
  for i = 1:numel(trajList)
    val = double(tr{trajList(i)}.val); K = size(val,2);
    Pall = drive_tier(val, hold, K*hold+20, nfrac);
    idx  = hold*(0:K-1).' + lat + 1; idx = idx(idx <= size(Pall,1));
    assert(numel(idx)==K, 'traj %d: campionati %d/%d control-step', trajList(i), numel(idx), K);
    P{i} = Pall(idx,:);
  end
end

function P = drive_tier(seq, hold, stopT, nfrac)
% pilota Donatello_Tier@BALANCED@13 con la sequenza fisica seq (4 x K), ogni colonna tenuta `hold` clock.
  if nargin<3||isempty(stopT), stopT = hold; end
  here = fileparts(mfilename('fullpath'));
  K = size(seq,2);
  assignin('base','stimTS_tier', [(0:K-1).'*hold, seq.']);
  lib = 'snn_champions_lib'; if ~bdIsLoaded(lib), load_system(fullfile(here,[lib '.slx'])); end
  mdl = 'tier_oracle_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block([lib '/Donatello_Tier'], [mdl '/DUT']);
  set_param([mdl '/DUT'], 'TIER','BALANCED', 'NFRAC','13');    % esplicito: niente default impliciti
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName','stimTS_tier', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr', sprintf('fixdt(1,32,%d)', nfrac));
    add_line(mdl, ['dm/' num2str(j)], ['c' num2str(j) '/1']);
    add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('simulink/Signal Routing/Mux', [mdl '/mx'], 'Inputs','5');
  for j=1:5, add_line(mdl, ['DUT/' num2str(j)], ['mx/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Pw'], 'VariableName','Pw','SaveFormat','Array');
  add_line(mdl,'mx/1','Pw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so = sim(mdl); P = double(so.get('Pw')); close_system(mdl,0);
end
