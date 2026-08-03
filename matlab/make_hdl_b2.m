function make_hdl_b2()
%MAKE_HDL_B2  [B2 SPIKE] Codegen VHDL della lane-neurone B2 (snn_neuron_b2) per stima area.
%  Genera l'RTL di UNA lane combinatoria (pesi = dato -> MAC). Da sintetizzare OOC su 7020
%  per LUT/DSP reali della lane; il B2 completo = lane + BRAM(pesi/stato) + controllo.
  here = fileparts(mfilename('fullpath')); addpath(here);
  % prototipi fi (f=13): stato scalare, input vettori, pesi = dato
  Vp   = fi(0, 1, 19, 13);          % V      Q5.13
  fatp = fi(0, 1, 17, 13);          % fatigue Q3.13
  xtap = fi(zeros(4,1),  1, 19, 13); % 4 tap sinaptici Q5.13
  tlr  = fi(zeros(16,1), 1, 19, 13); % ricorrenza rank=16 Q5.13
  fcw  = fi(zeros(4,1),  1, 16, 13); % pesi fc  Q2.13 (dato)
  Uw   = fi(zeros(16,1), 1, 16, 13); % pesi U   Q2.13 (dato)
  bth  = fi(0, 1, 19, 13);          % base_threshold Q5.13
  tj   = fi(0, 1, 17, 13);          % thresh_jump Q3.13
  Wout = fi(zeros(5,1),  1, 16, 13); % pesi readout Q2.13 (dato)

  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end

  fprintf('== codegen HDL B2 lane: snn_neuron_b2 ==\n');
  codegen('-config', cfg, 'snn_neuron_b2', '-args', ...
          {Vp, fatp, xtap, tlr, fcw, Uw, bth, tj, Wout}, '-report');
  fprintf('OK: RTL lane B2 generato\n');
  hdl_resource_summary(fullfile(here, 'codegen', 'snn_neuron_b2', 'hdlsrc', 'resource_report.html'));
end

function hdl_resource_summary(rpt)
  if ~isfile(rpt), fprintf('(nessun resource report)\n'); return; end
  txt = fileread(rpt);
  fprintf('  --- risorse lane (STIMA HDL Coder) ---\n');
  for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'Shift operators'}
    tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
    if ~isempty(tok), fprintf('  %-20s %s\n', key{1}, tok{1}); end
  end
end
