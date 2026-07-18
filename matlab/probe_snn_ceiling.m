function probe_snn_ceiling(blk, tag)
%PROBE_SNN_CEILING  [B2.0-2d] Sintesi OOC standalone di un blocco SNN(+decode) SENZA la legge IIDM,
%  per misurare il tetto HW INTRINSECO della SNN -- cioe' quanto in alto potrebbe salire l'Fmax se il
%  divisore IIDM (collo del controllore intero dopo R2) fosse gratis.
%    Donatello_Champion = s,v,dv,v_l -> snn_b2_fsm (R2) -> snn_decode_lut(64) -> [v0 T s0 a b].
%    4 ingressi (fixdt(1,32,20)), 5 uscite. NESSUNA divisione (la legge IIDM sta a valle, nel blocco M).
%  Riusa il pattern di probe_pipe_tanh: copia il blocco in un modello scratch (LinkStatus=none), makehdl.
%  VHDL -> matlab/hdl_pipe/<tag>; sintesi OOC + parse a valle (bash), stesso synth_acc_iidm.tcl (top DUT).
%    probe_snn_ceiling('Donatello_Champion','snn_champ')
  if nargin < 1 || isempty(blk), blk = 'Donatello_Champion'; end
  if nargin < 2 || isempty(tag), tag = 'snn_champ'; end
  here = fileparts(mfilename('fullpath'));
  out  = fullfile(here, 'hdl_pipe', tag); if exist(out,'dir'), rmdir(out,'s'); end; mkdir(out);
  lib  = 'snn_champions_lib';

  bdclose('all');
  load_system(fullfile(here, [lib '.slx'])); set_param(lib, 'Lock', 'off');
  mdl = ['m_snn_' tag]; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  dut = [mdl '/DUT'];
  add_block([lib '/' blk], dut);
  try, set_param(dut, 'LinkStatus', 'none'); catch, end   % slink: senza, la chart e' read-only
  vals = {'10', '6', '2', '4'};                            % s,v,dv,v_l (come probe_pipe_tanh)
  for j = 1:4
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], ...
              'Value', vals{j}, 'OutDataTypeStr', 'fixdt(1,32,20)', 'SampleTime', '1');
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  for j = 1:5                                               % 5 uscite: v0,T,s0,a,b
    add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j));
    add_line(mdl, ['DUT/' num2str(j)], ['o' num2str(j) '/1']);
  end
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', 'StopTime', '10');
  set_param(mdl, 'SimulationCommand', 'update');           % propaga i tipi, rivela errori chart
  makehdl(dut, 'TargetLanguage', 'VHDL', 'TargetDirectory', out, 'GenerateHDLTestBench', 'off');
  v = dir(fullfile(out, '**', '*.vhd'));
  fprintf('>> probe SNN ceiling  %s (%s): VHDL OK (%d file) -> %s\n', tag, blk, numel(v), out);
  close_system(mdl, 0); bdclose('all');
end
