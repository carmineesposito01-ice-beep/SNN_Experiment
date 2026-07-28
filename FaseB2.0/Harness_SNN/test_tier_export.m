function test_tier_export()
%TEST_TIER_EXPORT  Le .mem rileggono ESATTAMENTE i valori dell'oracolo? (round-trip storedInteger)
  here = fileparts(mfilename('fullpath')); addpath(fullfile(here,'..','..','matlab'));
  outdir = fullfile(tempdir,'tier_export_test'); if exist(outdir,'dir'), rmdir(outdir,'s'); end; mkdir(outdir);
  trajList = [1 33];
  tier_export_vectors(trajList, 'rt', outdir);
  m = load(fullfile(outdir,'meta_rt.mat'));
  stim = readmem(fullfile(outdir,'stim_rt.mem')); gold = readmem(fullfile(outdir,'gold_rt.mem'));
  assert(numel(stim)==m.K*4, 'stim: %d parole, atteso %d', numel(stim), m.K*4);
  assert(numel(gold)==m.K*5, 'gold: %d parole, atteso %d', numel(gold), m.K*5);
  P = tier_block_params(trajList(1), 500); p = P{1}(1,:); Tp = numerictype(1,21,13);
  for i=1:5
    exp_i = bitand(typecast(int32(storedInteger(fi(p(i),Tp))),'uint32'), uint32(2^21-1));
    assert(gold(i)==exp_i, 'gold param %d: file=%X atteso=%X', i, gold(i), exp_i);
  end
  fprintf('=== TEST_TIER_EXPORT PASSATO: %d control-step, round-trip bit-exact ===\n', m.K);
end
function w = readmem(f)
  t = strsplit(strtrim(fileread(f))); w = uint32(hex2dec(t(~cellfun(@isempty,t))));
end
