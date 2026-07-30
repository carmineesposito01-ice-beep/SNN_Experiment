function out = t7_series_to_mat(workdir, O, idx, outfile)
%T7_SERIES_TO_MAT  Impacchetta per il motore Python: serie dell'RTL (sorgente dei numeri riportati) e
%  serie dell'ORACOLO (baseline di qualita'), nello stesso file.
%
%  Le NOVE chiavi richieste da all_metrics vengono scritte TUTTE ed ESPLICITAMENTE:
%    s, v, vl, dv, a_ego, params, collided, min_gap, impact_dv
%  ⚠️ `impact_dv` ha un DEFAULT SILENZIOSO nel motore (`traj.get('impact_dv', 0.0)`): ometterla non da'
%     errore, restituisce 0 — cioe' "collisione a severita' nulla" per una collisione reale. Misurato su
%     aggressive_cut_in, il valore vero e' 5,39 m/s. L'asserzione sta in t7_metrics.py.
%
%  min_gap segue la stessa regola di qz_cl_sim (riga 33): se collide e' il gap FINALE (negativo),
%  altrimenti il minimo della serie. Riprodurla qui e' necessario perche' le serie RTL vengono dal TB,
%  non da qz_cl_sim.
  RTL = struct('name',{},'s',{},'v',{},'vl',{},'dv',{},'a_ego',{},'params',{}, ...
               'collided',{},'min_gap',{},'impact_dv',{});
  ORA = RTL;
  for i = 1:numel(idx)
    R = t7_read_series(fullfile(workdir, sprintf('ser_%d.txt', i)));
    n = R.N;
    if R.collided, mg = R.s_end; else, mg = min(R.s(1:n)); end
    RTL(i) = pack(sprintf('scen_%d', idx(i)), R.s(1:n), R.v(1:n), R.vl(1:n), R.dv(1:n), ...
                  R.a(1:n), R.params(1:n,:), R.collided, mg, R.impact_dv);
    o = O{i};
    ORA(i) = pack(sprintf('scen_%d', idx(i)), o.series.s, o.series.v, o.series.vl, o.series.dv, ...
                  o.series.a, o.params, o.collided, o.min_gap, o.impact_dv);
  end
  save(outfile, 'RTL', 'ORA', '-v7');        % -v7: leggibile da scipy.io.loadmat
  out = outfile;
  fprintf('t7_series_to_mat: %d scenari (RTL + oracolo) -> %s\n', numel(idx), outfile);
end

function e = pack(name, s, v, vl, dv, a, p, coll, mg, idv)
  n = numel(s);
  assert(all([numel(v) numel(vl) numel(dv) numel(a)] == n), ...
         '%s: serie di lunghezze diverse', name);
  assert(size(p,1) == n && size(p,2) == 5, ...
         '%s: params %s invece di [%d 5]', name, mat2str(size(p)), n);
  e = struct('name',name,'s',s(:).','v',v(:).','vl',vl(:).','dv',dv(:).', ...
             'a_ego',a(:).','params',p,'collided',double(coll), ...
             'min_gap',double(mg),'impact_dv',double(idv));
end
