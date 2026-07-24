function qz_cl_validate(levels, trajList)
%QZ_CL_VALIDATE  [Quantizzation_Study] Car-following in ANELLO CHIUSO per ciascun nfrac candidato.
%  Costruisce i MEX qz_snn_cl_step_n<f>_mex (uno per livello), gira l'anello sul set di traiettorie
%  (copia fedele di cl_matlab in run_block_closed_loop_test), e confronta il gap col riferimento
%  full-precision nfrac=13 (il blocco deployato). Metrica sul dataset: max|Δgap|, RMSE, collisioni.
%  Risponde a: "l'errore sui parametri a nfrac<13 degrada il controllo REALE?" (max|d| e' conservativo).
  if nargin < 1 || isempty(levels),   levels   = [11 12 13]; end
  if nargin < 2 || isempty(trajList), trajList = 1:20; end     % sottoinsieme; alzare a 1:60 per il dataset intero
  here  = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  addpath(mroot);   % snn_core, snn_normalize, snn_decode_lut, acc_iidm_open, acc_types, champ_weights

  dd = load(fullfile(mroot, 'champions_export.mat')); ch = dd.champions; if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1)); W = champ_weights(c);

  % 1) MEX per ogni livello (se manca)
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here);   cleanup = onCleanup(@() cd(oldd)); %#ok<NASGU>   % genera dentro Quantizzation_Study/
  for f = levels
    mexname = sprintf('qz_snn_cl_step_n%d_mex', f);
    if isempty(which(mexname))
      fprintf('build %s ...\n', mexname);
      codegen('qz_snn_cl_step', '-config', cfg, ...
              '-args', {zeros(4,1), coder.typeof(W), true, coder.Constant(f)}, ...
              '-o', mexname, '-d', ['codegen_n' num2str(f)]);
    end
  end

  % 2) anello per ogni livello e traiettoria
  ds = load(fullfile(mroot, 'test_dataset.mat')); tr = ds.trajectories;
  K = 200;
  gaps = containers.Map('KeyType', 'double', 'ValueType', 'any');
  for f = levels
    mexname = sprintf('qz_snn_cl_step_n%d_mex', f);
    fun = str2func(mexname);
    allg = cell(1, numel(trajList));
    for i = 1:numel(trajList)
      clear(mexname);                                  % azzera lo stato del MEX fra traiettorie (come cl_matlab)
      allg{i} = qz_cl_run(tr{trajList(i)}, W, K, fun, f);
    end
    gaps(f) = allg;
    fprintf('livello nfrac=%d: anello su %d traiettorie -> fatto\n', f, numel(trajList));
  end

  % 3) confronto vs 13 (riferimento full-precision deployato)
  assert(isKey(gaps, 13), 'serve nfrac=13 fra i livelli come riferimento');
  ref = gaps(13);
  fprintf('\nnfrac | max|Δgap| vs13 [m] | RMSE gap [m] | collisioni(gap<=0) | min gap [m]\n');
  fprintf('%s\n', repmat('-', 1, 72));
  for f = levels
    cur = gaps(f); dg = 0; se = 0; ns = 0; coll = 0; mng = inf;
    for i = 1:numel(cur)
      g = cur{i}; r = ref{i}; n = min(numel(g), numel(r));
      dg  = max(dg, max(abs(g(1:n) - r(1:n))));
      se  = se + sum((g(1:n) - r(1:n)).^2); ns = ns + n;
      coll = coll + sum(g <= 0); mng = min(mng, min(g));
    end
    fprintf('%5d | %17.4g | %12.4g | %18d | %.3f\n', f, dg, sqrt(se/ns), coll, mng);
  end
  fprintf('\n(Δgap vs 13 trascurabile e collisioni=0 => il livello e'' usabile in car-following)\n');
end


function g = qz_cl_run(t, W, K, fun, nfrac)
% UN anello chiuso su una traiettoria; ritorna il gap s(k). Copia fedele di cl_setup + cl_matlab
% (run_block_closed_loop_test), con nfrac fornito dal MEX `fun`. dvMode = 'train' (convenzione d'addestramento).
% nfrac va ripassato al MEX: con coder.Constant la MEX function esige comunque quell'argomento (== costante).
  val = double(t.val); gt = double(t.gt_params); K = min(K, size(val, 2));
  DT = 0.1; S_MAX = 150; s_lo = 0.5 * gt(3); v_cap = 1.2 * gt(1); xe0 = -val(1,1); ve0 = val(2,1);
  vl = val(4, 1:K).'; xl = zeros(K, 1); for k = 2:K, xl(k) = xl(k-1) + vl(k) * DT; end
  q = @(x) floor(x * 2^20) / 2^20;                    % Data Type Conversion a fixdt(1,32,20), RndMeth 'Floor'
  xe = xe0; ve = ve0; ve_prev = ve0; g = zeros(K, 1);
  for k = 1:K
    s   = min(max(xl(k) - xe, s_lo), S_MAX);
    dvk = ve_prev - vl(k);                             % 'train'
    xq  = [q(s); q(ve); q(dvk); q(vl(k))];
    [~, acc] = fun(xq, W, k == 1, nfrac);
    g(k)    = xq(1);
    xe_new  = xe + ve * DT;                            % balistico: v VECCHIA
    ve_new  = min(max(ve + acc * DT, 0), v_cap);
    ve_prev = ve; xe = xe_new; ve = ve_new;
  end
end
