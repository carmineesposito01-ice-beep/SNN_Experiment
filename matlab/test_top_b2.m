function test_top_b2()
%TEST_TOP_B2  [B2] Parita' del top (SNN B2 + decode) vs snn_core(fixed)+decode esatto, su xn.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), 'Donatello'), champs), 1);
  c = champs(idx);
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, 'max_delay', c.max_delay, ...
    'fc_weight', c.fc_weight, 'rec_U', c.rec_U, 'rec_V', c.rec_V, 'readout', c.readout, ...
    'delays', c.delays, 'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div);
  Tf = snn_types('fixed', 13);
  N = min(size(c.x_norm, 1), 12);

  % --- riferimento: snn_core fixed + decode esatto ---
  snn_core([], [], Tf, 'reset');
  ref = zeros(N, 5);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', Tf.V);
    raw = snn_core(xn, W, Tf);
    ref(t, :) = snn_decode(double(raw), c.param_lo, c.param_hi, c.decode_offset, c.logit_tau).';
  end

  % --- top B2 (streaming) ---
  clear snn_top_b2 snn_b2_fsm
  z4 = cast(zeros(4, 1), 'like', Tf.V);
  top = zeros(N, 5);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', Tf.V);
    [p, done] = snn_top_b2(xn, true);
    g = 0;
    while ~done && g < 500
      [p, done] = snn_top_b2(z4, false);
      g = g + 1;
    end
    top(t, :) = double(p(:)).';
  end

  rng = double(c.param_hi(:) - c.param_lo(:)).';
  e = abs(ref - top);
  fprintf('TOP B2 (SNN+decode) vs snn_core+decode: max abs err = %.6f\n', max(e(:)));
  fprintf('  per-parametro: %s   (rel range max = %.4f%%)\n', mat2str(max(e, [], 1), 4), 100 * max(max(e ./ rng)));
  if max(e(:)) < 0.01, disp('>> TOP OK (= errore solo LUT decode)'); else, disp('>> rivedere'); end
end
