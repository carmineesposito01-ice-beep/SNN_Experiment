function gen_ann_rom()
%GEN_ANN_ROM  Genera ann_rom.m con pesi ANN densa random-in-range baked (fi). La potenza dipende
%  dallo switching, non dall'accuratezza: pesi rappresentativi in [-1,1], deterministici (seed fisso).
  here = fileparts(mfilename('fullpath'));
  rng(42);                                    % deterministico
  W1 = 2*rand(32, 4)  - 1;                     % input fc 4->32
  Wh = 2*rand(32, 32) - 1;                     % hidden denso 32->32 (equivalente alla ricorrenza)
  Wo = 2*rand(5, 32)  - 1;                     % out 32->5
  fid = fopen(fullfile(here, 'ann_rom.m'), 'w');
  w = @(varargin) fprintf(fid, varargin{:});
  w('function A = ann_rom() %%#codegen\n');
  w('%%ANN_ROM  Pesi ANN densa random-in-range baked. GENERATO da gen_ann_rom.\n');
  w('  A.W1 = fi(%s, 1, 18, 13);\n', mat2str(W1, 17));
  w('  A.Wh = fi(%s, 1, 18, 13);\n', mat2str(Wh, 17));
  w('  A.Wo = fi(%s, 1, 18, 13);\n', mat2str(Wo, 17));
  w('end\n');
  fclose(fid);
  fprintf('scritto ann_rom.m (4->32->32->5, %d MAC/inf)\n', 4*32 + 32*32 + 32*5);
end
