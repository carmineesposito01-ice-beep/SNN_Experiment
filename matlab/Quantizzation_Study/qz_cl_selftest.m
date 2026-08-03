function qz_cl_selftest()
%QZ_CL_SELFTEST  [Quantizzation_Study] Fumo dell'anello fedele qz_cl_sim (checkpoint 2, MATLAB-only):
%  (A) teletrasporto cut_in: gap alla soglia == new_gap;
%  (B) rilevatore collisione PROVATO NEI DUE SENSI: scatta su un caso sintetico inevitabile, NON su following;
%  (C) oracolo (params veri) sui 9 scenari: SSM sensate.
%  NON e' il cancello di parita' vs Python (passo successivo) — e' la prova che l'anello e' vivo e coerente.
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories;

  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1), x(2), x(3), x(4), gtp(:), rst, acc_types('double'))));

  % (A) teletrasporto cut_in
  i = find(cellfun(@(x) strcmp(x.name,'cut_in'), tr), 1); t = tr{i};
  o = qz_cl_sim(t, oracle(t.gt_params)); kc = t.cut_in(1);
  assert(kc <= o.N && abs(o.series.s(kc) - t.cut_in(2)) < 1e-9, 'cut_in NON teletrasportato');
  fprintf('(A) cut_in: gap al passo %d = %.4f == new_gap %.4f  OK\n', kc, o.series.s(kc), t.cut_in(2));

  % (B) rilevatore collisione nei due sensi
  hard = struct('v_leader',zeros(1,300),'s_init',2.0,'v_init',30.0,'gt_params',t.gt_params,'cut_in',[]);
  oh = qz_cl_sim(hard, oracle(t.gt_params));
  assert(oh.collided, 'collisione NON rilevata su caso inevitabile');
  soft = tr{find(cellfun(@(x) strcmp(x.name,'following'), tr),1)};
  os = qz_cl_sim(soft, oracle(soft.gt_params));
  assert(~os.collided, 'collisione FALSA su following');
  fprintf('(B) collisione: inevitabile->%d (atteso 1), following->%d (atteso 0)  OK\n', oh.collided, os.collided);

  % (C) oracolo sui 9 scenari
  names = {'following','stop_and_go','hard_brake','cut_in','sinusoidal','cut_out','static_target','panic_stop','aggressive_cut_in'};
  fprintf('\n(C) ORACOLO (params veri) sui 9 scenari — 1 estrazione ciascuno:\n');
  fprintf('%-18s coll  min_gap  min_TTC  max_DRAC  brake_marg\n', 'scenario');
  for c = 1:numel(names)
    i = find(cellfun(@(x) strcmp(x.name,names{c}), tr), 1); t = tr{i};
    o = qz_cl_sim(t, oracle(t.gt_params));
    m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
    fprintf('%-18s %3d %8.3f %8.3f %9.3f %11.3f\n', names{c}, m.collided, m.min_gap, m.min_ttc, m.max_DRAC, m.brake_margin_min);
  end
  fprintf('\nself-test anello: PASSATO\n');
end
