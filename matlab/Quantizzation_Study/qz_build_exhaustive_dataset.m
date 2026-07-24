function qz_build_exhaustive_dataset()
%QZ_BUILD_EXHAUSTIVE_DATASET  [Quantizzation_Study] Assembla test_dataset_exhaustive.mat dal JSON
%  prodotto da gen_exhaustive_qz_dataset.py (generatore CANONICO del Simulator, build_scenarios).
%  Schema di ogni trajectories{i} (cell-of-struct, come la convenzione tr{i}.campo):
%     name      char            nome scenario (following, cut_in, panic_stop, ...)
%     regime    char            regime dei params (highway/urban/truck/mixed)
%     v_leader  [1xN] double     profilo velocita' leader
%     s_init    scalar           gap iniziale
%     v_init    scalar           velocita' ego iniziale
%     gt_params [1x5] double     v0,T,s0,a,b (i label che la rete deve stimare)
%     cut_in    [] | [k new_gap] evento teletrasporto: al passo k (1-based) il gap crolla a new_gap
%  NB off-by-one: il JSON porta t_cut 0-based (indice Python in v_leader[0..N-1]); qui -> k=t0+1 (1-based),
%  coerente con simulate() dove il reset avviene all'INIZIO del passo t (== passo MATLAB t+1).
  here = fileparts(mfilename('fullpath'));
  txt  = fileread(fullfile(here, 'exhaustive_scenarios.json'));
  d    = jsondecode(txt);
  raw  = d.trajectories;
  if iscell(raw), items = raw; else, items = num2cell(raw); end
  n = numel(items);
  trajectories = cell(1, n);
  for i = 1:n
    t  = items{i};
    ci = t.cut_in;
    if isempty(ci)
      cut = [];
    else
      cut = [double(ci(1)) + 1, double(ci(2))];   % 0-based Python -> 1-based MATLAB step
    end
    trajectories{i} = struct( ...
      'name',      char(string(t.name)), ...
      'regime',    char(string(t.regime)), ...
      'v_leader',  double(t.v_leader(:)).', ...
      's_init',    double(t.s_init), ...
      'v_init',    double(t.v_init), ...
      'gt_params', double(t.gt_params(:)).', ...
      'cut_in',    cut);
  end
  meta = d.meta;
  save(fullfile(here, 'test_dataset_exhaustive.mat'), 'trajectories', 'meta', '-v7');
  fprintf('scritto test_dataset_exhaustive.mat: %d traiettorie, N=%d\n', n, meta.N);
  names = cellfun(@(x) x.name, trajectories, 'UniformOutput', false);
  ncut  = sum(cellfun(@(x) ~isempty(x.cut_in), trajectories));
  u = unique(names);
  for k = 1:numel(u), fprintf('  %-18s %d\n', u{k}, sum(strcmp(names, u{k}))); end
  fprintf('traiettorie con evento cut-in: %d/%d\n', ncut, n);
end
