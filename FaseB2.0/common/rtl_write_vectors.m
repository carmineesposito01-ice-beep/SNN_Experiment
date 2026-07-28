function rtl_write_vectors(outdir, tag, stim, stimW, gold, goldW)
%RTL_WRITE_VECTORS  Scrive stim_<tag>.mem e gold_<tag>.mem da matrici fi (colonna = control-step). Generico T6/T7.
%  stim : nS x K fi (es. 4 x K, val fixdt(1,32,20)) -> stimW bit (nhex = ceil(stimW/4))
%  gold : nG x K fi (es. 5 x K param Q7.13 / 1 x K accel Q4.8) -> goldW bit
%  Valore = STORED INTEGER (compl. a 2) mascherato via typecast int32->uint32 (uint32 di negativo SATURA -> falsi mismatch).
  if ~exist(outdir,'dir'), mkdir(outdir); end
  K = size(stim,2); nS = size(stim,1); nG = size(gold,1);
  assert(size(gold,2)==K, 'stim/gold: K diverso (%d vs %d)', K, size(gold,2));
  fs = fopen(fullfile(outdir,['stim_' tag '.mem']),'w');
  fg = fopen(fullfile(outdir,['gold_' tag '.mem']),'w');
  fmtS = sprintf('%%0%dX\n', ceil(stimW/4)); fmtG = sprintf('%%0%dX\n', ceil(goldW/4));
  for k = 1:K
    for i=1:nS, fprintf(fs, fmtS, mask_hex(stim(i,k), stimW)); end
    for i=1:nG, fprintf(fg, fmtG, mask_hex(gold(i,k), goldW)); end
  end
  fclose(fs); fclose(fg);
  fprintf('rtl_write_vectors: %d control-step (stim %dx, gold %dx) -> %s\n', K, nS, nG, outdir);
end

function u = mask_hex(x_fi, nbit)
  u = bitand(typecast(int32(storedInteger(x_fi)),'uint32'), uint32(2^nbit-1));
end
