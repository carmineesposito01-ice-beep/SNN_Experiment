function qzi_acc_sweep(fracs, nTraj)
%QZI_ACC_SWEEP  [fast/MEX] Fedelta' OPEN-LOOP dell'IIDM sui golden inputs: accel(IIDM@nfrac) vs
%  accel(IIDM double), a params IDENTICI (SNN congelata @13). Riusa i MEX qzi_cl_step_n%d_mex (Task 1) +
%  qzi_cl_step_dbl_mex (riferimento double) -> veloce (niente fi interpretato: ~min invece di ~ore).
%  Metriche sull'accel: NRMSE (su escursione REALE del riferimento) + max|d| (worst-case). Riferimento =
%  IIDM DOUBLE a parita' di params (come run_acc_fixed_sweep). Progresso in qzi_acc_progress.txt
%  (riscritto a ogni traj -> leggibile durante la run, niente buio da buffering).
  if nargin < 1 || isempty(fracs), fracs = [13 8 5 2]; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  addpath(mroot); addpath(here);
  ds = load(fullfile(mroot,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(mroot,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W  = champ_weights(c);
  nTraj = min(nTraj, numel(tr));
  pfile = fullfile(here,'qzi_acc_progress.txt');

  % --- MEX: costruisci quelli mancanti (dbl riferimento + i 4 nfrac di Task 1) ---
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
  if isempty(which('qzi_cl_step_dbl_mex'))
    fprintf('build qzi_cl_step_dbl_mex ...\n');
    codegen('qzi_cl_step_dbl','-config',cfg,'-args',{zeros(4,1),coder.typeof(W),true}, ...
            '-o','qzi_cl_step_dbl_mex','-d','codegen_nidbl');
  end
  for f = fracs
    mx = sprintf('qzi_cl_step_n%d_mex', f);
    if isempty(which(mx))
      fprintf('build %s ...\n', mx);
      codegen('qzi_cl_step','-config',cfg,'-args',{zeros(4,1),coder.typeof(W),true,coder.Constant(f)}, ...
              '-o',mx,'-d',['codegen_ni' num2str(f)]);
    end
  end

  % --- calcolo (tutto MEX) ---
  numv = zeros(numel(fracs),1); maxd = zeros(numel(fracs),1); denv = 0; gMin = inf; gMax = -inf;
  for i = 1:nTraj
    val = double(tr{i}.val); N = size(val,2);
    aD = zeros(N,1);
    for k = 1:N, [~, aD(k)] = qzi_cl_step_dbl_mex(val(:,k), W, k==1); end
    gMin = min(gMin, min(aD)); gMax = max(gMax, max(aD)); denv = denv + N;
    for j = 1:numel(fracs)
      f = fracs(j); fun = str2func(sprintf('qzi_cl_step_n%d_mex', f));
      aF = zeros(N,1);
      for k = 1:N, [~, aF(k)] = fun(val(:,k), W, k==1, f); end
      numv(j) = numv(j) + sum((aF-aD).^2);
      maxd(j) = max(maxd(j), max(abs(aF-aD)));
    end
    fid = fopen(pfile,'w'); fprintf(fid,'traj %d/%d completato\n', i, nTraj); fclose(fid);
  end
  arng = gMax - gMin; if arng==0, arng=1; end
  nrmse = sqrt(numv/denv) / arng;

  fid = fopen(fullfile(here,'qzi_acc_sweep.tsv'),'w'); fprintf(fid,'nfrac\tNRMSE_accel\tmaxd_accel\n');
  fprintf('\n%-6s %13s %13s  (accel range double = %.4g m/s^2)\n','nfrac','NRMSE_accel','max|d|',arng);
  for j = 1:numel(fracs)
    fprintf('%-6d %13.6g %13.6g\n', fracs(j), nrmse(j), maxd(j));
    fprintf(fid,'%d\t%.6g\t%.6g\n', fracs(j), nrmse(j), maxd(j));
  end
  fclose(fid);
  fid = fopen(pfile,'w'); fprintf(fid,'FINITO: TSV scritto\n'); fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_acc_sweep.tsv'));
end
