function [best, tab] = run_acc_recip_sweep(Ns, nTraj)
%RUN_ACC_RECIP_SWEEP  [SP4-L] Quanti punti serve la LUT del reciproco?
%  E_L(N) = |accel(IIDM fixed, reciproco-LUT a N) - accel(IIDM fixed, divide() SP3)| a parita' di
%  parametri. Passa se E_L < budget E_snn (p99 0.272 / max 1.484, footprint quantizzazione rete, SP3).
%  Si sceglie la N minima che passa.
%
%  VELOCE via MEX: usa `acc_sweep_kernel_r<N>_mex` (da `build_acc_sweep_mex`). Il loop `fi`
%  interpretato costava ~1 h/N; col MEX l'intero sweep e' minuti. Il riferimento aD (divide(),
%  N-INDIPENDENTE) e la rete R si calcolano UNA VOLTA per traiettoria e si riusano su tutti gli N.
  if nargin < 1 || isempty(Ns), Ns = [16 32 64 128 256]; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W = champ_weights(c);
  nTraj = min(nTraj, numel(tr));
  bud_p99 = 0.272054; bud_max = 1.48433;                 % E_snn misurato in SP3 (run_acc_fixed_sweep)
  assert(exist('acc_sweep_kernel_r0_mex','file') == 3, ...
         'manca acc_sweep_kernel_r0_mex: esegui build_acc_sweep_mex prima');

  % pre-pass N-INDIPENDENTE: rete R + riferimento aD (divide() SP3) per traiettoria, UNA VOLTA sola.
  vc = cell(nTraj,1); Rc = cell(nTraj,1); aDc = cell(nTraj,1);
  for i = 1:nTraj
    vc{i}  = double(tr{i}.val);
    Rc{i}  = double(snn_traj_fixed_r16_mex(tr{i}.val, W));
    aDc{i} = acc_sweep_kernel_r0_mex(vc{i}, Rc{i}, 0);
  end

  fprintf('budget E_snn: p99=%.6g max=%.6g [m/s^2]\n\n%-6s %12s %12s %8s\n', bud_p99, bud_max, ...
          'N', 'E_L p99', 'E_L max', 'passa');
  tab = zeros(numel(Ns), 3);
  for j = 1:numel(Ns)
    N = Ns(j);
    assert(exist(sprintf('acc_sweep_kernel_r%d_mex', N), 'file') == 3, ...
           'manca acc_sweep_kernel_r%d_mex: esegui build_acc_sweep_mex([%d])', N, N);
    mexfn = str2func(sprintf('acc_sweep_kernel_r%d_mex', N));
    E = [];
    for i = 1:nTraj
      aL = mexfn(vc{i}, Rc{i}, N);
      E = [E; abs(aL - aDc{i})]; %#ok<AGROW>
    end
    tab(j,:) = [N, prctile(E,99), max(E)];
    fprintf('%-6d %12.6g %12.6g %8s\n', N, tab(j,2), tab(j,3), string(tab(j,2)<bud_p99 && tab(j,3)<bud_max));
  end

  k = find(tab(:,2) < bud_p99 & tab(:,3) < bud_max, 1);
  assert(~isempty(k), ['nessuna N in [%s] rispetta il budget E_snn (p99<%.4g, max<%.4g): il ' ...
         'reciproco-LUT sarebbe la fonte d''errore DOMINANTE. NON allargare il budget -- e'' il dato ' ...
         'che motiva M (time-mux).'], mat2str(Ns), bud_p99, bud_max);
  best = tab(k,1);
  fprintf('\n>>> MINIMO N reciproco-LUT che rispetta il budget: %d <<<\n', best);
end
