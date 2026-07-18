function gen_tanh_lut()
%GEN_TANH_LUT  [B2.0-2b A1] Genera tanh_lut_full.m: LUT PIENA 4096 = tanh(fi(x,1,19,8)) su x in [-8,8),
%  sfix19_En17. Bit-exact per costruzione (memoizza lo STESSO tanh nativo). Indirizzo = storedInteger(dd)
%  + 2049 (1-based); saturazione oltre ±8 (tanh piatto in En17 -> costanti alle estremita').
  here = fileparts(mfilename('fullpath'));
  s   = (-2048:2047).';                     % storedInteger di dd in [-8,8) @ En8
  x   = fi(double(s)/256, 1, 19, 8);        % ricostruisci dd (En8, esatto)
  th  = fi(tanh(x), 1, 19, 17);             % tanh nativo -> sfix19_En17
  vals = double(storedInteger(th));         % 4096 interi = i bit di sfix19_En17
  fid = fopen(fullfile(here,'tanh_lut_full.m'),'w');
  fprintf(fid, 'function th = tanh_lut_full(dd) %%#codegen\n');
  fprintf(fid, '%% [B2.0-2b A1] tanh via LUT PIENA bit-exact: memoizza tanh(fi(x,1,19,8)) su [-8,8),\n');
  fprintf(fid, '%%  saturazione oltre. th: sfix19_En17. GENERATO da gen_tanh_lut.m -- NON modificare a mano.\n');
  fprintf(fid, '  persistent TBL\n');
  fprintf(fid, '  if isempty(TBL)\n');
  fprintf(fid, '    TBL = int32([ ...\n');
  fprintf(fid, '      %d\n', vals);         % 4096 valori, uno per riga -> colonna
  fprintf(fid, '    ]);\n');
  fprintf(fid, '  end\n');
  fprintf(fid, '  si = int32(storedInteger(dd));       %% dd*2^8, intero\n');
  fprintf(fid, '  if si < int32(-2048)\n    a = int32(1);\n');
  fprintf(fid, '  elseif si > int32(2047)\n    a = int32(4096);\n');
  fprintf(fid, '  else\n    a = si + int32(2049);\n  end\n');
  fprintf(fid, '  raw = fi(TBL(a), 1, 19, 0);\n');
  fprintf(fid, '  th  = reinterpretcast(raw, numerictype(1,19,17));\n');
  fprintf(fid, 'end\n');
  fclose(fid);
  fprintf('scritto tanh_lut_full.m (%d entry)\n', numel(vals));
end
