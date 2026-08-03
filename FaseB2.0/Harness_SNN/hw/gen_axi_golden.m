function trajList = gen_axi_golden(trajList, nStep, outdir)
%GEN_AXI_GOLDEN  Stimoli + golden per la cosim AXI, dall'ORACOLO di T6a (il blocco stesso, via cache condivisa).
%  UN FILE PER TRAIETTORIA: stim_axi_<i>.mem / gold_axi_<i>.mem, perche' il runner rifa xsim per ogni traiettoria:
%  la hdl.RAM del Tier (stato SNN) si azzera SOLO all'init della simulazione (lezione T6a) -> concatenare piu'
%  traiettorie in una sola simulazione falserebbe il confronto dalla seconda in poi.
%  Default: TUTTE le 60 traiettorie x 1000 control-step = stesso perimetro di T6a (~1h in background).
  here = fileparts(mfilename('fullpath'));
  addpath(fullfile(here,'..'));                          % subset_diverse (non usato di default, utile per gate rapidi)
  addpath(fullfile(here,'..','..','..','matlab'));       % tier_golden_cache, test_dataset
  addpath(fullfile(here,'..','..','common'));            % rtl_write_vectors
  if nargin<1||isempty(trajList), trajList = 1:60; end
  if nargin<2||isempty(nStep),    nStep    = 1000; end
  if nargin<3||isempty(outdir),   outdir   = 'D:/zbd_tier_hw'; end
  ds = load(fullfile(here,'..','..','..','matlab','test_dataset.mat'));
  P  = tier_golden_cache(trajList);                       % stessa cache/oracolo di T6a
  for i = 1:numel(trajList)
    K = min(nStep, size(ds.trajectories{trajList(i)}.val,2));
    stim = fi(double(ds.trajectories{trajList(i)}.val(:,1:K)), 1, 32, 20);
    gold = fi(P{i}(1:K,:).', numerictype(1,21,13));
    rtl_write_vectors(outdir, sprintf('axi_%d', i), stim, 32, gold, 21);
  end
  save(fullfile(outdir,'meta_axi.mat'), 'trajList', 'nStep');
  fprintf('gen_axi_golden: %d traiettorie x %d control-step -> %s\n', numel(trajList), nStep, outdir);
end
