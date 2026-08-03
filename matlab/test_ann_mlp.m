function test_ann_mlp()
%TEST_ANN_MLP  Sanity/determinismo della FSM ANN: valid dopo ~1312 cicli, uscita finita.
  here = fileparts(mfilename('fullpath')); addpath(here);
  if ~isfile(fullfile(here, 'ann_rom.m')); gen_ann_rom(); end
  clear ann_mlp;                                       % reset stato persistent
  xn = fi([0.6; 0.3; 0.05; 0.3], 1, 19, 13);
  [~, ~] = ann_mlp(xn, true);                          % start (setup)
  v = false; c = 0;
  while ~v && c < 5000
    [o, v] = ann_mlp(xn, false);
    c = c + 1;
  end
  assert(v, 'valid mai asserito entro 5000 cicli');
  assert(all(isfinite(double(o))), 'uscita non finita');
  fprintf('TEST_ANN_MLP OK: cicli=%d (atteso ~1312), out=%s\n', c, mat2str(double(o)', 4));
end
