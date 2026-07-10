function make_hdl_b2fsm()
%MAKE_HDL_B2FSM  [B2] Codegen VHDL della FSM B2 completa (snn_b2_fsm) per Donatello.
%  Da sintetizzare OOC su 7020 per il numero d'area REALE del B2 deployabile.
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn = fi(zeros(4,1), 1, 19, 13);
  start = false;

  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = true;
  cfg.TestBenchName = 'tb_b2_fsm';
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end

  fprintf('== codegen HDL B2 FSM: snn_b2_fsm ==\n');
  codegen('-config', cfg, 'snn_b2_fsm', '-args', {xn, start}, '-report');
  fprintf('OK: RTL FSM B2 generato\n');
  rpt = fullfile(here, 'codegen', 'snn_b2_fsm', 'hdlsrc', 'resource_report.html');
  if isfile(rpt)
    txt = fileread(rpt);
    fprintf('  --- risorse FSM (STIMA) ---\n');
    for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'RAMs', 'Shift operators'}
      tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
      if ~isempty(tok), fprintf('  %-22s %s\n', key{1}, tok{1}); end
    end
  end
end
