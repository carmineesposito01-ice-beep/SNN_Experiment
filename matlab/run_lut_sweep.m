function run_lut_sweep(nmax)
%RUN_LUT_SWEEP  Accuratezza dei params di Donatello al variare della dimensione LUT del decode.
%  Forward B2 fixed via snn_traj_fixed_r16_mex (raw calcolato UNA volta per traiettoria). Il decode
%  LUT-N si applica in DOUBLE (tabella N-punti costruita una volta, interpolazione vettoriale): la
%  curva accuratezza-vs-N misura l'errore d'interpolazione della sigmoide, cioe' l'effetto della
%  DIMENSIONE LUT. Il decode fixed-point e' verificato a parte (snn_decode_lut(.,256)==snn_decode_hdl,
%  bit-exact) -- la quantizzazione fixed aggiunge un offset ~costante, non cambia il ginocchio.
%    acc% da NRMSE vs gt_params (veri) ; dmax vs LUT-512 (near-exact) = effetto della sola dimensione.
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  if nargin < 1, nmax = numel(tr); else, nmax = min(nmax, numel(tr)); end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  W = champ_weights(c); rng_p = double(c.param_hi(:) - c.param_lo(:)).';
  Ns = [16 32 64 128 256 512];
  Praw = cell(nmax, 1); gt = zeros(nmax, 5);
  for k = 1:nmax
    Praw{k} = double(snn_traj_fixed_r16_mex(tr{k}.val, W));   % raw fixed, una volta
    gt(k, :) = double(tr{k}.gt_params(:)).';
  end
  Pagg = @(N) cell2mat(arrayfun(@(k) mean_2h(decode_lut_double(Praw{k}, N)), (1:nmax).', 'UniformOutput', false));
  P512 = Pagg(512);   % baseline near-exact
  outdir = fullfile(here, 'axi', 'build', 'lut_sweep'); if ~exist(outdir, 'dir'), mkdir(outdir); end
  fid = fopen(fullfile(outdir, 'results_lut.csv'), 'w'); fprintf(fid, 'N,acc,dmax_vs_512\n');
  fprintf('%-5s | %-7s | %-12s\n', 'N', 'acc%', 'dmax vs 512');
  for N = Ns
    PN = Pagg(N);
    nrmse = sqrt(mean((PN - gt).^2, 1)) ./ rng_p;
    acc = 100 * (1 - mean(nrmse));
    dmax = max(abs(PN(:) - P512(:)));
    fprintf('%-5d | %6.2f | %.4f\n', N, acc, dmax);
    fprintf(fid, '%d,%.4f,%.4f\n', N, acc, dmax);
  end
  fclose(fid); fprintf('scritto %s (%d traiettorie)\n', fullfile(outdir, 'results_lut.csv'), nmax);
end

function m = mean_2h(P)          % media della 2a meta' (M x 5 -> 1 x 5)
  M = size(P, 1); m = mean(P(floor(M/2) + 1:M, :), 1);
end

function P = decode_lut_double(R, N)   % R: M x 5 raw -> M x 5 params, sigmoide LUT-N in double
  offset = [-0.40404 -0.39012 1.7718 2.6884 -0.95578]; invtau = [0.1 1/3 0.1 1/3 1/3];
  lo = [8 0.5 1 0.3 0.5]; hilo = [37 2 4 2.2 2.5]; scale = N / 16;
  sg = (1 ./ (1 + exp(-(-8 + (0:N-1) / scale)))).';   % N x 1 (colonna: sg(k+1) resta colonna)
  M = size(R, 1); P = zeros(M, 5);
  for i = 1:5
    adj = (R(:, i) - offset(i)) * invtau(i);
    scaled = (adj + 8) * scale;
    k = min(max(floor(scaled), 0), N - 2);         % M x 1 indice
    frac = scaled - k;
    P(:, i) = lo(i) + hilo(i) * (sg(k + 1) + frac .* (sg(k + 2) - sg(k + 1)));
  end
end
