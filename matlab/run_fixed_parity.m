function run_fixed_parity()
%RUN_FIXED_PARITY  Errore di quantizzazione del CORE fixed-point (Qm.n) vs golden.
%  Il decode resta ESATTO (double) dentro snn_entry (snn_entry.m:9), quindi l'errore
%  misurato e' PURAMENTE la quantizzazione del datapath ALIF, non l'approssimazione
%  del decode (quella e' lo step 2, LUT in fabric).
%
%  NB: prima passata con fimath di DEFAULT (intermedi full-precision, storage stretto
%  sulle variabili di stato tipizzate V/fatigue/V_LI). E' un LOWER BOUND sull'errore
%  di un datapath a larghezza fissa reale: serve a (a) confermare che il core gira in
%  fi, (b) vedere se l'eventprop diverge (comparatore >=/> o range), (c) primo segnale
%  Qm.n per tarare i word-length. Non e' pass/fail: REPORTA gli errori per-parametro.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  Tf = snn_types('fixed');
  pnames = {'v0', 'T', 's0', 'a', 'b'};

  fprintf('%-13s | %-7s | %-8s | %s\n', 'champion', 'variant', 'max|d|', 'errore per-parametro (fisico)');
  fprintf('%s\n', repmat('-', 1, 84));
  for i = 1:numel(champs)
    c = champs(i); W = to_weights(c); N = size(c.x_phys, 1);
    snn_core([], [], Tf, 'reset');                 % reset stato fixed una volta
    P = zeros(N, 5);
    for t = 1:N
      P(t, :) = snn_entry('fixed', c.x_phys(t, :).', W).';
    end
    dperr = abs(P - c.y_params);                    % N x 5
    permax = max(dperr, [], 1);                     % 1 x 5
    parts = arrayfun(@(k) sprintf('%s=%.3f', pnames{k}, permax(k)), 1:5, 'uni', 0);
    fprintf('%-13s | %-7s | %8.3f | %s\n', char(string(c.name)), ...
            char(string(c.variant)), max(permax), strjoin(parts, '  '));
  end
end

function W = to_weights(c)
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, ...
    'max_delay', c.max_delay, 'fc_weight', c.fc_weight, 'rec_U', c.rec_U, ...
    'rec_V', c.rec_V, 'readout', c.readout, 'delays', c.delays, ...
    'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div, 'param_lo', c.param_lo, 'param_hi', c.param_hi, ...
    'decode_offset', c.decode_offset, 'logit_tau', c.logit_tau, 'norm', c.norm);
end
