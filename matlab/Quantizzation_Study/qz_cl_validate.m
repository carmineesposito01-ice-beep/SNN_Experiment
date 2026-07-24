function qz_cl_validate(levels, trajList)
%QZ_CL_VALIDATE  [Quantizzation_Study] Valutazione MULTI-VISTA della quantizzazione di Donatello in
%  ANELLO CHIUSO, su piu' nfrac e su tutto il dataset. Per ciascun livello:
%   - VISTA COMPORTAMENTO (gap): max|Δgap| e RMSE vs riferimento nfrac=13, collisioni (gap<=0), min gap.
%   - VISTA PARAMETRI (rete): NRMSE per-parametro (v0,T,s0,a,b) vs nfrac=13, normalizzata sul range del
%     parametro nel riferimento -> cattura gli "equilibri interni" (la rete e' probabilistica: i parametri
%     possono spostarsi pur mantenendo il car-following).
%  ⚠️ CAVEAT SICUREZZA: il dataset ha gap stretti (min 1.25 m) ma NON cut-in fisici (dec. leader artefatta,
%     ~-222 m/s^2). Quindi collisioni=0 e' necessario ma NON sufficiente: un vero stress cut-in richiede
%     scenari sintetici (leader che frena in modo graduale). Vedi qz_cutin_stress (future work).
  if nargin < 1 || isempty(levels),   levels   = [8 9 10 11 12 13]; end
  if nargin < 2 || isempty(trajList), trajList = 1:60; end
  here  = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  addpath(mroot);

  dd = load(fullfile(mroot, 'champions_export.mat')); ch = dd.champions; if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1)); W = champ_weights(c);

  % 1) MEX per ogni livello (se manca)
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here); cleanup = onCleanup(@() cd(oldd)); %#ok<NASGU>
  for f = levels
    mexname = sprintf('qz_snn_cl_step_n%d_mex', f);
    if isempty(which(mexname))
      fprintf('build %s ...\n', mexname);
      codegen('qz_snn_cl_step', '-config', cfg, ...
              '-args', {zeros(4,1), coder.typeof(W), true, coder.Constant(f)}, ...
              '-o', mexname, '-d', ['codegen_n' num2str(f)]);
    end
  end

  % 2) anello per ogni livello e traiettoria -> raccogli gap g e parametri P (K x 5)
  ds = load(fullfile(mroot, 'test_dataset.mat')); tr = ds.trajectories;
  K = 200;
  G = containers.Map('KeyType','double','ValueType','any');   % gap
  Pm = containers.Map('KeyType','double','ValueType','any');  % parametri
  for f = levels
    mexname = sprintf('qz_snn_cl_step_n%d_mex', f); fun = str2func(mexname);
    gg = cell(1, numel(trajList)); pp = cell(1, numel(trajList));
    for i = 1:numel(trajList)
      clear(mexname);
      [gg{i}, pp{i}] = qz_cl_run(tr{trajList(i)}, W, K, fun, f);
    end
    G(f) = gg; Pm(f) = pp;
    fprintf('livello nfrac=%d: anello su %d traiettorie -> fatto\n', f, numel(trajList));
  end

  % 3) riferimento full-precision = nfrac 13
  assert(isKey(G,13), 'serve nfrac=13 fra i livelli come riferimento');
  gref = G(13); pref = Pm(13);
  % range di ciascun parametro nel riferimento (per la normalizzazione NRMSE)
  allP = cell2mat(pref(:)); prng = max(allP,[],1) - min(allP,[],1); prng(prng==0) = 1;
  pnames = {'v0','T','s0','a','b'};

  fid = fopen(fullfile(here,'cl_sweep.tsv'),'w');
  fprintf(fid,'nfrac\tmaxdgap_m\trmse_gap_m\tcollisioni\tmin_gap_m\tNRMSE_v0\tNRMSE_T\tNRMSE_s0\tNRMSE_a\tNRMSE_b\tNRMSE_mean\n');
  fprintf('\n=== VISTA COMPORTAMENTO (gap, vs nfrac=13) + VISTA PARAMETRI (NRMSE per-parametro) ===\n');
  fprintf('nfrac | max|Δgap| | RMSE gap | colli | min gap || NRMSE  v0     T     s0     a     b   | mean\n');
  fprintf('%s\n', repmat('-',1,104));
  for f = levels
    cur = G(f); dg=0; se=0; ns=0; coll=0; mng=inf;
    for i=1:numel(cur)
      g=cur{i}; r=gref{i}; n=min(numel(g),numel(r));
      dg=max(dg,max(abs(g(1:n)-r(1:n)))); se=se+sum((g(1:n)-r(1:n)).^2); ns=ns+n;
      coll=coll+sum(g<=0); mng=min(mng,min(g));
    end
    rmse_gap = sqrt(se/ns);
    % NRMSE per-parametro: aggrega su tutte le traiettorie
    curP = Pm(f); num=zeros(1,5); den=0;
    for i=1:numel(curP)
      Pf=curP{i}; Pr=pref{i}; n=min(size(Pf,1),size(Pr,1));
      num = num + sum((Pf(1:n,:)-Pr(1:n,:)).^2, 1); den = den + n;
    end
    nrmse = sqrt(num/den) ./ prng;   % [1x5]
    fprintf('%5d | %9.4g | %8.4g | %5d | %7.3f || %8.4f %6.4f %6.4f %6.4f %6.4f | %6.4f\n', ...
            f, dg, rmse_gap, coll, mng, nrmse(1),nrmse(2),nrmse(3),nrmse(4),nrmse(5), mean(nrmse));
    fprintf(fid,'%d\t%.6g\t%.6g\t%d\t%.4f\t%.6g\t%.6g\t%.6g\t%.6g\t%.6g\t%.6g\n', ...
            f, dg, rmse_gap, coll, mng, nrmse(1),nrmse(2),nrmse(3),nrmse(4),nrmse(5), mean(nrmse));
  end
  fclose(fid);
  fprintf('\nscritto %s\n', fullfile(here,'cl_sweep.tsv'));
  fprintf('parametri: %s ; NRMSE normalizzata sul range di ciascun parametro nel riferimento nfrac=13\n', strjoin(pnames,','));
end


function [g, P] = qz_cl_run(t, W, K, fun, nfrac)
% UN anello chiuso su una traiettoria; ritorna gap s(k) e i 5 parametri stimati P(k). Copia fedele di
% cl_setup + cl_matlab. nfrac va ripassato al MEX (coder.Constant esige comunque l'argomento == costante).
  val = double(t.val); gt = double(t.gt_params); K = min(K, size(val, 2));
  DT = 0.1; S_MAX = 150; s_lo = 0.5*gt(3); v_cap = 1.2*gt(1); xe0 = -val(1,1); ve0 = val(2,1);
  vl = val(4, 1:K).'; xl = zeros(K,1); for k = 2:K, xl(k) = xl(k-1) + vl(k)*DT; end
  q = @(x) floor(x * 2^20) / 2^20;
  xe = xe0; ve = ve0; ve_prev = ve0; g = zeros(K,1); P = zeros(K,5);
  for k = 1:K
    s   = min(max(xl(k) - xe, s_lo), S_MAX);
    dvk = ve_prev - vl(k);
    xq  = [q(s); q(ve); q(dvk); q(vl(k))];
    [p, acc] = fun(xq, W, k == 1, nfrac);
    g(k) = xq(1); P(k,:) = p(:).';
    xe_new = xe + ve*DT; ve_new = min(max(ve + acc*DT, 0), v_cap);
    ve_prev = ve; xe = xe_new; ve = ve_new;
  end
end
