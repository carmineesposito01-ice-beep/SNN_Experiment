function probe_iidm_divblock()
%PROBE_IIDM_DIVBLOCK  [IIDM #1 make-or-break] La conversione MATLAB-to-dataflow (imposta da un blocco
%  HDLMathLib/Divide ACCANTO alla chart) GENERA VHDL ora che il tanh e' una LUT bit-exact (A1, 2b)?
%  SP4 #1 mori' proprio qui ("Provide a floating-point input": dataflow vieta tanh fixed). Con A1 il tanh
%  non e' piu' fixed nativo -> quel blocco dovrebbe sparire. MA la chart ora ha anche la SNN 8-stadi (tanti
%  persistent): il dataflow potrebbe inciampare in un ALTRO vincolo §9 (HDL_PHASE). Questo probe lo scopre.
%
%  ESITO:
%    ✅ VHDL generato  -> #1 RIVIVIBILE: il divisore pipelinato (HDLMathLib/Divide, G1 bit-exact a divide())
%                        si puo' integrare via handshake -> Fmax controllore SU, bit-exact, GRATIS.
%    ❌ makehdl fallito -> si legge QUALE vincolo dataflow (tanh? persistent? struct?) -> se non e' il tanh,
%                        #1 resta morta e domani si va su #2 (divisore digit-recurrence a mano nella chart).
%
%  NB: uso il blocco Divide COMBINATORIO (latencyMode='Zero'): la conversione dataflow (cio' che uccise #1)
%  scatta per la CONVIVENZA blocco<->chart, non per la pipeline. Se genera con 'Zero', genera col pipelinato
%  (stessa struttura, solo registri in piu'). La pipeline/Fmax e' il passo di domani, non di stasera.
  here = fileparts(mfilename('fullpath')); addpath(here);
  lib = 'snn_champions_lib';
  bdclose('all');
  load_system(fullfile(here, [lib '.slx'])); set_param(lib, 'Lock', 'off');
  mdl = 'm_iidm_divblk'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  dut = [mdl '/DUT'];
  add_block([lib '/Donatello_ACC_IIDM_M'], dut);        % chart attuale: LUT tanh + SNN 8-stadi + fsm_div
  try, set_param(dut, 'LinkStatus', 'none'); catch, end

  % --- un blocco HDLMathLib/Divide DENTRO DUT, accanto alla chart (2 nuovi inport + valid -> dataOut) ---
  dts = 'fixdt(1,20,8)';                                  % ~T.acc (Q?.8) come in probe_divide_bitexact
  add_block('built-in/Inport',  [dut '/dvd'], 'Port', '5');
  add_block('built-in/Inport',  [dut '/dvr'], 'Port', '6');
  add_block('simulink/Signal Attributes/Data Type Conversion', [dut '/cvd'], 'OutDataTypeStr', dts);
  add_block('simulink/Signal Attributes/Data Type Conversion', [dut '/cvr'], 'OutDataTypeStr', dts);
  add_block('simulink/Sources/Constant', [dut '/vld'], 'Value', 'true', 'OutDataTypeStr', 'boolean', 'SampleTime', '-1');
  add_block('HDLMathLib/Divide', [dut '/DIV']);
  set_param([dut '/DIV'], 'latencyMode', 'Zero', 'RndMeth', 'Zero', 'OutDataTypeStr', dts);
  add_block('built-in/Outport', [dut '/qout'], 'Port', '2');
  add_line(dut, 'dvd/1', 'cvd/1'); add_line(dut, 'dvr/1', 'cvr/1');
  add_line(dut, 'cvd/1', 'DIV/1'); add_line(dut, 'cvr/1', 'DIV/2'); add_line(dut, 'vld/1', 'DIV/3');
  add_line(dut, 'DIV/1', 'qout/1');

  % --- mdl-level: 6 costanti -> DUT, 2 outport ---
  vals = {'10', '6', '2', '4', '30', '8'};
  for j = 1:6
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], ...
              'Value', vals{j}, 'OutDataTypeStr', 'fixdt(1,32,20)', 'SampleTime', '1');
    add_line(mdl, ['i' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('built-in/Outport', [mdl '/oa'], 'Port', '1'); add_line(mdl, 'DUT/1', 'oa/1');
  add_block('built-in/Outport', [mdl '/oq'], 'Port', '2'); add_line(mdl, 'DUT/2', 'oq/1');
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', 'StopTime', '10');

  out = fullfile(here, 'hdl_iidm_divblk'); if exist(out, 'dir'), rmdir(out, 's'); end
  fprintf('\n==== PROBE IIDM #1 make-or-break: Divide block ACCANTO alla chart (LUT tanh + SNN 8-stadi) ====\n');
  ok = false; msg = '';
  try
    set_param(mdl, 'SimulationCommand', 'update');       % propaga i tipi, rivela subito l'errore dataflow
    makehdl(dut, 'TargetLanguage', 'VHDL', 'TargetDirectory', out, 'GenerateHDLTestBench', 'off');
    v = dir(fullfile(out, '**', '*.vhd'));
    ok = ~isempty(v);
    fprintf('\n>> ESITO: OK VHDL GENERATO (%d file) -> #1 RIVIVIBILE (il tanh-LUT ha sbloccato il dataflow).\n', numel(v));
    fprintf('   Prossimo (domani): integrare il divisore PIPELINATO via handshake + sintesi OOC.\n');
  catch e
    msg = regexprep(e.message, '\s+', ' ');
    fprintf('\n>> ESITO: FALLITO makehdl:\n   %s\n', msg);
    fprintf('   -> se NON e'' il tanh, il blocco dataflow e'' un altro vincolo §9 (persistent SNN 8-stadi?).\n');
  end
  fprintf('==== FINE PROBE (ok=%d) ====\n', ok);
  close_system(mdl, 0); bdclose('all');
end
