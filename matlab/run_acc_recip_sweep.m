function [best, tab] = run_acc_recip_sweep(Ns, nTraj)
%RUN_ACC_RECIP_SWEEP  [SP4-L] Quanti punti serve la LUT del reciproco?
%  E_L(N) = |accel(IIDM fixed, reciproco-LUT a N) - accel(IIDM fixed, divide() SP3)| a parita' di
%  parametri. Passa se E_L < budget E_snn (p99 0.272 / max 1.484, footprint quantizzazione rete, SP3).
%  Si sceglie la N minima che passa. LENTO (fi interpretato): lanciarlo in background sul dataset intero.
  if nargin < 1 || isempty(Ns), Ns = [16 32 64 128 256]; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W = champ_weights(c); Tp = numerictype(1,21,13);
  Tdiv = acc_types('fixed');                    % recipN=0 -> divide() SP3 (riferimento)
  nTraj = min(nTraj, numel(tr));
  bud_p99 = 0.272054; bud_max = 1.48433;        % E_snn misurato in SP3 (run_acc_fixed_sweep)
  fprintf('budget E_snn: p99=%.6g max=%.6g [m/s^2]\n\n%-6s %12s %12s %8s\n', bud_p99, bud_max, ...
          'N', 'E_L p99', 'E_L max', 'passa');
  tab = zeros(numel(Ns), 3);
  for j = 1:numel(Ns)
    Trl = acc_types('fixed', 8, Ns(j)); E = [];
    for i = 1:nTraj
      val = double(tr{i}.val); R = double(snn_traj_fixed_r16_mex(val, W));
      P = zeros(size(val,2),5);
      for k=1:size(val,2), P(k,:)=double(snn_decode_lut(fi(R(k,:).',Tp),64)).'; end
      clear acc_iidm_open; aD = zeros(size(val,2),1);
      for k=1:size(val,2), aD(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k),P(k,:).',k==1,Tdiv)); end
      clear acc_iidm_open; aL = zeros(size(val,2),1);
      for k=1:size(val,2), aL(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k),P(k,:).',k==1,Trl)); end
      E = [E; abs(aL - aD)]; %#ok<AGROW>
    end
    tab(j,:) = [Ns(j), prctile(E,99), max(E)];
    fprintf('%-6d %12.6g %12.6g %8s\n', Ns(j), tab(j,2), tab(j,3), string(tab(j,2)<bud_p99 && tab(j,3)<bud_max));
  end
  k = find(tab(:,2) < bud_p99 & tab(:,3) < bud_max, 1);
  assert(~isempty(k), ['nessuna N in [%s] rispetta il budget: il reciproco-LUT sarebbe la fonte ' ...
         'd''errore dominante. NON allargare il budget: alzare N o rivedere i range.'], mat2str(Ns));
  best = tab(k,1);
  fprintf('\n>>> MINIMO N reciproco-LUT che rispetta il budget: %d <<<\n', best);
end
