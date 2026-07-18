function info = build_tanhdut(tag, srcTanhFile)
%BUILD_TANHDUT  [B2.0-2b L1] Costruisce un DUT scratch col SOLO tanh (I/O registrato via persistenti,
%  tanh combinatorio in mezzo: replica il path in-blocco st_dd_reg -> tanh -> thl_reg). La MATLAB Function
%  e' SOLA nel subsystem (niente blocchi accanto -> niente conversione MATLAB-to-dataflow, tanh fixed
%  ammesso, HDL_PHASE §9). srcTanhFile = file .m della variante: `function th = <fname>(dd)`, th sfix19_En17.
  here = fileparts(mfilename('fullpath'));
  out = fullfile(here,'hdl_tanh',tag); if exist(out,'dir'), rmdir(out,'s'); end
  src = fileread(fullfile(here, srcTanhFile));
  fname = regexp(src, 'function\s+\w+\s*=\s*(\w+)\s*\(', 'tokens', 'once'); fname = fname{1};
  main = strjoin({
    'function th = fcn(dd)'
    '%#codegen'
    '  persistent ddl thl started'
    '  if isempty(started)'
    ['    ddl = cast(0,''like'',dd); thl = ' fname '(cast(0,''like'',dd)); started = true;']
    '  end'
    '  th  = thl;                 % READ-BEFORE-WRITE: emette il valore REGISTRATO (thl = vero registro)'
    ['  thl = ' fname '(ddl);      % nuovo tanh: path TIMED ddl_reg -> tanh -> thl_reg']
    '  ddl = dd;                  % registra l''ingresso (porta -> ddl_reg)'
    'end'}, newline);
  code = [main newline newline src];
  bdclose('all'); mdl = ['m_tanh_' tag]; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT'];
  add_block('built-in/Subsystem', sub);
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/fcn']);
  ch = sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/fcn']); ch.Script = code;
  add_block('built-in/Inport', [sub '/dd'], 'Port','1'); add_line(sub, 'dd/1', 'fcn/1');
  add_block('built-in/Outport',[sub '/th'], 'Port','1'); add_line(sub, 'fcn/1', 'th/1');
  add_block('simulink/Sources/Constant',[mdl '/i1'],'Value','1','OutDataTypeStr','fixdt(1,19,8)','SampleTime','1');
  add_line(mdl,'i1/1','DUT/1');
  add_block('built-in/Outport',[mdl '/o1'],'Port','1'); add_line(mdl,'DUT/1','o1/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');            % propaga i tipi, rivela errori nella chart
  makehdl(sub,'TargetLanguage','VHDL','TargetDirectory',out,'GenerateHDLTestBench','off');
  v = dir(fullfile(out,'**','*.vhd')); assert(~isempty(v),'nessun VHDL per %s',tag);
  info = struct('tag',tag,'outdir',v(1).folder,'fname',fname);
  fprintf('L1 DUT %s generato (%d vhd) in %s\n', tag, numel(v), v(1).folder);
  close_system(mdl,0);
end
