function [G, O] = t7_golden_cache(idx, force)
%T7_GOLDEN_CACHE  Golden (blocco) e Oracolo sugli scenari richiesti, calcolati UNA VOLTA e messi in cache.
%
%  Requisito di metodo (Fase B2.0 §Requisiti 2): prova e metriche devono consumare lo STESSO golden.
%  Popolazioni diverse rendono i numeri non appaiabili e lo scostamento illeggibile, anche quando e' 0.
%
%  La cache memorizza la CONFIGURAZIONE MISURATA: se cambia anche un solo campo si ricalcola. Una cache
%  che non controlla la configurazione restituisce numeri di un'altra prova, e sembrano buoni.
%
%  idx   : indici degli scenari in test_dataset_exhaustive.mat (default 1:99)
%  force : true per ignorare la cache
%  G, O  : cell{numel(idx)} di output qz_cl_sim -- G = blocco, O = oracolo
  if nargin < 1 || isempty(idx),   idx = 1:99;   end
  if nargin < 2 || isempty(force), force = false; end
  here = fileparts(mfilename('fullpath'));
  root = fileparts(fileparts(here));
  ml   = fullfile(root,'matlab');
  addpath(ml, fullfile(ml,'Quantizzation_Study'), here);

  cfg = struct('block','Donatello_SNN_IIDM', 'tier','BALANCED', 'nfrac',13, ...
               'hold_g',500, 'round','Floor', 'in_type','fixdt(1,32,20)', ...
               'dataset','test_dataset_exhaustive.mat', 'idx',idx(:).');
  resdir = fullfile(here,'results');
  if ~isfolder(resdir), mkdir(resdir); end
  cache = fullfile(resdir,'golden_t7.mat');

  if ~force && isfile(cache)
    S = load(cache);
    if isfield(S,'cfg') && isequal(S.cfg, cfg)
      fprintf('t7_golden_cache: HIT (%d scenari)\n', numel(idx));
      G = S.G; O = S.O; return;
    end
    fprintf('t7_golden_cache: MISS (configurazione diversa) -> ricalcolo\n');
  end

  if ~bdIsLoaded('snn_champions_lib'), load_system(fullfile(ml,'snn_champions_lib.slx')); end
  build_acciidm_m_golden();
  ds = load(fullfile(ml,'Quantizzation_Study','test_dataset_exhaustive.mat'));
  tr = ds.trajectories;
  G = cell(numel(idx),1); O = cell(numel(idx),1);
  t0 = tic;
  for i = 1:numel(idx)
    t = tr{idx(i)};
    G{i} = qz_cl_sim(t, t7_step_block());
    O{i} = qz_cl_sim(t, t7_step_oracle(t.gt_params));
    fprintf('  [%3d/%3d] scen %2d %-18s | golden N=%3d coll=%d min_gap=%8.3f | oracolo N=%3d coll=%d min_gap=%8.3f | %6.1f s\n', ...
            i, numel(idx), idx(i), char(string(t.name)), ...
            G{i}.N, G{i}.collided, G{i}.min_gap, O{i}.N, O{i}.collided, O{i}.min_gap, toc(t0));
  end
  save(cache, 'G', 'O', 'cfg', '-v7.3');
  fprintf('t7_golden_cache: salvato %s (%d scenari, %.1f min)\n', cache, numel(idx), toc(t0)/60);
end
