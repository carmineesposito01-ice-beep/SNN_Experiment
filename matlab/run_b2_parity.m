function nmis = run_b2_parity(name)
%RUN_B2_PARITY  0 mismatch = il fsm B2 (ROM attiva) mirrora BIT-EXACT il core fixed, per `name`.
%  Gate di sicurezza B1.5-a: nessun champion si sintetizza senza 0 mismatch. Confronta raw del
%  core fixed (riferimento) con il raw del datapath serializzato snn_b2_fsm, control-step per
%  control-step, sulla sequenza golden del champion.
  here = fileparts(mfilename('fullpath'));
  gen_b2_rom(name);                       % ROM attiva = champion `name`
  clear b2_rom_active snn_b2_fsm;         % ricarica la ROM (nuovo champion) + resetta lo stato del fsm
  rehash;
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), name), champs), 1));
  T  = snn_types('fixed', 13); Wc = to_weights_local(c);
  N  = size(c.x_phys, 1); nmis = 0;
  snn_core([], [], T, 'reset');           % reset del core di riferimento
  for t = 1:N
    xn = cast(snn_normalize(c.x_phys(t, :).', c.norm), 'like', T.V);
    raw_core = snn_core(xn, Wc, T);
    % fsm: avvia una control-step su xn, poi cicla a vuoto fino a valid
    [rf, v] = snn_b2_fsm(xn, true); guard = 0;
    while ~v && guard < 2000
      [rf, v] = snn_b2_fsm(cast(zeros(4, 1), 'like', T.V), false); guard = guard + 1;
    end
    if ~v || any(storedInteger(raw_core(:)) ~= storedInteger(rf(:)))
      nmis = nmis + 1;
    end
  end
  fprintf('%-13s parity: %d mismatch su %d step\n', name, nmis, N);
end

function W = to_weights_local(c)
% Copia locale della to_weights di run_fixed_sweep (stesso schema di pesi per il core fixed).
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, ...
    'max_delay', c.max_delay, 'fc_weight', c.fc_weight, 'rec_U', c.rec_U, ...
    'rec_V', c.rec_V, 'readout', c.readout, 'delays', c.delays, ...
    'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div, 'param_lo', c.param_lo, 'param_hi', c.param_hi, ...
    'decode_offset', c.decode_offset, 'logit_tau', c.logit_tau, 'norm', c.norm);
end
