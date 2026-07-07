function raw = snn_core(xn, W, T, cmd)
%SNN_CORE  Un passo di controllo = n_ticks tick SNN interni. Ritorna raw [5x1] (LI).
%  Stato persistente (V, fatigue, s_prev, V_LI, x_buf) tra chiamate. 'reset' azzera.
  persistent V fatigue s_prev V_LI x_buf inited
  % reset-only path (prima di una nuova sequenza): azzera lo stato e ritorna
  if nargin >= 4 && strcmp(cmd, 'reset')
    inited = []; raw = []; return;
  end
  hidden = double(W.hidden); maxd = double(W.max_delay); nt = double(W.n_ticks); out = 5;
  if isempty(inited)
    V = zeros(hidden, 1, 'like', T.V); fatigue = zeros(hidden, 1, 'like', T.fatigue);
    s_prev = zeros(hidden, 1, 'like', T.V); V_LI = zeros(out, 1, 'like', T.raw);
    x_buf = zeros(4, maxd, 'like', T.V);   % ring buffer: colonna d+1 = ritardo d
    inited = true;
  end

  % pesi (gia' po2). In 'double' matmul diretto; in HDL i po2-constant -> shift (CSD).
  W_po2 = cast(W.fc_weight, 'like', T.w);          % 32x4
  U = cast(W.rec_U, 'like', T.w); Vr = cast(W.rec_V, 'like', T.w);   % 32xR, Rx32
  Wout = cast(W.readout, 'like', T.w);             % 5x32
  base_th = cast(W.base_threshold(:), 'like', T.V);
  tjump   = max(cast(W.thresh_jump(:), 'like', T.V), 0);
  ld = cast(W.leak_div(:), 'like', T.V);           % 32x1 (=8)
  delays = double(W.delays);                       % 32x4 interi in [0,6)

  for k = 1:nt
    % 1. shift del ring-buffer + inserimento x corrente in colonna 1 (ritardo 0)
    x_buf(:, 2:end) = x_buf(:, 1:end-1);
    x_buf(:, 1) = xn;

    % 2. corrente sinaptica ritardata: sinapsi (i,j) usa x_buf(:, delays(i,j)+1)
    I_input = zeros(hidden, 1, 'like', T.acc);
    for d = 0:maxd-1
      mask = (delays == d);                         % 32x4
      I_input = I_input + sum((W_po2 .* mask) .* (x_buf(:, d+1).'), 2);
    end

    % 3. ricorrenza LOW-RANK in 2 passi (mai densa)
    t_lr = Vr * s_prev;                             % Rx1
    rec  = U * t_lr;                                % 32x1

    % 4. membrana: leak bit-shift (V/ld) + drive. ld=8 -> 7/8 V.
    drive = I_input + rec;
    V(:) = V - V ./ ld + drive;

    % 5. soglia adattiva (fatigue pre-update)
    eff_th = base_th + max(fatigue, 0);

    % 6. spike (comparatore hard >=)
    s = cast(V >= eff_th, 'like', T.V);

    % 7. fatigue: leak + salto
    fatigue(:) = fatigue - fatigue ./ ld + s .* tjump;

    % 8. soft reset
    V(:) = V - s .* eff_th;
    s_prev = s;

    % 9. output LI: leak (bit_shift=3 -> 7/8) + readout
    V_LI(:) = V_LI - V_LI ./ 8 + Wout * s;
  end
  raw = V_LI;
end
