function run_parity_tests()
%RUN_PARITY_TESTS  Parita' float del core MATLAB vs golden PyTorch. Exit code !=0 su fail.
%  Per ogni champion: (a) parita' della normalizzazione; (b) parita' del forward
%  completo processando i N campioni come SEQUENZA (reset una volta, stato persiste),
%  esattamente come model.forward_sequence in PyTorch.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat'));
  champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end   % cell-of-struct -> struct array

  tolN = 1e-9;    % normalizzazione: ~esatta
  tolY = 1e-4;    % forward float: tolleranza stretta
  failed = false;

  for i = 1:numel(champs)
    c = champs(i);
    W = to_weights(c);
    N = size(c.x_phys, 1);

    % (a) parita' normalizzazione
    en = 0;
    for t = 1:N
      en = max(en, max(abs(snn_normalize(c.x_phys(t, :).', W.norm) - c.x_norm(t, :).')));
    end

    % (b) parita' forward: SEQUENZA (reset UNA volta, stato persiste tra i passi)
    snn_core([], [], snn_types('double'), 'reset');
    ey = 0;
    for t = 1:N
      p = snn_entry('double', c.x_phys(t, :).', W);
      ey = max(ey, max(abs(p(:) - c.y_params(t, :).')));
    end

    okN = en < tolN; okY = ey < tolY;
    fprintf('%-13s  norm|err|=%.2e [%s]   fwd|err|=%.2e [%s]\n', ...
            char(string(c.name)), en, tf(okN), ey, tf(okY));
    failed = failed || ~okN || ~okY;
  end

  if failed, error('run_parity_tests:FAIL', 'Parita'' fallita'); end
  disp('ALL PARITY PASS');
end

function W = to_weights(c)
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, ...
    'max_delay', c.max_delay, 'fc_weight', c.fc_weight, 'rec_U', c.rec_U, ...
    'rec_V', c.rec_V, 'readout', c.readout, 'delays', c.delays, ...
    'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div, 'param_lo', c.param_lo, 'param_hi', c.param_hi, ...
    'decode_offset', c.decode_offset, 'logit_tau', c.logit_tau, 'norm', c.norm);
end

function s = tf(b)
  if b, s = 'PASS'; else, s = 'FAIL'; end
end
