function build_lib_dataset_test()
%BUILD_LIB_DATASET_TEST  Costruisce snn_lib_dataset_test.slx: un banco che testa TUTTI gli 8 blocchi
%  della libreria milestone col dataset, ognuno al SUO rate corretto.
%
%  Due sorgenti dallo STESSO dataset (le riempie il runner run_lib_dataset_test.m):
%    srcFast (1 step/campione)  -> i 4 Campioni double (Donatello/Leonardo/Michelangelo/Raffaello):
%                                  stato ALIF per-campione, come demo_test. Uscita = 5 params.
%    srcHold (campione tenuto H) -> i blocchi HDL time-mux, via Data Type Conversion a fixdt(1,32,20):
%                                  Donatello_LUT (estimatore, NLUT=64), Donatello_Tier (estimatore,
%                                  BALANCED/nfrac13), Donatello_ACC_IIDM_M (controllore completo).
%  ACC-IIDM (controllore standalone, 9 ingressi): 4 ingressi fisici + 5 params, TUTTI dalla stessa
%  sorgente held e SINCRONI (cambiano insieme a inizio hold) -> 1 inferenza/control-step, l'OU aggiorna
%  una volta. I params li fornisce il runner in fw_params (= decode64, cio' che Tier/LUT producono).
%  [Comporre Tier->ACC dal vivo darebbe un DOPPIO edge (i params di Tier arrivano ~405 clock dopo i
%   fisici) -> l'OU aggiornerebbe due volte: serve un handshake "params pronti" non presente nei blocchi.
%   Per testare il blocco si sincronizzano gli ingressi = l'uso previsto della sua interfaccia a 9  port.]
%
%  Ogni uscita va in un To Workspace (P_<nome> per i params, A_M/A_S per le accelerazioni). Il runner
%  imposta le sorgenti, simula e confronta col riferimento (ref_params / MEX+decode / acc_iidm_open).
%  Rigenerazione: build_lib_dataset_test.m.
  here=fileparts(mfilename('fullpath')); cd(here);
  lib='snn_champions_lib'; if ~bdIsLoaded(lib), load_system(fullfile(here,[lib '.slx'])); end
  mdl='snn_lib_dataset_test'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl);

  % ---- sorgente FAST (1 step/campione): i 4 Campioni double ----
  add_block('simulink/Sources/From Workspace',[mdl '/srcFast'], 'VariableName','fw_fast', ...
            'Interpolate','off','OutputAfterFinalValue','Holding final value','SampleTime','1');
  add_block('simulink/Signal Routing/Demux',[mdl '/dmF'],'Outputs','4'); add_line(mdl,'srcFast/1','dmF/1');
  champs={'Donatello','Leonardo','Michelangelo','Raffaello'};
  for ci=1:numel(champs)
    nm=champs{ci}; add_block([lib '/' nm],[mdl '/' nm]);
    for j=1:4, add_line(mdl,['dmF/' num2str(j)],[nm '/' num2str(j)]); end
    add_block('simulink/Signal Routing/Mux',[mdl '/mx_' nm],'Inputs','5');
    for j=1:5, add_line(mdl,[nm '/' num2str(j)],['mx_' nm '/' num2str(j)]); end
    add_block('simulink/Sinks/To Workspace',[mdl '/P_' nm],'VariableName',['P_' nm],'SaveFormat','Array');
    add_line(mdl,['mx_' nm '/1'],['P_' nm '/1']);
  end

  % ---- sorgente HOLD (campione tenuto H clock): i blocchi HDL time-mux ----
  add_block('simulink/Sources/From Workspace',[mdl '/srcHold'], 'VariableName','fw_hold', ...
            'Interpolate','off','OutputAfterFinalValue','Holding final value','SampleTime','1');
  add_block('simulink/Signal Routing/Demux',[mdl '/dmH'],'Outputs','4'); add_line(mdl,'srcHold/1','dmH/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/dtc' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');   % >=20 bit frazionari = bit-exact
    add_line(mdl,['dmH/' num2str(j)],['dtc' num2str(j) '/1']);
  end
  % estimatori HDL (4 in -> 5 out): LUT combinato e Tier configurabile
  for blk={'Donatello_LUT','Donatello_Tier'}
    nm=blk{1}; add_block([lib '/' nm],[mdl '/' nm]);
    for j=1:4, add_line(mdl,['dtc' num2str(j) '/1'],[nm '/' num2str(j)]); end
    add_block('simulink/Signal Routing/Mux',[mdl '/mx_' nm],'Inputs','5');
    for j=1:5, add_line(mdl,[nm '/' num2str(j)],['mx_' nm '/' num2str(j)]); end
    add_block('simulink/Sinks/To Workspace',[mdl '/P_' nm],'VariableName',['P_' nm],'SaveFormat','Array');
    add_line(mdl,['mx_' nm '/1'],['P_' nm '/1']);
  end
  % controllore completo bundled (4 in -> accel)
  add_block([lib '/Donatello_ACC_IIDM_M'],[mdl '/Donatello_ACC_IIDM_M']);
  for j=1:4, add_line(mdl,['dtc' num2str(j) '/1'],['Donatello_ACC_IIDM_M/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace',[mdl '/A_M'],'VariableName','A_M','SaveFormat','Array');
  add_line(mdl,'Donatello_ACC_IIDM_M/1','A_M/1');
  % controllore standalone (9 in): 4 fisici (dtc) + 5 params (dtcp), tutti held e SINCRONI.
  add_block('simulink/Sources/From Workspace',[mdl '/srcParams'], 'VariableName','fw_params', ...
            'Interpolate','off','OutputAfterFinalValue','Holding final value','SampleTime','1');
  add_block('simulink/Signal Routing/Demux',[mdl '/dmP'],'Outputs','5'); add_line(mdl,'srcParams/1','dmP/1');
  for j=1:5
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/dtcp' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dmP/' num2str(j)],['dtcp' num2str(j) '/1']);
  end
  add_block([lib '/ACC-IIDM'],[mdl '/ACC_IIDM']);
  for j=1:4, add_line(mdl,['dtc' num2str(j) '/1'],['ACC_IIDM/' num2str(j)]); end
  for j=1:5, add_line(mdl,['dtcp' num2str(j) '/1'],['ACC_IIDM/' num2str(j+4)]); end
  add_block('simulink/Sinks/To Workspace',[mdl '/A_S'],'VariableName','A_S','SaveFormat','Array');
  add_line(mdl,'ACC_IIDM/1','A_S/1');

  % config default dei blocchi configurabili
  set_param([mdl '/Donatello_LUT'],'NLUT','64');
  set_param([mdl '/Donatello_Tier'],'TIER','BALANCED','NFRAC','13');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','SaveOutput','off');

  try, Simulink.BlockDiagram.arrangeSystem(mdl); catch, end
  save_system(mdl, fullfile(here,[mdl '.slx']));
  close_system(mdl,0);
  fprintf('OK: snn_lib_dataset_test.slx costruito (8 blocchi; srcFast Campioni, srcHold+srcParams HDL)\n');
end
