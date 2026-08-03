function test_rtl_export()
%TEST_RTL_EXPORT  Le .mem rileggono ESATTAMENTE i valori di riferimento? (round-trip storedInteger)
  here = fileparts(mfilename('fullpath'));
  outdir = fullfile(tempdir,'rtl_export_test'); if exist(outdir,'dir'), rmdir(outdir,'s'); end; mkdir(outdir);
  trajList = [1 7];
  build_champion_golden();                                    % golden fedele al blocco
  rtl_export_vectors('snn', trajList, 'rt', outdir);
  m    = load(fullfile(outdir,'meta_rt.mat'));                 % K, trajList
  stim = readmem(fullfile(outdir,'stim_rt.mem'));
  gold = readmem(fullfile(outdir,'gold_rt.mem'));
  assert(numel(stim)==m.K*4, 'stim: %d parole, atteso %d', numel(stim), m.K*4);
  assert(numel(gold)==m.K*5, 'gold: %d parole, atteso %d', numel(gold), m.K*5);

  % ricalcola stim+gold del PRIMO control-step della prima traiettoria e confronta col file
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  cc = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),ch),1));
  W  = champ_weights(cc); Tp = numerictype(1,21,13);
  val = fi(double(tr{trajList(1)}.val),1,32,20);
  for j = 1:4
    exp_s = typecast(int32(storedInteger(val(j,1))),'uint32');
    assert(stim(j)==exp_s, 'stim ingresso %d: file=%08X atteso=%08X', j, stim(j), exp_s);
  end
  clear snn_traj_champion_mex; P = snn_traj_champion_mex(tr{trajList(1)}.val, 500);   % golden fedele
  for i = 1:5
    exp_i = bitand(typecast(int32(storedInteger(fi(P(1,i),Tp))),'uint32'), uint32(2^21-1));
    assert(gold(i)==exp_i, 'gold param %d: file=%06X atteso=%06X', i, gold(i), exp_i);
  end
  fprintf('=== TEST_RTL_EXPORT PASSATO: %d control-step, round-trip stim+gold bit-exact ===\n', m.K);
end

function w = readmem(f)
  t = strsplit(strtrim(fileread(f)));
  w = uint32(hex2dec(t(~cellfun(@isempty,t))));
end
