function qz_cl_parity_gate()
%QZ_CL_PARITY_GATE  [Quantizzation_Study] CANCELLO-CHIAVE: prova che qz_cl_sim (port MATLAB) combacia col
%  motore canonico utils/closed_loop_eval.simulate() (Python) sull'ORACOLO. Confronta la serie del gap s(t)
%  passo-passo sui 9 scenari (estrazione params 0). Se max|Δs| e' al livello del float e i flag collided
%  coincidono, il port e' fedele (non solo "sembra giusto"). Riferimento: oracle_parity_ref.json.
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  ref = jsondecode(fileread(fullfile(here,'oracle_parity_ref.json'))).trajectories;
  ds  = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories;   % primi 9 = draw 0, stesso ordine
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1), x(2), x(3), x(4), gtp(:), rst, acc_types('double'))));
  fprintf('%-18s  N_ml N_py   max|ds|    coll ml/py   min_gap ml/py\n', 'scenario');
  worst = 0; okflags = true;
  for j = 1:numel(ref)
    r = ref(j); t = tr{j};
    assert(strcmp(t.name, char(string(r.name))), 'ordine ref/dataset disallineato');
    o = qz_cl_sim(t, oracle(t.gt_params));
    n = min(o.N, numel(r.s));
    dmax = max(abs(o.series.s(1:n) - r.s(1:n).'));
    worst = max(worst, dmax);
    okf = (o.collided == logical(r.collided));
    okflags = okflags && okf;
    fprintf('%-18s  %4d %4d   %.2e   %d/%d       %8.4f/%8.4f\n', ...
            char(string(r.name)), o.N, r.N, dmax, o.collided, r.collided, o.min_gap, r.min_gap);
  end
  fprintf('\nmax|Δs| su tutti gli scenari/step = %.3e ; flag collided coerenti: %d\n', worst, okflags);
  assert(worst < 1e-2 && okflags, 'PARITA'' FALLITA: il port MATLAB diverge dal simulate() canonico');
  fprintf('CANCELLO PARITA'' oracolo MATLAB vs Python: PASSATO (max|Δs|=%.2e m)\n', worst);
end
