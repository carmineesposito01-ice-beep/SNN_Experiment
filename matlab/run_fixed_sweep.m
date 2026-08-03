function run_fixed_sweep()
%RUN_FIXED_SWEEP  Ginocchio dei bit frazionari Qm.n: errore param (fisico) vs nfrac.
%  Per ogni champion e ogni nfrac: core in fi (decode esatto double) su tutta la
%  sequenza golden -> max|d| sui 5 parametri. Serve a scegliere il word-length minimo
%  che rende l'errore comportamentalmente trascurabile, senza sovradimensionare l'FPGA.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  fracs = [5 7 9 11 13];

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
      fprintf(' %5.2f', max(max(abs(P - c.y_params))));
    end
    fprintf('\n');
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
