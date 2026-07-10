function make_hdl_probe()
%MAKE_HDL_PROBE  [B2 S1] Codegen del probe di serializzazione (snn_tick_probe).
%  Verifica se HDL Coder serializza il loop neuroni top-level (1 lane + RAM).
%  Metrica chiave nel resource summary: Multipliers ~22 (serializzato) vs ~704 (unrolled).
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn       = fi(zeros(4,1),   1, 19, 13);
  fcw_all  = fi(zeros(32,4),  1, 16, 13);
  Uw_all   = fi(zeros(32,16), 1, 16, 13);
  tlr      = fi(zeros(16,1),  1, 19, 13);
  bth_all  = fi(zeros(32,1),  1, 19, 13);
  tj_all   = fi(zeros(32,1),  1, 17, 13);
  Wout_all = fi(zeros(5,32),  1, 16, 13);

  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  cfg.LoopOptimization = 'StreamLoops';
  cfg.MapPersistentVarsToRAM = true;
  cfg.RAMThreshold = '16';        % V/fatigue (32) -> RAM

  fprintf('== codegen HDL probe: snn_tick_probe ==\n');
  codegen('-config', cfg, 'snn_tick_probe', '-args', ...
          {xn, fcw_all, Uw_all, tlr, bth_all, tj_all, Wout_all}, '-report');
  fprintf('OK: probe generato\n');
  rpt = fullfile(here, 'codegen', 'snn_tick_probe', 'hdlsrc', 'resource_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    fprintf('  --- risorse probe (STIMA) ---\n');
    for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'Shift operators'}
      tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
      if ~isempty(tok), fprintf('  %-20s %s\n', key{1}, tok{1}); end
    end
    m = regexp(txt, 'Multipliers\s*\((\d+)\)', 'tokens', 'once');
    if ~isempty(m)
      nm = str2double(m{1});
      if nm <= 60,  fprintf('>> SERIALIZZATO (Multipliers=%d ~ 1 lane)\n', nm);
      else,         fprintf('>> NON serializzato (Multipliers=%d ~ unrolled)\n', nm); end
    end
  end
end
