function qz_mp_advanced_gate()
%QZ_MP_ADVANCED_GATE  Gate della Modalita' Avanzata del blocco Donatello_Tier (Approccio A).
%  1) Base ADV-off: nessuna regressione (run_block_traj_test, dmax=0).
%  2) Struttura: 15 varianti (12 Base + 3 ADV) + mask ADV/6-slider + chart ADV cotta coi tipi per-campo.
%  3) ADV-on @[13x6] == Base NFRAC=13 (ADV corretto a piena precisione, confronto output-vs-output del blocco).
%  4) ADV DISCRIMINA: rifatto a [13 13 2 13 13 13] (acc=2) l'output CAMBIA vs full -> i tipi per-campo atterrano.
%  5) HDL gen da ADV: makehdl con ADV on -> Donatello.vhd + DualPortRAM (architettura time-mux).
%  Ripristina il default [13x6] alla fine (il .slx committato ha l'ADV a piena precisione).
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  lib = 'snn_champions_lib'; sub = [lib '/Donatello_Tier']; vs = [sub '/VS'];
  libf = fullfile(mroot, [lib '.slx']);

  % ---- GATE 1: Base ADV-off, nessuna regressione ----
  build_tier_configurable();                                  % default nf=[13x6]
  d1 = run_block_traj_test(20, 'Donatello_Tier', 500, 1, 20); % attivo = BALANCED_n13 (full precision)
  assert(d1 == 0, 'REGRESSIONE Base ADV-off: dmax=%.4g', d1);
  fprintf('GATE1 Base ADV-off: dmax=0 (nessuna regressione)\n');

  % ---- GATE 2: struttura ADV ----
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libf);
  for t = {'SLOW','BALANCED','FAST'}   % 3 ADV + campioni Base (n13/n2) per tier, per-nome (robusto)
    assert(getSimulinkBlockHandle([vs '/' t{1} '_ADV'])>0, 'manca variante ADV %s', t{1});
    assert(getSimulinkBlockHandle([vs '/' t{1} '_n13'])>0, 'manca variante Base %s_n13', t{1});
    assert(getSimulinkBlockHandle([vs '/' t{1} '_n2'])>0, 'manca variante Base %s_n2', t{1});
  end
  mo = Simulink.Mask.get(sub);
  for p = {'ADV','nV','nfat','nacc','naccw','nraw','nw'}
    assert(~isempty(mo.getParameter(p{1})), 'manca il param mask %s', p{1});
  end
  chAdv = sfroot().find('-isa','Stateflow.EMChart','Path',[vs '/BALANCED_ADV/SNN']);
  assert(~isempty(chAdv) && contains(chAdv.Script, 'qz_snn_types_mp('), 'chart ADV non cotta coi tipi per-campo');
  assert(contains(chAdv.Script, '[13 13 13 13 13 13]'), 'chart ADV: config attesa [13x6] non trovata');
  close_system(lib,0);
  fprintf('GATE2 struttura: 15 varianti + mask ADV/6-slider + chart ADV cotta per-campo\n');

  % ---- GATE 3: ADV-on @[13x6] == Base NFRAC=13 ----
  ds = load(fullfile(mroot,'test_dataset.mat')); val = double(ds.trajectories{1}.val);
  seq = val(:, 1:10); ST = 10*500 + 20;                       % 10 control-step tenuti 500 clock ciascuno
  P_base = drive_cfg(seq, 500, ST, 'BALANCED', '13', 'off');
  P_full = drive_cfg(seq, 500, ST, 'BALANCED', '13', 'on');
  d3 = max(max(abs(P_full - P_base)));
  assert(d3 == 0, 'ADV-on @[13x6] != Base NFRAC=13 (dmax=%.4g)', d3);
  fprintf('GATE3 ADV-on @full-precision == Base NFRAC=13: dmax=0\n');

  % ---- GATE 4: ADV discrimina (acc=2 cambia l'output) ----
  build_tier_configurable([13 13 2 13 13 13]);               % ADV cotta con acc=2
  P_adv2 = drive_cfg(seq, 500, ST, 'BALANCED', '13', 'on');
  d4 = max(max(abs(P_adv2 - P_base)));
  assert(d4 > 0, 'ADV [13 13 2 ..] NON discrimina dal full (dmax=%.4g): tipi per-campo non applicati', d4);
  fprintf('GATE4 ADV discrimina: acc=2 cambia l''output (dmax vs full = %.4g > 0)\n', d4);

  % ---- GATE 5: HDL gen da ADV ----
  outdir = 'D:/zbd_qz/adv_hdl'; if exist(outdir,'dir'), rmdir(outdir,'s'); end
  vhddir = gen_hdl_cfg('BALANCED', 'on', outdir);
  assert(~isempty(dir(fullfile(vhddir,'BALANCED_ADV.vhd'))), 'ADV: variante BALANCED_ADV non generata');
  assert(~isempty(dir(fullfile(vhddir,'DualPortRAM_generic.vhd'))), 'ADV: manca DualPortRAM (non time-mux)');
  fprintf('GATE5 HDL da ADV: BALANCED_ADV.vhd + SNN + DualPortRAM generati (time-mux)\n');

  % ---- ripristino default ----
  build_tier_configurable();
  fprintf('=== GATE ADV PASSATO — default [13x6] ripristinato ===\n');
end

function P = drive_cfg(seq, hold, stopT, tier, nfracPopup, advOnOff)
% pilota Donatello_Tier con la config mask data; ritorna il log params grezzo (per confronto output-vs-output)
  K = size(seq, 2); ts = [(0:K-1).' * hold, seq(:,1:K).'];
  assignin('base', 'stimTS_adv', ts);
  mdl = 'adv_drv_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_Tier', [mdl '/DUT']);
  set_param([mdl '/DUT'], 'TIER', tier, 'NFRAC', nfracPopup, 'ADV', advOnOff);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName','stimTS_adv', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], 'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl, ['dm/' num2str(j)], ['c' num2str(j) '/1']); add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('simulink/Signal Routing/Mux', [mdl '/mx'], 'Inputs','5');
  for j=1:5, add_line(mdl, ['DUT/' num2str(j)], ['mx/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Pw'], 'VariableName','Pw','SaveFormat','Array');
  add_line(mdl, 'mx/1', 'Pw/1');
  set_param(mdl, 'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so = sim(mdl); P = double(so.get('Pw')); close_system(mdl,0);
end

function vhddir = gen_hdl_cfg(tier, advOnOff, outdir)
% makehdl del blocco (istanza linkata) con la config mask data -> genera la variante attiva
  mdl = 'adv_hdl_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl); cu = onCleanup(@() close_system(mdl,0)); %#ok<NASGU>
  add_block('snn_champions_lib/Donatello_Tier', [mdl '/DUT']);
  set_param([mdl '/DUT'], 'TIER', tier, 'ADV', advOnOff);
  ivals = {'10','6','2','4'};
  for j=1:4
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], 'Value', ivals{j}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  for j=1:5, add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j)); add_line(mdl, ['DUT/' num2str(j)], ['o' num2str(j) '/1']); end
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');
  makehdl([mdl '/DUT'], 'TargetLanguage','VHDL','TargetDirectory',outdir,'GenerateHDLTestBench','off');
  s = dir(fullfile(outdir,'**','SNN.vhd')); assert(~isempty(s), 'nessun VHDL (SNN.vhd)'); vhddir = s(1).folder;
end
