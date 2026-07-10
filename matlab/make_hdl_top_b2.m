function make_hdl_top_b2()
%MAKE_HDL_TOP_B2  [B2] Codegen VHDL del top integrato (snn_top_b2 = SNN B2 + decode).
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn = fi(zeros(4,1), 1, 19, 13);
  start = false;
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  fprintf('== codegen HDL top B2: snn_top_b2 ==\n');
  codegen('-config', cfg, 'snn_top_b2', '-args', {xn, start}, '-report');
  fprintf('OK: RTL top B2 generato\n');
  rpt = fullfile(here, 'codegen', 'snn_top_b2', 'hdlsrc', 'resource_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    fprintf('  --- risorse top (STIMA) ---\n');
    for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'RAMs'}
      tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
      if ~isempty(tok), fprintf('  %-22s %s\n', key{1}, tok{1}); end
    end
  end
end
