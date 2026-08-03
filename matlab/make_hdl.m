function make_hdl(name)
%MAKE_HDL  Genera RTL (VHDL) dal core fixed-point di un champion via HDL Coder
%  (workflow MATLAB-to-HDL: design snn_hdl_<name> + testbench generato).
%  Il design e' gia' fixed-point (fi Q?.13) -> niente float->fixed conversion.
%  Uso: make_hdl            % Donatello
%       make_hdl('Raffaello')
  if nargin < 1, name = 'Donatello'; end
  here = fileparts(mfilename('fullpath')); addpath(here);
  design = ['snn_hdl_' name]; tb = ['tb_hdl_' name];

  % --- genera il testbench (stream del golden x_norm del champion) ---
  fid = fopen(fullfile(here, [tb '.m']), 'w');
  fprintf(fid, 'function %s()\n', tb);
  fprintf(fid, '%%%s  Testbench HDL (stream x_norm golden). GENERATO da make_hdl.\n', upper(tb));
  fprintf(fid, '  d = load(''champions_export.mat''); champs = d.champions;\n');
  fprintf(fid, '  if iscell(champs), champs = [champs{:}]; end\n');
  fprintf(fid, '  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), ''%s''), champs), 1);\n', name);
  fprintf(fid, '  c = champs(idx); Tf = snn_types(''fixed'', 13); N = size(c.x_norm, 1);\n');
  fprintf(fid, '  for t = 1:N\n');
  fprintf(fid, '    xn = cast(c.x_norm(t, :).'', ''like'', Tf.V);\n');
  fprintf(fid, '    raw = %s(xn); %%#ok\n', design);
  fprintf(fid, '  end\n');
  fprintf(fid, 'end\n');
  fclose(fid);

  % --- config HDL Coder ---
  proto = fi(zeros(4, 1), 1, 19, 13);          % xn Q5.13 (== snn_types fixed f=13)
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.TestBenchName = tb;
  cfg.GenerateHDLTestBench = true;
  cfg.SimulateGeneratedCode = false;           % no cosim in questo step
  try, cfg.HDLLintTool = 'None'; catch, end

  % --- ottimizzazioni per l'AREA (bit-preserving: HDL Coder mantiene la semantica) ---
  cfg.LoopOptimization = 'StreamLoops';               % folda i loop (tick/delay) invece di unroll
  cfg.ConstantMultiplierOptimization = 'CSD';         % pesi po2 costanti -> shift
  cfg.ResourceSharing = 32;                           % condivide fino a 32 op identiche (folda i 32 neuroni)
  cfg.ShareAdders = true;                             % condivide anche gli adder (default: solo mult)

  fprintf('== codegen HDL: %s (tb=%s) ==\n', design, tb);
  codegen('-config', cfg, design, '-args', {proto}, '-report');
  fprintf('OK: RTL generato per %s\n', name);
  hdl_resource_summary(fullfile(here, 'codegen', design, 'hdlsrc', 'resource_report.html'));
end

function hdl_resource_summary(rpt)
  if ~isfile(rpt), fprintf('(nessun resource report)\n'); return; end
  txt = fileread(rpt);
  fprintf('  --- risorse ---\n');
  for key = {'Multipliers', 'Adders/Subtractors', 'Registers', 'Multiplexers', 'Shift operators'}
    tok = regexp(txt, [regexptranslate('escape', key{1}) '\s*\((\d+)\)'], 'tokens', 'once');
    if ~isempty(tok), fprintf('  %-20s %s\n', key{1}, tok{1}); end
  end
end
