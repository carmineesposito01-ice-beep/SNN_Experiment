function raw = snn_core(xn, W, T, cmd)
%SNN_CORE  Un passo di controllo = n_ticks tick SNN interni. Ritorna raw [5x1] (LI).
%  Stato persistente (V, fatigue, s_prev, V_LI, x_buf) tra chiamate. 'reset' azzera.
  persistent V fatigue s_prev V_LI x_buf inited
  % reset-only path (prima di una nuova sequenza): azzera lo stato e ritorna
  if nargin >= 4 && strcmp(cmd, 'reset')
    inited = []; raw = []; return;
  end
  hidden = double(W.hidden); maxd = double(W.max_delay); nt = double(W.n_ticks); rnk = double(W.rank); out = 5;
  if isempty(inited)
    V = zeros(hidden, 1, 'like', T.V); fatigue = zeros(hidden, 1, 'like', T.fatigue);
    s_prev = zeros(hidden, 1, 'like', T.V); V_LI = zeros(out, 1, 'like', T.raw);
    x_buf = zeros(4, maxd, 'like', T.V);   % ring buffer: colonna d+1 = ritardo d
    inited = true;
  end

  % pesi (gia' po2). Nel loop: fc/U via po2shift (fi->shift esatto), Vr/Wout gated dagli spike.
  W_po2 = cast(W.fc_weight, 'like', T.w);          % 32x4
  U = cast(W.rec_U, 'like', T.w); Vr = cast(W.rec_V, 'like', T.w);   % 32xR, Rx32
  Wout = cast(W.readout, 'like', T.w);             % 5x32
  base_th = cast(W.base_threshold(:), 'like', T.V);
  tjump   = max(cast(W.thresh_jump(:), 'like', T.V), 0);
  sh = round(log2(double(W.leak_div(1))));         % bit-shift leak (=3); leak_div po2 uniforme sui champion
  delays = double(W.delays);                       % 32x4 interi in [0,6)
  % esponenti/segni po2 dei pesi reali (fc, U) -> shift in fixed. Calcolati UNA volta su
  % costanti (foldati da HDL Coder come sh); |w|+(w==0) evita log2(0). Double path usa w*x.
  fcd = double(W.fc_weight); ud = double(W.rec_U);
  Kfc = round(log2(abs(fcd) + (fcd == 0))); Sfc = sign(fcd);
  KU  = round(log2(abs(ud)  + (ud  == 0))); SU  = sign(ud);

  s = zeros(hidden, 1, 'like', T.V);
  for k = 1:nt
    % 1. shift del ring-buffer + inserimento x corrente in colonna 1 (ritardo 0)
    x_buf(:, 2:end) = x_buf(:, 1:end-1);
    x_buf(:, 1) = xn;

    % 2. t_lr = Vr*s_prev : s_prev in {0,1} -> somma condizionata delle colonne (NO mult)
    t_lr = zeros(rnk, 1, 'like', T.acc);
    for j = 1:hidden
      if s_prev(j) > 0
        t_lr(:) = t_lr + Vr(:, j);
      end
    end

    % 3. LOOP PER-NEURONE (streamable in HDL: 1 lane condivisa sui 32 neuroni)
    wacc = zeros(out, 1, 'like', T.raw);             % accumulatore readout
    for i = 1:hidden
      % 3a. corrente sinaptica: fc(i,j) po2 -> SHIFT sul tap ritardato costante
      Ii = cast(0, 'like', T.accw);
      for j = 1:4
        Ii(:) = Ii + po2shift(Sfc(i, j), Kfc(i, j), W_po2(i, j), x_buf(j, delays(i, j) + 1), T.accw);
      end
      % 3b. ricorrenza: U(i,r) po2 -> SHIFT su t_lr
      reci = cast(0, 'like', T.accw);
      for r = 1:rnk
        reci(:) = reci + po2shift(SU(i, r), KU(i, r), U(i, r), t_lr(r), T.accw);
      end
      % 3c. membrana (leak-shift) + spike + fatigue + reset
      Vi  = leaky(V(i), sh) + (Ii + reci);
      eth = base_th(i) + max(fatigue(i), 0);
      si  = cast(Vi >= eth, 'like', T.V);            % comparatore hard >=
      fatigue(i) = leaky(fatigue(i), sh) + si * tjump(i);
      V(i) = Vi - si * eth;
      s(i) = si;
      % 3c. readout: si in {0,1} -> add condizionato di Wout(:,i) (NO mult)
      if si > 0
        wacc(:) = wacc + Wout(:, i);
      end
    end
    s_prev = s;

    % 4. output LI: leak bit-shift (bit_shift=3 -> 7/8) + readout accumulato
    V_LI(:) = leaky(V_LI, 3) + wacc;
  end
  raw = V_LI;
end

function y = leaky(x, n)
%LEAKY  Leak bit-shift: y = x - x/2^n. In fi -> x - bitsra(x,n) (shift aritmetico
%  esatto, 0-cost in HDL); in double -> x - x/2^n. Sostituisce la divisione fi (./ld)
%  che con l'auto-output-type introduceva un errore precision-independent (plateau ~3.5).
  if isfi(x)
    y = x - bitsra(x, n);
  else
    y = x - x ./ pow2(n);
  end
end

function y = po2shift(sgn, k, w, x, Tw)
%PO2SHIFT  y = w*x con w peso po2 (sgn=segno, k=esponente costanti). In fi: cast x al
%  tipo LARGO Tw (+frac) e shift ESATTO per 2^k (bitshift: 0 moltiplicatori, 0 perdita
%  di precisione grazie ai frac extra); in double: w*x diretto. sgn=0 -> peso mascherato.
  if isfi(x)
    if sgn == 0
      y = cast(0, 'like', Tw);
    else
      xs = bitshift(cast(x, 'like', Tw), k);   % x*2^k in tipo largo (shift aritmetico)
      if sgn < 0, y = -xs; else, y = xs; end
    end
  else
    y = w * x;
  end
end
