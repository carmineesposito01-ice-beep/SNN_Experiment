function ok = run_block_hdl_gate(blockName)
%RUN_BLOCK_HDL_GATE  Cancello "ALTRO PC" per i blocchi HDL-ready self-contained di snn_champions_lib.
%  Dimostra il requisito: **portando SOLO il .slx su un altro PC, HDL Coder deve generare il VHDL,
%  senza alcun altro file**. Come: copia solo `snn_champions_lib.slx` in una cartella isolata, TOGLIE
%  `matlab/` dal path (verificando che nessun .m del progetto sia raggiungibile), istanzia il blocco e
%  lancia `makehdl`. Se il VHDL esce => self-contained e HDL-ready **dimostrato**, non promesso.
%
%  ok = run_block_hdl_gate()                 % default: Donatello_Champion
%  ok = run_block_hdl_gate('Donatello_LUT64')
%
%  Atteso: fra i file generati c'e' `DualPortRAM_generic.vhd` = l'hdl.RAM della FSM ⇒ e' davvero
%  l'architettura **time-mux** del deployato (HDL_PHASE §3.1.1), non la parallela superata.
  if nargin < 1, blockName = 'Donatello_Champion'; end
  here = fileparts(mfilename('fullpath'));
  lib  = 'snn_champions_lib';
  work = fullfile(tempdir, 'snn_hdl_gate');

  bdclose('all');
  if exist(work, 'dir'), rmdir(work, 's'); end
  mkdir(work);
  copyfile(fullfile(here, [lib '.slx']), work);      % <-- SOLO il .slx

  oldPath = path; oldDir = pwd;
  restore = onCleanup(@() cleanupGate(oldPath, oldDir));
  warning('off', 'MATLAB:rmpath:DirNotFound');
  rmpath(here);                                      % simula l'altro PC
  cd(work);

  % l'isolamento e' parte del test: se un .m e' ancora raggiungibile, il gate non prova nulla
  for f = {'snn_b2_fsm', 'b2_rom_active', 'snn_types', 'snn_decode_hdl', 'snn_decode_lut'}
    assert(isempty(which(f{1})), 'gate non valido: %s ancora sul path', f{1});
  end
  fprintf('isolamento OK: nessun .m del progetto raggiungibile\n');

  ok = false;
  load_system(fullfile(work, [lib '.slx']));
  mdl = 'gate_mdl'; new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT'];
  add_block([lib '/' blockName], sub);
  vals = {'10', '6', '2', '4'};                      % s, v, dv, v_l fisici (fixed: double non e' HDL)
  for j = 1:4
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], 'Value', vals{j}, ...
              'OutDataTypeStr', 'fixdt(1,32,20)', 'SampleTime', '1');   % >=20 bit frazionari (vedi §3.1.3)
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  for j = 1:5
    add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j));
    add_line(mdl, ['DUT/' num2str(j)], ['o' num2str(j) '/1']);
  end
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', 'StopTime', '10');
  save_system(mdl, fullfile(work, [mdl '.slx']));
  set_param(mdl, 'SimulationCommand', 'update');     % compila: rivela errori nella chart
  outdir = fullfile(work, 'hdlsrc');
  makehdl(sub, 'TargetLanguage', 'VHDL', 'TargetDirectory', outdir, 'GenerateHDLTestBench', 'off');

  v = dir(fullfile(outdir, '**', '*.vhd'));
  ok = ~isempty(v);
  fprintf('\n%-28s VHDL generati: %d\n', blockName, numel(v));
  for i = 1:numel(v), fprintf('   %-30s %8d byte\n', v(i).name, v(i).bytes); end
  hasRAM = any(strcmp({v.name}, 'DualPortRAM_generic.vhd'));
  fprintf('   time-mux (DualPortRAM presente): %s\n', string(hasRAM));
  assert(ok && hasRAM, 'gate fallito: VHDL assente o architettura non time-mux');
  fprintf('\n=== GATE PASSATO: %s e'' self-contained e HDL-ready ===\n', blockName);
end

function cleanupGate(oldPath, oldDir)
  cd(oldDir); path(oldPath); bdclose('all');
end
