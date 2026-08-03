function ok = run_acc_iidm_gate()
%RUN_ACC_IIDM_GATE  Cancello HDL self-contained per il blocco standalone R17 ACC-IIDM (9 in -> accel).
%  Come run_block_hdl_gate (copia solo il .slx, toglie matlab/ dal path, istanzia, makehdl) ma: 9 ingressi,
%  niente NFRAC (precisione fissa R17/nfrac=8), niente assert DualPortRAM (l'IIDM non ha la RAM della SNN).
%  Isolamento: acc_iidm_open/acc_types E le funzioni-fase IIDM NON devono essere sul path -> la chart le
%  inlina tutte (self-contained provato, come i blocchi Donatello_*).
  here = fileparts(mfilename('fullpath')); lib = 'snn_champions_lib';
  work = fullfile(tempdir, 'acc_iidm_hdl_gate');
  bdclose('all');
  if exist(work,'dir'), rmdir(work,'s'); end; mkdir(work);
  copyfile(fullfile(here,[lib '.slx']), work);        % <-- SOLO il .slx

  oldPath = path; oldDir = pwd; restore = onCleanup(@() cleanupGate(oldPath,oldDir)); %#ok<NASGU>
  warning('off','MATLAB:rmpath:DirNotFound'); rmpath(here); cd(work);
  for f = {'acc_iidm_open','acc_types','iidm_prep','iidm_nd','iidm_use_b','iidm_final_c', ...
           'div_seq_step','sqrt_seq_step','iidm_ab','iidm_tanh'}
    assert(isempty(which(f{1})), 'gate non valido: %s ancora sul path (la chart deve inlinarlo)', f{1});
  end
  fprintf('isolamento OK: acc_iidm_open/acc_types + funzioni-fase IIDM non raggiungibili sul path\n');

  ok = false;
  load_system(fullfile(work,[lib '.slx']));
  blk = [lib '/ACC-IIDM'];
  mdl = 'gate_acc_iidm'; new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT']; add_block(blk, sub);
  % s,v,dv,v_l, v0,T,s0,a,b  (fisici; fixed >=20 bit frazionari - double non e' HDL)
  vals = {'10','6','2','4','25','1.5','2','1.5','2'};
  for j = 1:9
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], 'Value', vals{j}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('built-in/Outport', [mdl '/accel'], 'Port','1');
  add_line(mdl, 'DUT/1', 'accel/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  save_system(mdl, fullfile(work,[mdl '.slx']));
  set_param(mdl,'SimulationCommand','update');        % compila: rivela errori nella chart

  outdir = fullfile(work,'hdlsrc');
  makehdl(sub,'TargetLanguage','VHDL','TargetDirectory',outdir,'GenerateHDLTestBench','off');
  v = dir(fullfile(outdir,'**','*.vhd')); ok = ~isempty(v);
  fprintf('\nACC-IIDM (R17): VHDL generati: %d\n', numel(v));
  for i = 1:numel(v), fprintf('   %-32s %8d byte\n', v(i).name, v(i).bytes); end
  assert(ok, 'GATE FALLITO: makehdl non ha generato VHDL per ACC-IIDM (R17)');
  fprintf('\n=== GATE HDL PASSATO: ACC-IIDM (R17) self-contained + HDL-ready ===\n');
end

function cleanupGate(oldPath, oldDir)
  cd(oldDir); path(oldPath); bdclose('all');
end
