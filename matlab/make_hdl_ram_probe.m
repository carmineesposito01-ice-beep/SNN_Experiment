function make_hdl_ram_probe()
%MAKE_HDL_RAM_PROBE  [B2 hdl.RAM] Codegen del probe cycle-based (snn_ram_probe).
%  Verifica che hdl.RAM produca 1 lane + RAM. Metrica: Multipliers ~22 (1 lane) + RAM.
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn  = fi(zeros(4,1),  1, 19, 13);
  tlr = fi(zeros(16,1), 1, 19, 13);

  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end

  fprintf('== codegen HDL ram-probe: snn_ram_probe ==\n');
  ok = true;
  try
    codegen('-config', cfg, 'snn_ram_probe', '-args', {xn, tlr}, '-report');
  catch e
    ok = false; fprintf('CODEGEN FAILED: %s\n', e.message);
  end
  rpt = fullfile(here, 'codegen', 'snn_ram_probe', 'hdlsrc', 'resource_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    fprintf('  --- risorse (STIMA) ---\n');
    for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'RAMs', 'Total 1-Bit Registers'}
      tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
      if ~isempty(tok), fprintf('  %-24s %s\n', key{1}, tok{1}); end
    end
    m = regexp(txt, 'Multipliers\s*\((\d+)\)', 'tokens', 'once');
    if ~isempty(m)
      nm = str2double(m{1});
      if nm <= 60, fprintf('>> SERIALIZZATO (Multipliers=%d ~ 1 lane) + RAM\n', nm);
      else,        fprintf('>> NON serializzato (Multipliers=%d)\n', nm); end
    end
  end
  if ok, fprintf('>> CODEGEN OK\n'); else, fprintf('>> CODEGEN KO\n'); end
end
