function gen_hdl_tops()
%GEN_HDL_TOPS  Genera snn_hdl_<name>.m: wrapper HDL self-contained per champion.
%  Pesi BAKED come letterali (costanti a codegen-time) + chiamata a snn_core (il
%  forward NON e' ri-scritto: single-source). Input xn [4x1] normalizzato (fi Q5.13),
%  output raw [5x1] LI (fi Q7.13). Il decode NON e' incluso (LUT separata, step 2).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name));
    fn = fullfile(here, ['snn_hdl_' name '.m']);
    fid = fopen(fn, 'w');
    w = @(varargin) fprintf(fid, varargin{:});
    w('function raw = snn_hdl_%s(xn) %%#codegen\n', name);
    w('%%SNN_HDL_%s  Wrapper HDL: pesi baked + snn_core (fixed Q?.13). GENERATO da gen_hdl_tops.\n', upper(name));
    w('%%  xn [4x1] normalizzato (fi Q5.13) -> raw [5x1] LI. Decode escluso (LUT in fabric).\n');
    w('  W = struct();\n');
    w('  W.hidden = int32(%d); W.rank = int32(%d); W.n_ticks = int32(10); W.max_delay = int32(6);\n', ...
      c.hidden, c.rank);
    % coder.const: pesi COSTANTI a codegen-time -> CSD folda i po2 in shift (0 DSP).
    % In MATLAB interpretato coder.const e' no-op, quindi la parita' resta intatta.
    w('  W.fc_weight = coder.const(%s);\n', mat2str(c.fc_weight, 17));
    w('  W.rec_U = coder.const(%s);\n', mat2str(c.rec_U, 17));
    w('  W.rec_V = coder.const(%s);\n', mat2str(c.rec_V, 17));
    w('  W.readout = coder.const(%s);\n', mat2str(c.readout, 17));
    w('  W.delays = coder.const(%s);\n', mat2str(c.delays, 17));
    w('  W.base_threshold = coder.const(%s);\n', mat2str(c.base_threshold(:), 17));
    w('  W.thresh_jump = coder.const(%s);\n', mat2str(c.thresh_jump(:), 17));
    w('  W.leak_div = coder.const(%s);\n', mat2str(c.leak_div(:), 17));
    w('  T = snn_types(''fixed'', 13);\n');
    w('  raw = snn_core(xn, W, T);\n');
    w('end\n');
    fclose(fid);
    fprintf('scritto %s (%s, hidden=%d rank=%d)\n', ['snn_hdl_' name '.m'], ...
            char(string(c.variant)), c.hidden, c.rank);
  end
end
