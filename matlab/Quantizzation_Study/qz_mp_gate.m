function out = qz_mp_gate(nf, trajList)
%QZ_MP_GATE  [Quantizzation_Study] Verdetto + cruscotto di una config per-campo nf, sull'intero dataset.
%  Cancello: max|Δgap| vs full-precision (tutti-13) <= 0.5 m  E  0 collisioni extra vs oracolo.
%  out: .maxdgap .coll_extra .pass  + cruscotto (.min_gap .brake_margin .max_DRAC .min_TTC .nrmse[1x5] .impact_max)
  THR = 0.5;   % soglia comportamentale [m] (spec §3)
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  if nargin < 2 || isempty(trajList), trajList = 1:99; end
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories; T = tr(trajList);

  fun = qz_mp_mex(nf, W);                       % MEX per nf (build-if-missing); vedi funzione locale

  % riferimento full-precision (cache): gap per traiettoria + params + baseline oracolo
  ref = qz_mp_ref13(here, W, T, trajList);      % struct con .gap{i} .P{i} .Bcoll (oracolo)

  nt = numel(T); maxdg = 0; coll = 0; mng = inf; bmn = inf; drmax = 0; ttcmin = inf;
  num = zeros(1,5); den = 0; impmax = 0;
  for i = 1:nt
    o = qz_cl_sim(T{i}, @(x,rst) fun(x, W, rst, nf));
    g = o.series.s; gr = ref.gap{i}; n = min(numel(g), numel(gr));
    maxdg = max(maxdg, max(abs(g(1:n) - gr(1:n))));
    m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
    if o.collided && ~ref.Bcoll(i), coll = coll + 1; end   % collisione EXTRA vs oracolo
    mng = min(mng, m.min_gap); bmn = min(bmn, m.brake_margin_min);
    drmax = max(drmax, m.max_DRAC); if isfinite(m.min_ttc), ttcmin = min(ttcmin, m.min_ttc); end
    if ref.Bcoll(i), impmax = max(impmax, m.impact_dv); end
    Pr = ref.P{i}; np = min(size(o.params,1), size(Pr,1));
    num = num + sum((o.params(1:np,:) - Pr(1:np,:)).^2, 1); den = den + np;
  end
  out = struct('nf', nf, 'maxdgap', maxdg, 'coll_extra', coll, ...
               'pass', (maxdg <= THR && coll == 0), ...
               'min_gap', mng, 'brake_margin', bmn, 'max_DRAC', drmax, 'min_TTC', ttcmin, ...
               'nrmse', sqrt(num/den) ./ ref.prng, 'impact_max', impmax);
end

function fun = qz_mp_mex(nf, W)
% build-if-missing del MEX di qz_snn_cl_step_mp per la tupla nf (coder.Constant)
  here = fileparts(mfilename('fullpath'));
  tag = sprintf('%d_', nf); tag = tag(1:end-1);
  mx = sprintf('qz_mp_step_%s_mex', tag);
  if isempty(which(mx))
    cfg = coder.config('mex'); cfg.GenerateReport = false; oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
    codegen('qz_snn_cl_step_mp', '-config', cfg, ...
            '-args', {zeros(4,1), coder.typeof(W), true, coder.Constant(double(nf))}, ...
            '-o', mx, '-d', ['codegen_mp_' tag]);
  end
  fun = str2func(mx);
end

function ref = qz_mp_ref13(here, W, T, trajList)
% riferimento full-precision (tutti-13): cache su file per non ricalcolarlo a ogni chiamata
  cf = fullfile(here, sprintf('mp_ref13_%d_%d.mat', trajList(1), trajList(end)));
  if isfile(cf), s = load(cf); ref = s.ref; return; end
  fun = qz_mp_mex([13 13 13 13 13 13], W);
  oracle = @(gtp) @(x,rst) deal(gtp(:), double(acc_iidm_open(x(1),x(2),x(3),x(4),gtp(:),rst,acc_types('double'))));
  nt = numel(T); gap = cell(1,nt); P = cell(1,nt); Bcoll = false(1,nt);
  for i = 1:nt
    o = qz_cl_sim(T{i}, @(x,rst) fun(x, W, rst, [13 13 13 13 13 13])); gap{i} = o.series.s; P{i} = o.params;
    oo = qz_cl_sim(T{i}, oracle(T{i}.gt_params)); Bcoll(i) = oo.collided;
  end
  allP = cell2mat(P(:)); prng = max(allP,[],1) - min(allP,[],1); prng(prng==0) = 1;
  ref = struct('gap', {gap}, 'P', {P}, 'Bcoll', Bcoll, 'prng', prng);
  save(cf, 'ref');
end
