function make_hdl_decode_lut()
%MAKE_HDL_DECODE_LUT  [SP1 Task 5] Codegen VHDL del decode LUT-N (snn_decode_lut) per ogni N, a
%  conferma dell'HDL-readiness: 0 errori, sigmoide realizzata come TABELLA COSTANTE (niente exp nel
%  datapath -> la tabella e' pre-calcolata a codegen-time via coder.const), risorse crescenti con N.
%  Mirror di make_hdl_decode per snn_decode_lut(raw, N=coder.Constant).
%  La dir HDL (codegen/snn_decode_lut/hdlsrc) e' la STESSA per ogni N (il nome DUT non cambia) ->
%  i numeri si leggono SUBITO dopo ogni codegen, prima che il N successivo la sovrascriva. RTL gitignored.
  here = fileparts(mfilename('fullpath')); addpath(here);
  raw = fi(zeros(5,1), 1, 21, 13);
  Ns  = [16 32 64 128 256 512];
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  keys = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'RAMs'};
  Res  = zeros(numel(Ns), numel(keys)); noexp = false(1, numel(Ns));
  hdldir = fullfile(here, 'codegen', 'snn_decode_lut', 'hdlsrc');
  for i = 1:numel(Ns)
    N = Ns(i);
    fprintf('== HDL decode LUT-%d ==\n', N);
    codegen('-config', cfg, 'snn_decode_lut', '-args', {raw, coder.Constant(N)}, '-report');
    rpt = fullfile(hdldir, 'resource_report.html');
    if isfile(rpt)
      txt = fileread(rpt);
      for k = 1:numel(keys)
        tok = regexp(txt, [regexptranslate('escape', keys{k}) '\s*\((\d+)\)'], 'tokens', 'once');
        if ~isempty(tok), Res(i,k) = str2double(tok{1}); end
      end
    end
    vhd = fullfile(hdldir, 'snn_decode_lut.vhd');
    if isfile(vhd)
      vt = lower(fileread(vhd));
      noexp(i) = ~(contains(vt, 'exp(') || contains(vt, 'exponential'));
    end
  end
  fprintf('\n== SP1 Task 5 - HDL Coder: risorse (STIMA) decode LUT-N ==\n');
  fprintf('%-5s | %-11s | %-18s | %-9s | %-12s | %-4s | no-exp\n', 'N', keys{:});
  for i = 1:numel(Ns)
    fprintf('%-5d | %-11d | %-18d | %-9d | %-12d | %-4d | %s\n', Ns(i), ...
            Res(i,1), Res(i,2), Res(i,3), Res(i,4), Res(i,5), tf(noexp(i)));
  end
  assert(all(noexp), 'qualche N contiene exp nel datapath VHDL');
  fprintf('OK: %d/%d decode LUT-N HDL-ready (0 errori, sigmoide = tabella costante, nessun exp).\n', ...
          numel(Ns), numel(Ns));
end

function s = tf(b)
  if b, s = 'si'; else, s = 'NO'; end
end
