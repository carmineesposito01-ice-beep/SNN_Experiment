function make_hdl_probe2()
%MAKE_HDL_PROBE2  [B2 S2a] Codegen del probe pulito (snn_tick_probe2).
%  Verifica se, con pesi interni + init scalarizzati, l'auto-RAM-mapping di V/fatigue regge.
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn  = fi(zeros(4,1),  1, 19, 13);
  tlr = fi(zeros(16,1), 1, 19, 13);

  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  cfg.LoopOptimization = 'StreamLoops';
  cfg.MapPersistentVarsToRAM = true;
  cfg.RAMThreshold = '16';

  fprintf('== codegen HDL probe2: snn_tick_probe2 ==\n');
  ok = true;
  try
    codegen('-config', cfg, 'snn_tick_probe2', '-args', {xn, tlr}, '-report');
  catch e
    ok = false; fprintf('CODEGEN FAILED: %s\n', e.message);
  end
  rpt = fullfile(here, 'codegen', 'snn_tick_probe2', 'hdlsrc', 'snn_tick_probe2_hdl_conformance_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    nramfail = numel(regexp(txt, 'RAM mapping failed', 'start'));
    fprintf('>> RAM mapping failed warnings: %d\n', nramfail);
    if nramfail == 0, fprintf('>> V/fatigue MAPPANO in RAM (auto-flow OK)\n');
    else,             fprintf('>> auto-flow NON basta -> serve hdl.RAM esplicito\n'); end
  end
  if ok, fprintf('>> CODEGEN OK\n'); else, fprintf('>> CODEGEN KO\n'); end
end
