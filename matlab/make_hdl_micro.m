function make_hdl_micro()
%MAKE_HDL_MICRO  Codegen VHDL di micro_ac e micro_mac (nessun argomento: stato interno LFSR).
  here = fileparts(mfilename('fullpath')); addpath(here);
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  for fn = {'micro_ac', 'micro_mac'}
    fprintf('== codegen HDL: %s ==\n', fn{1});
    codegen('-config', cfg, fn{1}, '-args', {}, '-report');
    fprintf('OK: %s\n', fn{1});
  end
end
