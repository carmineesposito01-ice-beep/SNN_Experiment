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
             pR_valid pR_idx pC1_valid pC1_idx pC1_Ii pC1_reci pC1_Vread pC1_fat ...
             pC_valid pC_idx pC_V pC_fat rawreg inited
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
    pC1_valid = false; pC1_idx = uint8(0);
    pC1_Ii = cast(0, 'like', T.accw); pC1_reci = cast(0, 'like', T.accw);
    pC1_Vread = cast(0, 'like', T.V); pC1_fat = cast(0, 'like', T.fatigue);
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

  % --- STADIO C1 (produce Vi, eth): dal neurone pR ---
  % [2d R3] spezzo lo stadio-C in C1 (Vi/eth) -> registro pC1 -> C2 (soglia+update): il compute del
  % neurone gira su 2 cicli (latenza +1, GRATIS nel time-mux) -> dimezza la profondita' combinatoria.
  % Bit-exact: STESSA aritmetica, solo registrata a meta'. La lettura RAM (pR/rdAddr) e' INTATTA; la
  % scrittura (via pC) slitta di 1 ciclo -> nessun hazard entro il tick (ogni neurone letto/scritto 1 volta).
  nC1_valid = false; nC1_idx = uint8(0);
  nC1_Ii = cast(0, 'like', T.accw); nC1_reci = cast(0, 'like', T.accw);
  nC1_Vread = cast(0, 'like', T.V); nC1_fat = cast(0, 'like', T.fatigue);
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
    % Registra i DUE accumuli (Ii, reci: entrambi T.accw grazie a Ii(:)= e al cast dell'albero) +
    % Vread/fatread: C2 fa Vi=leaky(Vread)+(Ii+reci) e la soglia. Cosi' i tipi registrati sono NOTI
    % (T.accw/T.V/T.fatigue); registrare Vi/eth darebbe conflitto di tipo (l'addizione fixed li allarga).
    nC1_Ii = Ii; nC1_reci = reci;
    nC1_Vread = Vread;                    % porta Vread (T.V) a C2 (leaky)
    nC1_fat = fatread;                    % porta fatread (T.fatigue) a C2 (eth + nC_fat)
    nC1_valid = true; nC1_idx = pR_idx;
  end

  % --- STADIO C2 (soglia + update): dal registro pC1 (neurone del ciclo PRECEDENTE) ---
  nC_valid = false; nC_idx = uint8(0);
  nC_V = cast(0, 'like', T.V); nC_fat = cast(0, 'like', T.fatigue);
  if pC1_valid
    i2  = double(pC1_idx) + 1;
    % Vi/eth calcolati QUI da (Ii,reci,Vread,fatread) registrati -> stessi valori dell'originale (bit-exact),
    % ma i tipi larghi (Vi, eth) restano LOCALI (non registrati) -> nessun conflitto di tipo in codegen.
    Vi  = cast(pC1_Vread - bitsra(pC1_Vread, sh), 'like', T.V) + (pC1_Ii + pC1_reci);
    eth = cast(W.bth(i2), 'like', T.V) + cast(max(pC1_fat, cast(0,'like',T.fatigue)), 'like', T.V);
    si  = Vi >= eth;
    sib = cast(si, 'like', T.V);
    nC_fat   = cast(cast(pC1_fat - bitsra(pC1_fat, sh), 'like', T.fatigue) + sib * cast(W.tj(i2), 'like', T.V), 'like', T.fatigue);
    nC_V     = cast(Vi - sib * eth, 'like', T.V);
    nC_valid = true; nC_idx = pC1_idx;
    if si
      for o = 1:out
        wacc(o) = cast(wacc(o) + W.Wout(o, i2), 'like', T.raw);
      end
      for r = 1:rnk
        t_lr_nxt(r) = cast(t_lr_nxt(r) + cast(W.Vr(r, i2), 'like', T.acc), 'like', T.acc);
      end
    end
  end

  % --- STADIO R (read schedule): programma la lettura del neurone rc ---
  nR_valid = false; nR_idx = uint8(0);
  if rc < uint8(hidden)
    nR_valid = true; nR_idx = rc;
    rc = rc + uint8(1);
  end

  % avanza i registri pipeline (R -> C1 -> C2 -> write)
  pR_valid = nR_valid; pR_idx = nR_idx;
  pC1_valid = nC1_valid; pC1_idx = nC1_idx; pC1_Ii = nC1_Ii; pC1_reci = nC1_reci; pC1_Vread = nC1_Vread; pC1_fat = nC1_fat;
  pC_valid = nC_valid; pC_idx = nC_idx; pC_V = nC_V; pC_fat = nC_fat;

  % --- fine tick: tutti i 32 neuroni scritti ---
  if written >= uint8(hidden)
    V_LI = cast(cast(V_LI - bitsra(V_LI, 3), 'like', T.raw) + wacc, 'like', T.raw);
    wacc = cast(zeros(out, 1), 'like', T.raw);
    t_lr = t_lr_nxt;
    t_lr_nxt = cast(zeros(rnk, 1), 'like', T.acc);
    written = uint8(0); rc = uint8(0);
    pR_valid = false; pC1_valid = false; pC_valid = false;
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
