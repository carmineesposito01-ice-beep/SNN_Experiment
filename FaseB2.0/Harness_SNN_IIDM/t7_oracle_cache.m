function O = t7_oracle_cache(idx, force)
%T7_ORACLE_CACHE  Oracolo (controllore IDEALE, IIDM analitico coi parametri veri) sugli scenari richiesti,
%  calcolato UNA VOLTA e messo in cache. Serve a due cose distinte:
%    1. la sequenza `accel` di riferimento con cui PLANT-PAR pilota il plant SENZA DUT;
%    2. la baseline di qualita' contro cui si confrontano le metriche dell'RTL.
%
%  ⚠️ NON produce piu' un "golden" del blocco. Il riferimento del DUT e' il BLOCCO STESSO, pilotato dopo
%     la run RTL sugli ingressi effettivamente ricevuti (t7_block_replay). Il precedente golden basato su
%     `acciidm_m_traj` e' stato RIMOSSO: e' l'estrazione del monolite DEPRECATO e NON e' equivalente al
%     composto (385 scarti su 600 control-step, misurato il 2026-07-30).
%
%  La cache memorizza la CONFIGURAZIONE misurata: se cambia un solo campo si ricalcola.
  if nargin < 1 || isempty(idx),   idx = 1:99;    end
  if nargin < 2 || isempty(force), force = false; end
  here = fileparts(mfilename('fullpath'));
  root = fileparts(fileparts(here));
  ml   = fullfile(root,'matlab');
  addpath(ml, fullfile(ml,'Quantizzation_Study'), here);

  cfg = struct('kind','oracle', 'controller','acc_iidm_open(double)+gt_params', ...
               'dataset','test_dataset_exhaustive.mat', 'idx',idx(:).');
  resdir = fullfile(here,'results');
  if ~isfolder(resdir), mkdir(resdir); end
  cache = fullfile(resdir,'oracle_t7.mat');

  if ~force && isfile(cache)
    S = load(cache);
    if isfield(S,'cfg') && isequal(S.cfg, cfg)
      fprintf('t7_oracle_cache: HIT (%d scenari)\n', numel(idx)); O = S.O; return;
    end
    fprintf('t7_oracle_cache: MISS (configurazione diversa) -> ricalcolo\n');
  end

  ds = load(fullfile(ml,'Quantizzation_Study','test_dataset_exhaustive.mat'));
  tr = ds.trajectories;
  O = cell(numel(idx),1);
  t0 = tic;
  for i = 1:numel(idx)
    t = tr{idx(i)};
    O{i} = qz_cl_sim(t, t7_step_oracle(t.gt_params));
    fprintf('  [%3d/%3d] scen %2d %-18s | oracolo N=%3d coll=%d min_gap=%8.3f | %5.1f s\n', ...
            i, numel(idx), idx(i), char(string(t.name)), ...
            O{i}.N, O{i}.collided, O{i}.min_gap, toc(t0));
  end
  save(cache, 'O', 'cfg', '-v7.3');
  fprintf('t7_oracle_cache: salvato %s (%d scenari, %.1f s)\n', cache, numel(idx), toc(t0));
end
