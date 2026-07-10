function make_hdl_ann()
%MAKE_HDL_ANN  Codegen VHDL della ANN densa time-mux (mirror make_hdl_b2fsm).
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn = fi(zeros(4, 1), 1, 19, 13);
  start = false;
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  fprintf('== codegen HDL ANN ==\n');
  codegen('-config', cfg, 'ann_mlp', '-args', {xn, start}, '-report');
  fprintf('OK: ann_mlp RTL generato\n');
end
