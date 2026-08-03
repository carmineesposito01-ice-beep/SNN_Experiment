function gen_tanh_lut()
%GEN_TANH_LUT  [B2.0-2b] Genera le LUT del tanh (bit-exact per costruzione, memoizzano il tanh nativo):
%   - tanh_lut_full.m   (A1): LUT PIENA 4096 su x in [-8,8) @ En8, sfix19_En17. Lookup diretto -> bit-exact.
%   - tanh_lut_interp.m (A2a): LUT 256 celle (257 nodi) su [-8,8] + interpolazione lineare -> approssimato.
%  Tabelle come LITERAL int32 (bit di sfix19_En17) + reinterpretcast: HDL-safe (niente tanh runtime, niente
%  coder.const che HDL Coder rifiuta). Indirizzo = storedInteger(dd)+offset.
  here = fileparts(mfilename('fullpath'));

  % ---- A1: LUT piena 4096 (lookup diretto, bit-exact) ----
  s   = (-2048:2047).';
  xf  = fi(double(s)/256, 1, 19, 8);
  vf  = double(storedInteger(fi(tanh(xf), 1, 19, 17)));
  fid = fopen(fullfile(here,'tanh_lut_full.m'),'w');
  fprintf(fid, 'function th = tanh_lut_full(dd) %%#codegen\n');
  fprintf(fid, '%% [B2.0-2b A1] tanh via LUT PIENA bit-exact: memoizza tanh(fi(x,1,19,8)) su [-8,8),\n');
  fprintf(fid, '%%  saturazione oltre. th: sfix19_En17. GENERATO da gen_tanh_lut.m -- NON modificare a mano.\n');
  fprintf(fid, '  persistent TBL\n  if isempty(TBL)\n    TBL = int32([ ...\n');
  fprintf(fid, '      %d\n', vf);
  fprintf(fid, '    ]);\n  end\n');
  fprintf(fid, '  si = int32(storedInteger(dd));\n');
  fprintf(fid, '  if si < int32(-2048)\n    a = int32(1);\n  elseif si > int32(2047)\n    a = int32(4096);\n  else\n    a = si + int32(2049);\n  end\n');
  fprintf(fid, '  th = reinterpretcast(fi(TBL(a), 1, 19, 0), numerictype(1,19,17));\n');
  fprintf(fid, 'end\n');
  fclose(fid);

  % ---- A2a: LUT 256 celle + interpolazione lineare (257 nodi ai bordi delle celle) ----
  kn  = (0:256).';
  xn  = fi(-8 + double(kn)*(16/256), 1, 19, 8);        % nodi @ En8 (16/256 = 1/16, esatto)
  vn  = double(storedInteger(fi(tanh(xn), 1, 19, 17)));
  fid = fopen(fullfile(here,'tanh_lut_interp.m'),'w');
  fprintf(fid, 'function th = tanh_lut_interp(dd) %%#codegen\n');
  fprintf(fid, '%% [B2.0-2b A2a] tanh via LUT PICCOLA (256 celle) + interp lineare su [-8,8). Approssimato.\n');
  fprintf(fid, '%%  GENERATO da gen_tanh_lut.m -- NON modificare a mano. th: sfix19_En17.\n');
  fprintf(fid, '  persistent TBL\n  if isempty(TBL)\n    TBL = int32([ ...\n');
  fprintf(fid, '      %d\n', vn);
  fprintf(fid, '    ]);\n  end\n');
  fprintf(fid, '  si = int32(storedInteger(dd)) + int32(2048);\n');
  fprintf(fid, '  if si < int32(0),    si = int32(0);    end\n');
  fprintf(fid, '  if si > int32(4095), si = int32(4095); end\n');
  fprintf(fid, '  node = bitshift(si, -4);\n  frac = si - bitshift(node, 4);\n');
  fprintf(fid, '  a = reinterpretcast(fi(TBL(node+1), 1, 19, 0), numerictype(1,19,17));\n');
  fprintf(fid, '  b = reinterpretcast(fi(TBL(node+2), 1, 19, 0), numerictype(1,19,17));\n');
  fprintf(fid, '  th = fi(a + bitsra((b - a) * fi(frac, 0, 6, 0), 4), 1, 19, 17);   %% interp = a + (b-a)*frac/16 (shift, no double)\n');
  fprintf(fid, 'end\n');
  fclose(fid);

  fprintf('scritto tanh_lut_full.m (%d entry) + tanh_lut_interp.m (%d nodi)\n', numel(vf), numel(vn));
end
