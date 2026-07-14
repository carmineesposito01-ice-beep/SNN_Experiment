function run_b15a_validate(nmax)
%RUN_B15A_VALIDATE  Metriche funzionali fixed-point dei 4 champion sul dataset held-out,
%  usando il MEX compilato (snn_traj_fixed_r{16,8}_mex) per il core fi; il decode (sigmoide,
%  nonlineare) resta in double, per-step. Aggrega come il riferimento Python (media 2a meta',
%  indici N/2+1:N), poi:
%    - NRMSE per-param vs gt_params (veri)      -> accuratezza dell'hardware
%    - max|delta| vs ref_params (float, stessa aggregazione) -> errore di quantizzazione
%  Scrive axi/build/phase_b15a/functional.csv. nmax (opz.) limita le traiettorie (test rapido).
%  Prerequisito: build_traj_mex (genera i due MEX).
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  if nargin < 1, nmax = numel(tr); else, nmax = min(nmax, numel(tr)); end
  names = {'Donatello', 'Michelangelo', 'Raffaello', 'Leonardo'};
  hdr = {'v0', 'T', 's0', 'a', 'b'};
  outdir = fullfile(here, 'axi', 'build', 'phase_b15a'); if ~exist(outdir, 'dir'), mkdir(outdir); end
  fid = fopen(fullfile(outdir, 'functional.csv'), 'w');
  fprintf(fid, 'champion,param,nrmse_vs_gt,delta_vs_float\n');
  fprintf('%-13s | %-30s | %-7s | %-8s\n', 'champion', 'NRMSE vs GT [v0 T s0 a b]', 'acc%', 'maxdFlt');
  for ci = 1:numel(names)
    c    = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), names{ci}), champs), 1));
    W    = champ_weights(c);
    is16 = (c.rank == 16);
    rng  = double(c.param_hi(:) - c.param_lo(:));
    sqerr = zeros(5, 1); dmax = 0;
    for k = 1:nmax
      t = tr{k}; val = t.val; N = size(val, 2);
      if is16, Praw = snn_traj_fixed_r16_mex(val, W); else, Praw = snn_traj_fixed_r8_mex(val, W); end
      P = zeros(N, 5);
      for s = 1:N
        P(s, :) = snn_decode(Praw(s, :).', W.param_lo, W.param_hi, W.decode_offset, W.logit_tau).';
      end
      pfix = mean(P(floor(N/2) + 1:N, :), 1).';           % media 2a meta'
      co = cellstr(t.champion_order); ri = find(strcmp(strtrim(co), names{ci}), 1);
      pflt = double(t.ref_params(ri, :)).';
      gt   = double(t.gt_params(:));
      sqerr = sqerr + (pfix - gt).^2;
      dmax  = max(dmax, max(abs(pfix - pflt)));
    end
    nrmse = sqrt(sqerr / nmax) ./ rng;
    acc = 100 * (1 - mean(nrmse));
    fprintf('%-13s | %s | %6.2f | %.4f\n', names{ci}, sprintf('%.3f ', nrmse), acc, dmax);
    for p = 1:5, fprintf(fid, '%s,%s,%.4f,%.4f\n', names{ci}, hdr{p}, nrmse(p), dmax); end
  end
  fclose(fid);
  fprintf('scritto %s (%d traiettorie)\n', fullfile(outdir, 'functional.csv'), nmax);
end
