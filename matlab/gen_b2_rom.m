function gen_b2_rom()
%GEN_B2_ROM  Genera b2_donatello_rom.m con i pesi Donatello BAKED come letterali
%  (costanti a codegen-time -> niente load(), niente ricorsione iofun). Come gen_hdl_tops.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), 'Donatello'), champs), 1);
  c = champs(idx);
  fid = fopen(fullfile(here, 'b2_donatello_rom.m'), 'w');
  w = @(varargin) fprintf(fid, varargin{:});
  w('function W = b2_donatello_rom() %%#codegen\n');
  w('%%B2_DONATELLO_ROM  Pesi Donatello baked (letterali). GENERATO da gen_b2_rom.\n');
  % pesi baked come fi (tipo che il datapath usa: fc/U/Wout=T.w Q2.13; Vr=T.acc Q5.13;
  % bth/tj=T.V Q5.13) -> niente cast float nel datapath. delays=double (solo indice).
  w('  W.fc = fi(%s, 1, 16, 13);\n',   mat2str(double(c.fc_weight), 17));
  w('  W.U = fi(%s, 1, 16, 13);\n',    mat2str(double(c.rec_U), 17));
  w('  W.Vr = fi(%s, 1, 19, 13);\n',   mat2str(double(c.rec_V), 17));
  w('  W.Wout = fi(%s, 1, 16, 13);\n', mat2str(double(c.readout), 17));
  w('  W.bth = fi(%s, 1, 19, 13);\n',  mat2str(double(c.base_threshold(:)), 17));
  w('  W.tj = fi(%s, 1, 19, 13);\n',   mat2str(max(double(c.thresh_jump(:)), 0), 17));
  w('  W.delays = %s;\n',              mat2str(double(c.delays), 17));
  w('  W.sh = %d;\n',                  round(log2(double(c.leak_div(1)))));
  % costanti normalize: xn = [x1*invS; x2*invV; (clamp(x3,-DV,DV)+DV)*inv2DV; x4*invVL]
  nrm = double(c.norm(:));  % [S V DV VL]
  w('  W.invS = fi(%.17g, 1, 24, 20);\n',   1 / nrm(1));
  w('  W.invV = fi(%.17g, 1, 24, 20);\n',   1 / nrm(2));
  w('  W.invVL = fi(%.17g, 1, 24, 20);\n',  1 / nrm(4));
  w('  W.inv2DV = fi(%.17g, 1, 24, 20);\n', 1 / (2 * nrm(3)));
  w('  W.DV = fi(%.17g, 1, 20, 13);\n',     nrm(3));
  w('end\n');
  fclose(fid);
  fprintf('scritto b2_donatello_rom.m (Donatello, rank=%d)\n', c.rank);
end
