function test_t7_step_block()
%TEST_T7_STEP_BLOCK  Il golden passo-passo e' BIT-IDENTICO al blocco composto Donatello_SNN_IIDM.
%  E' il cancello di fedelta' del riferimento: se cade questo, ogni confronto RTL a valle misura
%  la cosa sbagliata. Riproduce la Fase 0 di T5 (drift_chosen.m) col percorso passo-passo di T7a.
%
%  ⚠️ Il blocco NON si pilota con ingressi costanti (probe P1): `align` rilascerebbe valori identici
%     a quelli tenuti, le sue uscite non cambierebbero e l'ACC non vedrebbe alcun fronte. Qui si usano
%     control-step reali e distinti del dataset.
  root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
  ml   = fullfile(root,'matlab');
  addpath(ml, fullfile(ml,'Quantizzation_Study'), fileparts(mfilename('fullpath')));
  cd(ml);
  if ~bdIsLoaded('snn_champions_lib'), load_system(fullfile(ml,'snn_champions_lib.slx')); end
  build_acciidm_m_golden();

  ds = load(fullfile(ml,'test_dataset.mat')); tr = ds.trajectories;
  K = 6;
  raw  = double(tr{1}.val(:,1:K));
  fmF  = fimath('RoundingMethod','Floor','OverflowAction','Saturate');
  valF = double(fi(raw, 1, 32, 20, fmF));               % convenzione FLOOR (spec §4, probe P4b)

  % --- percorso GOLDEN: un control-step per chiamata ---
  f = t7_step_block();
  A = zeros(K,1);
  for k = 1:K, [~, A(k)] = f(valF(:,k), k == 1); end

  % --- percorso BLOCCO: streaming in Simulink, campionato a fine control-step ---
  hb = 1300;                                            % > latenza del composto (554, probe P1)
  assignin('base','stim_si', [(0:K-1).'*hb, valF.']);
  mdl = 'tst_snn_iidm'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_SNN_IIDM',[mdl '/DUT']);
  add_block('simulink/Sources/From Workspace',[mdl '/src'],'VariableName','stim_si', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux',[mdl '/dm'],'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/c' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']);
    add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace',[mdl '/Aw'],'VariableName','Aw','SaveFormat','Array');
  add_line(mdl,'DUT/1','Aw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1', ...
            'StopTime',num2str(K*hb+40),'SaveOutput','off');
  so = sim(mdl); Ablk = double(so.get('Aw')); close_system(mdl,0);
  Achk = Ablk(hb*(1:K).' - 20);

  d = max(abs(Achk(:) - A(:)));
  fprintf('golden : %s\n', mat2str(A(:).', 9));
  fprintf('blocco : %s\n', mat2str(Achk(:).', 9));
  fprintf('test_t7_step_block: dmax = %.17g\n', d);
  assert(d == 0, 'golden passo-passo NON bit-identico al blocco (dmax=%g)', d);
  fprintf('test_t7_step_block: PASSATO\n');
end
