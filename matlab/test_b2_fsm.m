function test_b2_fsm()
%TEST_B2_FSM  [B2] Equivalenza FSM vs snn_core (entrambi FIXED) su Donatello.
%  Se coincidono bit-exact -> la FSM cycle-based implementa la stessa aritmetica.
%  NB: copre solo i primi 12 control-step della sequenza golden -> per l'equivalenza VERA
%  usare `run_b2_parity_dataset` (60 traiettorie x 1000 step). Vedi HDL_PHASE §2.1.
  here = fileparts(mfilename('fullpath'));
  % snn_b2_fsm legge b2_rom_active(): senza rigenerarla il test userebbe il champion lasciato da un
  % run precedente (es. Leonardo dopo run_b2_parity_dataset) e fallirebbe in modo SPURIO -> il test
  % dipenderebbe dall'ordine d'esecuzione. Rigenerare sempre la ROM del champion sotto test.
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
  T = snn_types('fixed', 13);
  N = min(size(c.x_norm, 1), 12);

  % --- riferimento: snn_core fixed ---
  snn_core([], [], T, 'reset');
  ref = zeros(N, 5);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', T.V);
    r = snn_core(xn, W, T);
    ref(t, :) = double(r(:)).';
  end

  % --- FSM streaming ---
  clear snn_b2_fsm
  fsm = zeros(N, 5);
  z4 = cast(zeros(4, 1), 'like', T.V);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', T.V);
    [raw, valid] = snn_b2_fsm(xn, true);
    g = 0;
    while ~valid && g < 3000
      [raw, valid] = snn_b2_fsm(z4, false);
      g = g + 1;
    end
    fsm(t, :) = double(raw(:)).';
    if t == 1, fprintf('control-step 1: %d cicli fino a valid\n', g); end
  end

  err = max(abs(ref(:) - fsm(:)));
  fprintf('B2 FSM vs snn_core (fixed): max|err| = %.6g su %d control-step\n', err, N);
  fprintf('  ref(1,:) = %s\n', mat2str(ref(1, :), 6));
  fprintf('  fsm(1,:) = %s\n', mat2str(fsm(1, :), 6));
  if err < 1e-9, disp('>> BIT-EXACT MATCH'); else, disp('>> MISMATCH (da debuggare)'); end
end
