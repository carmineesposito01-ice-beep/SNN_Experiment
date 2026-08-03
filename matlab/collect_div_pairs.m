function P = collect_div_pairs(maxTraj)
%COLLECT_DIV_PAIRS  [SP4-M-FSM G1] Estrae le coppie (num,den) REALI che le 5 divisioni dell'ACC-IIDM fixed
%  assumono sul dataset. Riferimento: MEX(snn_core forward fixed)+decode-64 -> acc_iidm_open fixed (la
%  stessa catena di run_block_acciidm_test). Le coppie escono da acc_iidm_open via il suo 2o output
%  (nargout>=2), gia' castate a T.acc (lossless) -> nessuna duplicazione della matematica (difesa §2.1).
%  Ritorna P (M x 2) = [num den] in double, impilate per tutte le divisioni/step/traiettorie.
  here = fileparts(mfilename('fullpath'));
  if nargin < 1 || isempty(maxTraj), maxTraj = inf; end
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  W  = champ_weights(c); Tp = numerictype(1,21,13); Tt = acc_types('fixed');
  nT = min(numel(tr), maxTraj);
  P = [];
  for t = 1:nT
    R   = double(snn_traj_fixed_r16_mex(tr{t}.val, W));   % forward fixed (MEX)
    val = double(fi(double(tr{t}.val),1,32,20));          % ingressi pre-quantizzati (come SP2 test)
    clear collect_step_mex;                                % stato OU pulito per traiettoria (MEX)
    K  = size(val,2);
    Pt = zeros(5*K,2);
    for k = 1:K
      p = double(snn_decode_lut(fi(R(k,:).',Tp),64));      % 64 = decode del campione
      [~, pairs] = collect_step_mex(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1);   % MEX (fi interpretato = ~47 min)
      Pt((k-1)*5+(1:5), :) = double(pairs);
    end
    P = [P; Pt]; %#ok<AGROW>
    if mod(t,5)==0 || t==nT, fprintf('  collect traj %d/%d (%d coppie)\n', t, nT, size(P,1)); end
  end
  fprintf('collect_div_pairs: %d coppie da %d traiettorie\n', size(P,1), nT);
end
