function qz_run_fixed_sweep()
%QZ_RUN_FIXED_SWEEP  [Quantizzation_Study] Ginocchio dei bit frazionari Qm.n: errore param vs nfrac.
%  Copia isolata di run_fixed_sweep, con GRIGLIA ESTESA (5..13) e scrittura del risultato in
%  acc_sweep.tsv. Per ogni champion e ogni nfrac: core in fi (decode esatto double) su tutta la
%  sequenza golden -> max|d| sui 5 parametri. NON modifica l'originale run_fixed_sweep.
  here  = fileparts(mfilename('fullpath'));
  mroot = fileparts(here);                                  % .../matlab
  d = load(fullfile(mroot, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  % SOLO Donatello: e' il forward DEPLOYATO (blocco Donatello_Tier, prescelto BAL). Gli altri champion
  % sono reti diverse, non deployate -> la loro curva di quantizzazione e' irrilevante per questo studio.
  % (I tier SLOW/BAL/FAST condividono questo stesso forward -> stessa accuratezza-vs-nfrac.)
  champs = champs(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs));
  assert(~isempty(champs), 'champion Donatello non trovato in champions_export.mat');
  fracs = [2 3 4 5 6 7 8 9 10 11 12 13];

  rows = {};   % {champion, nfrac, maxd}
  fprintf('%-13s |', 'champion / f');
  for f = fracs, fprintf(' Q?.%-2d', f); end
  fprintf('    (max|d| param, fisico; double=~2e-6)\n');
  fprintf('%s\n', repmat('-', 1, 13 + numel(fracs) * 6 + 40));
  for i = 1:numel(champs)
    c = champs(i); W = to_weights(c); N = size(c.x_phys, 1);
    fprintf('%-13s |', char(string(c.name)));
    for f = fracs
      T = snn_types('fixed', f);
      snn_core([], [], T, 'reset');
      P = zeros(N, 5);
      for t = 1:N
        xn  = cast(snn_normalize(c.x_phys(t, :).', W.norm), 'like', T.V);
        raw = snn_core(xn, W, T);
        P(t, :) = snn_decode(double(raw), W.param_lo, W.param_hi, ...
                             W.decode_offset, W.logit_tau).';
      end
      dmx = max(max(abs(P - c.y_params)));
      rows(end+1, :) = {char(string(c.name)), f, dmx}; %#ok<AGROW>
      fprintf(' %5.2f', dmx);
    end
    fprintf('\n');
  end

  fid = fopen(fullfile(here, 'acc_sweep.tsv'), 'w');
  fprintf(fid, 'champion\tnfrac\tmaxd\n');
  for k = 1:size(rows, 1)
    fprintf(fid, '%s\t%d\t%.6g\n', rows{k, 1}, rows{k, 2}, rows{k, 3});
  end
  fclose(fid);
  fprintf('scritto %s (%d righe)\n', fullfile(here, 'acc_sweep.tsv'), size(rows, 1));
end

function W = to_weights(c)
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, ...
    'max_delay', c.max_delay, 'fc_weight', c.fc_weight, 'rec_U', c.rec_U, ...
    'rec_V', c.rec_V, 'readout', c.readout, 'delays', c.delays, ...
    'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div, 'param_lo', c.param_lo, 'param_hi', c.param_hi, ...
    'decode_offset', c.decode_offset, 'logit_tau', c.logit_tau, 'norm', c.norm);
end
