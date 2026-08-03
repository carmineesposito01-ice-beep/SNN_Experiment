function probe_snn_fwd(tag)
%PROBE_SNN_FWD  [B2.0-2d] Standalone del SOLO forward SNN (snn_b2_fsm -> raw), per misurare il TETTO HW
%  della rete verso i 136 MHz del tanh-L1. Il collo e' lo stadio-C di snn_b2_fsm (pC_fat/pC_V): qui non
%  c'e' ne' decode ne' legge IIDM (che nel controllore cappa a 15,84) -> il WNS di questo DUT E' il tetto SNN.
%  Chart SOLA nel subsystem => niente conversione MATLAB-to-dataflow (fixed ammesso, HDL_PHASE §9).
%  I/O registrato (read-before-write). ROM+types+fsm INLINATI => self-contained, ricostruito dal
%  snn_b2_fsm.m CORRENTE ad ogni round. VHDL -> matlab/hdl_pipe/<tag>; sintesi OOC (top DUT) a valle.
%    probe_snn_fwd('snn_fwd_r2')
  if nargin < 1 || isempty(tag), tag = 'snn_fwd'; end
  here = fileparts(mfilename('fullpath'));
  out  = fullfile(here, 'hdl_pipe', tag); if exist(out,'dir'), rmdir(out,'s'); end; mkdir(out);
  srcRom   = fileread(fullfile(here, 'b2_rom_active.m'));   % ROM Donatello (baked, coder.const)
  srcTypes = fileread(fullfile(here, 'snn_types.m'));
  srcFsm   = fileread(fullfile(here, 'snn_b2_fsm.m'));
  main = strjoin({
    'function [o1, o2, o3, o4, o5] = SNNFWD(x1, x2, x3, x4)'
    '%#codegen'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = cast([x1; x2; x3; x4], ''like'', Tt.V);'
    '  persistent xprev started rawl'
    '  if isempty(started)'
    '    xprev = xn; started = true; rawl = cast(zeros(5,1), ''like'', Tt.raw); go = true;'
    '  else'
    '    go = any(xn ~= xprev);            % edge-triggered: 1 campione = 1 inferenza'
    '  end'
    '  xprev = xn;'
    '  [r, valid] = snn_b2_fsm(xn, go);'
    '  rr = rawl;                          % READ-BEFORE-WRITE: uscita = registro (rawl vero registro)'
    '  if valid, rawl = r; end'
    '  o1 = rr(1); o2 = rr(2); o3 = rr(3); o4 = rr(4); o5 = rr(5);'
    'end'}, newline);
  code = [main newline newline srcRom newline newline srcTypes newline newline srcFsm];

  bdclose('all'); mdl = ['m_' tag]; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT'];
  add_block('built-in/Subsystem', sub);
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/fcn']);
  ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/fcn']); ch.Script = code;
  for j = 1:4
    add_block('built-in/Inport', [sub '/x' num2str(j)], 'Port', num2str(j));
    add_line(sub, ['x' num2str(j) '/1'], ['fcn/' num2str(j)]);
  end
  for j = 1:5
    add_block('built-in/Outport', [sub '/o' num2str(j)], 'Port', num2str(j));
    add_line(sub, ['fcn/' num2str(j)], ['o' num2str(j) '/1']);
  end
  for j = 1:4
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], ...
              'Value', sprintf('%.4f', 0.1*j), 'OutDataTypeStr', 'fixdt(1,19,13)', 'SampleTime', '1');
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  for j = 1:5
    add_block('built-in/Outport', [mdl '/y' num2str(j)], 'Port', num2str(j));
    add_line(mdl, ['DUT/' num2str(j)], ['y' num2str(j) '/1']);
  end
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', 'StopTime', '10');
  set_param(mdl, 'SimulationCommand', 'update');           % propaga tipi, rivela errori chart
  makehdl(sub, 'TargetLanguage', 'VHDL', 'TargetDirectory', out, 'GenerateHDLTestBench', 'off');
  v = dir(fullfile(out, '**', '*.vhd'));
  fprintf('>> probe SNN fwd  %s: VHDL OK (%d file) -> %s\n', tag, numel(v), out);
  close_system(mdl, 0); bdclose('all');
end
