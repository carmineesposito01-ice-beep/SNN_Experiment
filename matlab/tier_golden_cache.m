function [P, meta] = tier_golden_cache(trajList, force)
%TIER_GOLDEN_CACHE  Golden del blocco Donatello_Tier@BALANCED calcolato UNA VOLTA e riusato: la stessa cache
%  alimenta l'export dei vettori RTL e le metriche -> i due si riferiscono agli STESSI identici dati.
%  Salva golden_tier_bal.mat accanto a questo file, con la CONFIGURAZIONE misurata (tracciabilita').
%  force=true ricalcola ignorando la cache. Ritorna P{i} = Ni x 5 (double) e meta (config + latenza).
  if nargin<1 || isempty(trajList), trajList = 1:60; end
  if nargin<2 || isempty(force),    force = false;  end
  here  = fileparts(mfilename('fullpath'));
  cfile = fullfile(here, 'golden_tier_bal.mat');
  cfg = struct('block','Donatello_Tier', 'tier','BALANCED', 'nfrac_param',13, ...
               'hold',500, 'nfrac_in',20, 'dataset','test_dataset.mat');
  if ~force && exist(cfile,'file')
    S = load(cfile);
    if isequal(S.meta.cfg, cfg) && all(ismember(trajList, S.meta.trajList))
      [~, loc] = ismember(trajList, S.meta.trajList);
      P = S.P(loc); meta = S.meta; meta.trajList = trajList; meta.fromCache = true;
      fprintf('tier_golden_cache: cache HIT (%d traj) <- %s\n', numel(trajList), cfile);
      return
    end
    fprintf('tier_golden_cache: cache MISS (config o traiettorie diverse) -> ricalcolo\n');
  end
  t0 = tic;
  [P, lat] = tier_block_params(trajList, cfg.hold, cfg.nfrac_in);
  meta = struct('cfg',cfg, 'trajList',trajList, 'lat',lat, 'secs',toc(t0), ...
                'built', char(datetime('now','Format','yyyy-MM-dd HH:mm:ss')), 'fromCache',false);
  save(cfile, 'P', 'meta');
  fprintf('tier_golden_cache: calcolato %d traj in %.1f min (lat=%d) -> %s\n', ...
          numel(trajList), meta.secs/60, lat, cfile);
end
