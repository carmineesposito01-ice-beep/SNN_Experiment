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
             pR_valid pR_idx pCx_valid pCx_idx pCx_xsel pCx_Vread pCx_fat ...
             pCm_valid pCm_idx pCm_Iip pCm_recip pCm_Vread pCm_fat ...
             pCa_valid pCa_idx pCa_reci pCa_Ii pCa_Vread pCa_fat ...
             pC1_valid pC1_idx pC1_Ii pC1_reci pC1_Vread pC1_fat ...
             pC2i_valid pC2i_idx pC2i_Vi pC2i_eth pC2i_fat ...
             pC2a_valid pC2a_idx pC2a_nCV pC2a_sib pC2a_fat ...
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
    pCx_valid = false; pCx_idx = uint8(0);
    pCx_xsel = cast(zeros(4, 1), 'like', T.V);
    pCx_Vread = cast(0, 'like', T.V); pCx_fat = cast(0, 'like', T.fatigue);
    pCm_valid = false; pCm_idx = uint8(0);
    pCm_Iip = cast(zeros(4, 1), 'like', T.accw); pCm_recip = cast(zeros(rnk, 1), 'like', T.accw);
    pCm_Vread = cast(0, 'like', T.V); pCm_fat = cast(0, 'like', T.fatigue);
    pCa_valid = false; pCa_idx = uint8(0);
    pCa_reci = cast(zeros(rnk/4, 1), 'like', T.accw);   % rnk/4 somme parziali (dopo 2 livelli d'albero)
    pCa_Ii = cast(0, 'like', T.accw);
    pCa_Vread = cast(0, 'like', T.V); pCa_fat = cast(0, 'like', T.fatigue);
    pC1_valid = false; pC1_idx = uint8(0);
    pC1_Ii = cast(0, 'like', T.accw); pC1_reci = cast(0, 'like', T.accw);
    pC1_Vread = cast(0, 'like', T.V); pC1_fat = cast(0, 'like', T.fatigue);
    % [2d R8] prototipi dei tipi LARGHI di Vi/eth (l'addizione fixed li allarga oltre T.V): servono per
    % registrarli fra C2i (Vi/eth) e C2a (soglia/nC_V) senza conflitto di tipo in codegen.
    zV = cast(0, 'like', T.V); zA = cast(0, 'like', T.accw); zF = cast(0, 'like', T.fatigue);
    Vi0  = cast(zV - bitsra(zV, sh), 'like', T.V) + (zA + zA);
    eth0 = cast(zV, 'like', T.V) + cast(max(zF, zF), 'like', T.V);
    pC2i_valid = false; pC2i_idx = uint8(0);
    pC2i_Vi = cast(0, 'like', Vi0); pC2i_eth = cast(0, 'like', eth0);
    pC2i_fat = cast(0, 'like', T.fatigue);
    pC2a_valid = false; pC2a_idx = uint8(0);
    pC2a_nCV = cast(0, 'like', T.V); pC2a_sib = cast(0, 'like', T.V);
    pC2a_fat = cast(0, 'like', T.fatigue);
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

  % --- STADIO Cx (mux xbuf: seleziona i 4 ingressi ritardati): dal neurone pR ---
  % [2d R9] separo il mux a indice variabile xbuf(j,col) dal DSP mult: Cx registra i 4 valori selezionati
  % (xsel), Cm fa solo i moltiplicatori dai valori registrati -> il mult (~4,6ns) resta l'unico op del suo path.
  nCx_valid = false; nCx_idx = uint8(0);
  nCx_xsel = cast(zeros(4, 1), 'like', T.V);
  nCx_Vread = cast(0, 'like', T.V); nCx_fat = cast(0, 'like', T.fatigue);
  if pR_valid
    i = double(pR_idx) + 1;
    for j = 1:4
      col = double(W.delays(i, j)) + 1;
      nCx_xsel(j) = xbuf(j, col);
    end
    nCx_Vread = Vread; nCx_fat = fatread;
    nCx_valid = true; nCx_idx = pR_idx;
  end

  % --- STADIO Cm (MAC: 16 prodotti reci + 4 prodotti Ii, REGISTRATI): dagli ingressi mux registrati pCx ---
  % [2d R6] isolo i moltiplicatori: Cm calcola e REGISTRA i prodotti (uscite DSP), Ca fa gli alberi dai
  % prodotti registrati -> il DSP mult (~4,6ns) esce dal path degli alberi (mappato sul registro P del DSP48).
  % Bit-exact: stessi prodotti, solo registrati.
  nCm_valid = false; nCm_idx = uint8(0);
  nCm_Iip = cast(zeros(4, 1), 'like', T.accw);
  nCm_recip = cast(zeros(rnk, 1), 'like', T.accw);
  nCm_Vread = cast(0, 'like', T.V); nCm_fat = cast(0, 'like', T.fatigue);
  if pCx_valid
    i = double(pCx_idx) + 1;
    for j = 1:4
      nCm_Iip(j) = cast(cast(W.fc(i, j), 'like', T.w) * pCx_xsel(j), 'like', T.accw);
    end
    for r = 1:rnk
      nCm_recip(r) = cast(cast(W.U(i, r), 'like', T.w) * t_lr(r), 'like', T.accw);
    end
    nCm_Vread = pCx_Vread; nCm_fat = pCx_fat;
    nCm_valid = true; nCm_idx = pCx_idx;
  end

  % --- STADIO Ca (alberi: Ii 4->1, reci L1-L2 16->4): dai prodotti registrati pCm ---
  kmid = coder.const(rnk / 4);                    % rnk=16 -> 4 parziali dopo 2 livelli
  nCa_valid = false; nCa_idx = uint8(0);
  nCa_reci = cast(zeros(kmid, 1), 'like', T.accw);
  nCa_Ii = cast(0, 'like', T.accw);
  nCa_Vread = cast(0, 'like', T.V); nCa_fat = cast(0, 'like', T.fatigue);
  if pCm_valid
    % Ii ad albero (4->2->1) dai prodotti registrati
    Ii_p = pCm_Iip;
    Ii_p(1) = cast(Ii_p(1) + Ii_p(2), 'like', T.accw);
    Ii_p(2) = cast(Ii_p(3) + Ii_p(4), 'like', T.accw);
    nCa_Ii  = cast(Ii_p(1) + Ii_p(2), 'like', T.accw);
    % reci: primi 2 livelli d'albero (16->4) dai prodotti registrati
    reci_p = pCm_recip;
    lvsz_a = coder.const(round(rnk ./ 2 .^ (1:2)));   % rnk=16 -> [8 4]
    for lev = 1:2
      for q = 1:lvsz_a(lev)
        reci_p(q) = cast(reci_p(2*q - 1) + reci_p(2*q), 'like', T.accw);
      end
    end
    nCa_reci = reci_p(1:kmid);            % rnk/4 somme parziali (T.accw)
    nCa_Vread = pCm_Vread; nCa_fat = pCm_fat;
    nCa_valid = true; nCa_idx = pCm_idx;
  end

  % --- STADIO C1 (SECONDA meta' dell'albero reci): dal registro pCa ---
  nC1_valid = false; nC1_idx = uint8(0);
  nC1_Ii = cast(0, 'like', T.accw); nC1_reci = cast(0, 'like', T.accw);
  nC1_Vread = cast(0, 'like', T.V); nC1_fat = cast(0, 'like', T.fatigue);
  if pCa_valid
    reci_p2 = pCa_reci;                  % kmid parziali
    lvsz_b = coder.const(round(kmid ./ 2 .^ (1:log2(kmid))));   % kmid=4 -> [2 1]
    for lev = 1:numel(lvsz_b)
      for q = 1:lvsz_b(lev)
        reci_p2(q) = cast(reci_p2(2*q - 1) + reci_p2(2*q), 'like', T.accw);
      end
    end
    nC1_reci = reci_p2(1);
    nC1_Ii = pCa_Ii; nC1_Vread = pCa_Vread; nC1_fat = pCa_fat;   % Vi/soglia -> C2 (tipi larghi restano locali)
    nC1_valid = true; nC1_idx = pCa_idx;
  end

  % --- STADIO C2i (calcola Vi ed eth, tipi larghi 28-bit): dal registro pC1 ---
  % [2d R8] separo Vi/eth (catena di add 28-bit, era il collo in C2a-R7) dalla soglia/nC_V: C2i li produce
  % e REGISTRA (tipi larghi via prototipo Vi0/eth0 in init; init nel corpo via 'like' pC2i_*). Bit-exact.
  nC2i_valid = false; nC2i_idx = uint8(0);
  nC2i_Vi = cast(0, 'like', pC2i_Vi); nC2i_eth = cast(0, 'like', pC2i_eth);
  nC2i_fat = cast(0, 'like', T.fatigue);
  if pC1_valid
    i2 = double(pC1_idx) + 1;
    nC2i_Vi  = cast(pC1_Vread - bitsra(pC1_Vread, sh), 'like', T.V) + (pC1_Ii + pC1_reci);
    nC2i_eth = cast(W.bth(i2), 'like', T.V) + cast(max(pC1_fat, cast(0,'like',T.fatigue)), 'like', T.V);
    nC2i_fat = pC1_fat;
    nC2i_valid = true; nC2i_idx = pC1_idx;
  end

  % --- STADIO C2a (soglia + nC_V + accumulo readout): dal registro pC2i ---
  nC2a_valid = false; nC2a_idx = uint8(0);
  nC2a_nCV = cast(0, 'like', T.V); nC2a_sib = cast(0, 'like', T.V);
  nC2a_fat = cast(0, 'like', T.fatigue);
  if pC2i_valid
    i2  = double(pC2i_idx) + 1;
    si  = pC2i_Vi >= pC2i_eth;
    sib = cast(si, 'like', T.V);
    nC2a_nCV = cast(pC2i_Vi - sib * pC2i_eth, 'like', T.V);
    nC2a_sib = sib; nC2a_fat = pC2i_fat;
    nC2a_valid = true; nC2a_idx = pC2i_idx;
    if si
      for o = 1:out
        wacc(o) = cast(wacc(o) + W.Wout(o, i2), 'like', T.raw);
      end
      for r = 1:rnk
        t_lr_nxt(r) = cast(t_lr_nxt(r) + cast(W.Vr(r, i2), 'like', T.acc), 'like', T.acc);
      end
    end
  end

  % --- STADIO C2b (nC_fat = leaky(fat) + sib*tj): dal registro pC2a; nC_V passa attraverso ---
  nC_valid = false; nC_idx = uint8(0);
  nC_V = cast(0, 'like', T.V); nC_fat = cast(0, 'like', T.fatigue);
  if pC2a_valid
    i3 = double(pC2a_idx) + 1;
    nC_fat = cast(cast(pC2a_fat - bitsra(pC2a_fat, sh), 'like', T.fatigue) + pC2a_sib * cast(W.tj(i3), 'like', T.V), 'like', T.fatigue);
    nC_V   = pC2a_nCV;
    nC_valid = true; nC_idx = pC2a_idx;
  end

  % --- STADIO R (read schedule): programma la lettura del neurone rc ---
  nR_valid = false; nR_idx = uint8(0);
  if rc < uint8(hidden)
    nR_valid = true; nR_idx = rc;
    rc = rc + uint8(1);
  end

  % avanza i registri pipeline (R -> Cm -> Ca -> C1 -> C2 -> write)
  pR_valid = nR_valid; pR_idx = nR_idx;
  pCx_valid = nCx_valid; pCx_idx = nCx_idx; pCx_xsel = nCx_xsel; pCx_Vread = nCx_Vread; pCx_fat = nCx_fat;
  pCm_valid = nCm_valid; pCm_idx = nCm_idx; pCm_Iip = nCm_Iip; pCm_recip = nCm_recip; pCm_Vread = nCm_Vread; pCm_fat = nCm_fat;
  pCa_valid = nCa_valid; pCa_idx = nCa_idx; pCa_reci = nCa_reci; pCa_Ii = nCa_Ii; pCa_Vread = nCa_Vread; pCa_fat = nCa_fat;
  pC1_valid = nC1_valid; pC1_idx = nC1_idx; pC1_Ii = nC1_Ii; pC1_reci = nC1_reci; pC1_Vread = nC1_Vread; pC1_fat = nC1_fat;
  pC2i_valid = nC2i_valid; pC2i_idx = nC2i_idx; pC2i_Vi = nC2i_Vi; pC2i_eth = nC2i_eth; pC2i_fat = nC2i_fat;
  pC2a_valid = nC2a_valid; pC2a_idx = nC2a_idx; pC2a_nCV = nC2a_nCV; pC2a_sib = nC2a_sib; pC2a_fat = nC2a_fat;
  pC_valid = nC_valid; pC_idx = nC_idx; pC_V = nC_V; pC_fat = nC_fat;

  % --- fine tick: tutti i 32 neuroni scritti ---
  if written >= uint8(hidden)
    V_LI = cast(cast(V_LI - bitsra(V_LI, 3), 'like', T.raw) + wacc, 'like', T.raw);
    wacc = cast(zeros(out, 1), 'like', T.raw);
    t_lr = t_lr_nxt;
    t_lr_nxt = cast(zeros(rnk, 1), 'like', T.acc);
    written = uint8(0); rc = uint8(0);
    pR_valid = false; pCx_valid = false; pCm_valid = false; pCa_valid = false; pC1_valid = false; pC2i_valid = false; pC2a_valid = false; pC_valid = false;
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
