function qz_tier_nfrac_gate()
%QZ_TIER_NFRAC_GATE  [Quantizzation_Study] Cancello del menu NFRAC (12 varianti tier x nfrac) su Donatello_Tier:
%  (1) REGRESSIONE: default (BALANCED, nfrac=13) BIT-EXACT al riferimento storico (run_block_traj_test asserta
%      dmax==0) -> a nfrac=13 la sostituzione 13->13 e' no-op;
%  (2) i 4 livelli (13/8/5/2) COMPILANO, params finiti, e la quantizzazione MORDE (8/5/2 differiscono da 13);
%  (3) HDL: makehdl del blocco a nfrac=8 genera VHDL valido (time-mux, DualPortRAM).
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot);
  build_tier_configurable();

  fprintf('\n--- (1) REGRESSIONE bit-exact @nfrac=13 (default BALANCED) ---\n');
  d13 = run_block_traj_test(20, 'Donatello_Tier', 500, 1, 20);   % assert dmax==0 interno
  fprintf('   dmax @nfrac=13 = %.4g\n', d13);

  fprintf('\n--- (2) i 4 livelli compilano + effetto quantizzazione (TIER=BALANCED) ---\n');
  ds = load(fullfile(mroot,'test_dataset.mat')); val = double(ds.trajectories{1}.val);
  P = containers.Map('KeyType','char','ValueType','any');
  for nf = {'13','8','5','2'}
    Pn = drive_tier('BALANCED', nf{1}, val(:,1:20), 500, 20*500+20);
    assert(all(isfinite(Pn(:))), 'params non finiti a nfrac=%s', nf{1});
    P(nf{1}) = Pn; fprintf('   nfrac=%-2s: compila, params finiti\n', nf{1});
  end
  for nf = {'8','5','2'}
    dd = max(max(abs(P(nf{1}) - P('13'))));
    fprintf('   max|Δparam| nfrac %s vs 13 = %.4g  -> %s\n', nf{1}, dd, string(dd>0));
    assert(dd > 0, 'nfrac=%s non ha effetto (== 13)', nf{1});
  end

  fprintf('\n--- (3) HDL @nfrac=8 (BALANCED) ---\n');
  v = makehdl_tier('8', 'BALANCED', 'D:/zbd_qz/tier_nfrac8');
  ok = ~isempty(v) && any(strcmp({v.name},'DualPortRAM_generic.vhd'));
  fprintf('   makehdl @nfrac=8: %d file VHDL, DualPortRAM=%d\n', numel(v), ok);
  assert(ok, 'VHDL @nfrac=8 non valido');
  fprintf('\n=== GATE MENU NFRAC: PASSATO (bit-exact@13, 4 livelli OK, effetto@8/5/2, HDL@8) ===\n');
end

function P = drive_tier(tier, nfracStr, seq, hold, stopT)
% pilota Donatello_Tier con TIER/NFRAC (popup) impostati via mask
  K = size(seq,2); ts = [(0:K-1).'*hold, seq.']; assignin('base','stimTS_tn', ts);
  mdl='tier_nfrac_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl); cu=onCleanup(@() close_system(mdl,0)); %#ok<NASGU>
  add_block('snn_champions_lib/Donatello_Tier', [mdl '/DUT']);
  set_param([mdl '/DUT'], 'TIER', tier, 'NFRAC', nfracStr);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName','stimTS_tn', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], 'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']); add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Signal Routing/Mux', [mdl '/mx'], 'Inputs','5');
  for j=1:5, add_line(mdl,['DUT/' num2str(j)],['mx/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Pw'], 'VariableName','Pw','SaveFormat','Array');
  add_line(mdl,'mx/1','Pw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so=sim(mdl); P=double(so.get('Pw'));
end

function v = makehdl_tier(nfracStr, tier, od)
  if exist(od,'dir'), rmdir(od,'s'); end
  mdl='tier_hdl_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl); cu=onCleanup(@() close_system(mdl,0)); %#ok<NASGU>
  sub=[mdl '/Donatello_Tier']; add_block('snn_champions_lib/Donatello_Tier', sub);
  set_param(sub, 'TIER', tier, 'NFRAC', nfracStr);
  for j=1:4
    add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)],'Value',num2str(j+0.5),...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl,['i' num2str(j) '/1'],['Donatello_Tier/' num2str(j)]);
  end
  for j=1:5, add_block('built-in/Outport',[mdl '/o' num2str(j)],'Port',num2str(j)); add_line(mdl,['Donatello_Tier/' num2str(j)],['o' num2str(j) '/1']); end
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');
  makehdl(sub,'TargetLanguage','VHDL','TargetDirectory',od,'GenerateHDLTestBench','off');
  v = dir(fullfile(od,'**','*.vhd'));
end
