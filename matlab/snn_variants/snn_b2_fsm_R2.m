function [raw, valid] = snn_b2_fsm(xn, start) %#codegen
%SNN_B2_FSM  [B2] SNN Donatello time-multiplexato (1 neurone/clock) con hdl.RAM.
%  Mirror BIT-EXACT dell'aritmetica di snn_core, serializzato: V/fatigue in hdl.RAM,
%  pesi in ROM (coder.const), pipeline a 2 stadi per la latenza RAM (read->compute->write,
%  1 sola chiamata RAM/ciclo). Streaming: start=1 -> nuova control-step; valid=1 -> raw pronto.
  W = coder.const(b2_rom_active());
  T = snn_types('fixed', 13);
  hidden = 32; nt = 10; rnk = coder.const(size(W.U, 2)); out = 5; sh = W.sh;

  persistent Vram fatram xbuf xnreg t_lr t_lr_nxt V_LI wacc ...
             tickc rc written phase ...
             pR_valid pR_idx pC_valid pC_idx pC_V pC_fat rawreg inited
  if isempty(inited)
    Vram   = hdl.RAM('RAMType', 'Dual port');
    fatram = hdl.RAM('RAMType', 'Dual port');
    xbuf   = cast(zeros(4, 6), 'like', T.V);
    xnreg  = cast(zeros(4, 1), 'like', T.V);
    t_lr     = cast(zeros(rnk, 1), 'like', T.acc);
    t_lr_nxt = cast(zeros(rnk, 1), 'like', T.acc);
    V_LI = cast(zeros(out, 1), 'like', T.raw);
    wacc = cast(zeros(out, 1), 'like', T.raw);
    tickc = uint8(0); rc = uint8(0); written = uint8(0); phase = uint8(0);
    pR_valid = false; pR_idx = uint8(0);
    pC_valid = false; pC_idx = uint8(0);
    pC_V = cast(0, 'like', T.V); pC_fat = cast(0, 'like', T.fatigue);
    rawreg = cast(zeros(out, 1), 'like', T.raw);
    inited = true;
  end

  valid = false;
  raw = rawreg;

  % ---------- helper x_buf: shift + inserimento xnreg (inizio tick) ----------
  % (fatto inline dove serve)

  if phase == uint8(0)
    % IDLE: su start latcha xn, fa lo shift del tick 0, avvia la pipeline
    if start
      xnreg = xn;
      xbuf(:, 2:6) = xbuf(:, 1:5); xbuf(:, 1) = xnreg;   % tick 0 shift+insert
      tickc = uint8(0); rc = uint8(0); written = uint8(0);
      wacc = cast(zeros(out, 1), 'like', T.raw);
      pR_valid = false; pC_valid = false;
      phase = uint8(1);
    end
    % passo RAM idle (mantiene coerenza)
    [~, ~] = Vram(cast(0,'like',T.V), uint8(0), false, uint8(0));
    [~, ~] = fatram(cast(0,'like',T.fatigue), uint8(0), false, uint8(0));
    return;
  end

  % ---------- FASE 1: RUN (pipeline 2-stadi, 1 chiamata RAM/ciclo) ----------
  % indirizzo di lettura per questo ciclo (neurone rc, se ancora da leggere)
  if rc < uint8(hidden), rdAddr = rc; else, rdAddr = uint8(0); end

  % UNA chiamata RAM: scrive il risultato dello stadio C (pC), legge rdAddr
  [~, Vread]   = Vram(pC_V,   pC_idx, pC_valid, rdAddr);
  [~, fatread] = fatram(pC_fat, pC_idx, pC_valid, rdAddr);
  if pC_valid
    written = written + uint8(1);
  end

  % --- STADIO C (compute): calcola il neurone i cui dati arrivano ORA (pR) ---
  nC_valid = false; nC_idx = uint8(0);
  nC_V = cast(0, 'like', T.V); nC_fat = cast(0, 'like', T.fatigue);
  if pR_valid
    i = double(pR_idx) + 1;
    Ii = cast(0, 'like', T.accw);
    for j = 1:4
      col = double(W.delays(i, j)) + 1;
      Ii(:) = Ii + cast(cast(W.fc(i, j), 'like', T.w) * xbuf(j, col), 'like', T.accw);
    end
    % [2d R2] accumulo reci ad ALBERO bilanciato (profondita' rnk->log2(rnk)) invece del ripple
    % sequenziale: taglia il path critico. Bit-exact SE gli intermedi non saturano T.accw (verificato
    % dal parity 0/60000; il ripple originale non satura sul dataset -> ribilanciare l'ordine e' esatto).
    % Loop a bound FISSO (lvsz coder.const) -> HDL Coder li srotola come i for gia' presenti; rnk in {8,16}.
    reci_p = cast(zeros(rnk, 1), 'like', T.accw);
    for r = 1:rnk
      reci_p(r) = cast(cast(W.U(i, r), 'like', T.w) * t_lr(r), 'like', T.accw);
    end
    lvsz = coder.const(round(rnk ./ 2 .^ (1:log2(rnk))));   % rnk=16 -> [8 4 2 1]
    for lev = 1:numel(lvsz)
      for q = 1:lvsz(lev)
        reci_p(q) = cast(reci_p(2*q - 1) + reci_p(2*q), 'like', T.accw);
      end
    end
    reci = reci_p(1);
    % (Ii+reci) RESTA in T.accw (Q8.17): il cast a T.V (Q5.13) buttava i 4 bit frazionari extra
    % di accw PRIMA del confronto di soglia -> spike decisi diversamente da snn_core quando Vi cade
    % entro ~2^-14 da eth (misurato: 82,4% dei control-step del dataset divergenti). Vedi HDL_PHASE §2.1.
    % Come snn_core.m:64  ->  Vi = leaky(V(i), sh) + (Ii + reci);
    Vi  = cast(Vread - bitsra(Vread, sh), 'like', T.V) + (Ii + reci);
    eth = cast(W.bth(i), 'like', T.V) + cast(max(fatread, cast(0,'like',T.fatigue)), 'like', T.V);
    si  = Vi >= eth;
    sib = cast(si, 'like', T.V);
    nC_fat   = cast(cast(fatread - bitsra(fatread, sh), 'like', T.fatigue) + sib * cast(W.tj(i), 'like', T.V), 'like', T.fatigue);
    nC_V     = cast(Vi - sib * eth, 'like', T.V);
    nC_valid = true; nC_idx = pR_idx;
    if si
      for o = 1:out
        wacc(o) = cast(wacc(o) + W.Wout(o, i), 'like', T.raw);
      end
      for r = 1:rnk
        t_lr_nxt(r) = cast(t_lr_nxt(r) + cast(W.Vr(r, i), 'like', T.acc), 'like', T.acc);
      end
    end
  end

  % --- STADIO R (read schedule): programma la lettura del neurone rc ---
  nR_valid = false; nR_idx = uint8(0);
  if rc < uint8(hidden)
    nR_valid = true; nR_idx = rc;
    rc = rc + uint8(1);
  end

  % avanza i registri pipeline
  pR_valid = nR_valid; pR_idx = nR_idx;
  pC_valid = nC_valid; pC_idx = nC_idx; pC_V = nC_V; pC_fat = nC_fat;

  % --- fine tick: tutti i 32 neuroni scritti ---
  if written >= uint8(hidden)
    V_LI = cast(cast(V_LI - bitsra(V_LI, 3), 'like', T.raw) + wacc, 'like', T.raw);
    wacc = cast(zeros(out, 1), 'like', T.raw);
    t_lr = t_lr_nxt;
    t_lr_nxt = cast(zeros(rnk, 1), 'like', T.acc);
    written = uint8(0); rc = uint8(0);
    pR_valid = false; pC_valid = false;
    if tickc >= uint8(nt - 1)
      rawreg = V_LI; raw = V_LI; valid = true;
      phase = uint8(0); tickc = uint8(0);
    else
      tickc = tickc + uint8(1);
      xbuf(:, 2:6) = xbuf(:, 1:5); xbuf(:, 1) = xnreg;   % shift+insert per il tick successivo
    end
  end
end

% ---- ROM pesi del champion attivo: in b2_rom_active.m (baked, GENERATO da gen_b2_rom(name)) ----
