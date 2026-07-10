function make_hdl_decode()
%MAKE_HDL_DECODE  [decode] Codegen VHDL dello stadio decode (snn_decode_hdl).
  here = fileparts(mfilename('fullpath')); addpath(here);
  raw = fi(zeros(5,1), 1, 21, 13);
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  fprintf('== codegen HDL decode: snn_decode_hdl ==\n');
  codegen('-config', cfg, 'snn_decode_hdl', '-args', {raw}, '-report');
  fprintf('OK: RTL decode generato\n');
  rpt = fullfile(here, 'codegen', 'snn_decode_hdl', 'hdlsrc', 'resource_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    fprintf('  --- risorse decode (STIMA) ---\n');
    for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'RAMs'}
      tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
      if ~isempty(tok), fprintf('  %-22s %s\n', key{1}, tok{1}); end
    end
  end
end
