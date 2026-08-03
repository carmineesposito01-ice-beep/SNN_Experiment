function test_top_b2()
%TEST_TOP_B2  [B2] Parita' del top (SNN B2 + decode) vs snn_core(fixed)+decode esatto, su xn.
%  NB: copre solo la sequenza golden -> per l'equivalenza VERA del forward usare
%  `run_b2_parity_dataset` (60 traiettorie x 1000 step). Vedi HDL_PHASE §2.1.
  here = fileparts(mfilename('fullpath'));
  % la ROM (b2_rom_active) e' stato GLOBALE: senza rigenerarla il test userebbe il champion
  % lasciato da un run precedente -> fallimento spurio dipendente dall'ordine d'esecuzione.
  gen_b2_rom('Donatello');
  clear b2_rom_active snn_b2_fsm; rehash;
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
  % Soglia agganciata al BUDGET gia' accettato dal progetto (quantizzazione fixed <= 0.028 su v0,
  % HDL_PHASE §2), non a un numero magico: l'errore qui e' l'approssimazione del decode, e il criterio
  % di scelta della LUT e' che resti SOTTO la quantizzazione (DECODE_LUT_SWEEP.md §5bis).
  % Col decode LUT-64 del campione (dal 2026-07-14) l'atteso e' ~0.013; col vecchio 256 era ~0.002
  % (per quello la soglia era 0.01, che col campione attuale darebbe un falso allarme).
  tol = 0.028;
  if max(e(:)) < tol
    disp('>> TOP OK (errore = approssimazione del decode, sotto il budget di quantizzazione)');
  else
    disp('>> rivedere');
  end
  assert(max(e(:)) < tol, ['top: errore %.4g >= budget %.3g -> il decode e'' diventato la fonte ' ...
         'd''errore dominante (rivedere la dimensione della LUT, DECODE_LUT_SWEEP.md §5bis)'], max(e(:)), tol);
end
