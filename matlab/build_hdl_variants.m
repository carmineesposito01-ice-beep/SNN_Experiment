function build_hdl_variants()
%BUILD_HDL_VARIANTS  Aggiunge a snn_champions_lib.slx i blocchi Donatello HDL-ready SELF-CONTAINED:
%  `Donatello_Champion` (decode deployato, sigma-LUT 256) + `Donatello_LUT{16..512}` (decode LUT-N).
%
%  ARCHITETTURA = quella del bitstream: forward B2 **time-mux** (snn_b2_fsm, hdl.RAM, 1 neurone/clock)
%  -> HDL Coder genera il time-mux (DualPortRAM), non la parallela superata (HDL_PHASE §3.1.1).
%
%  I/O **FISICO** (fixed): s, v, dv, v_l -> v0, T, s0, a, b. **NIENTE start/done**: la FSM e' pilotata
%  internamente (free-running: riparte su done) -> plug&play e nessun fallimento silenzioso (§3.1.2).
%
%  SELF-CONTAINED: la chart inlina come **funzioni locali** i sorgenti VERI, letti a build-time
%  (b2_rom_active + snn_types + snn_b2_fsm + il decode). Le funzioni locali hanno precedenza sul path
%  => nessuna copia a mano (niente deriva) e il `.slx` gira/genera VHDL **su un altro PC senza alcun .m**.
%  Gate d'accettazione: `run_block_hdl_gate` (toglie matlab/ dal path e lancia makehdl).
%
%  USO: il time-mux impiega ~341 clock/inferenza -> il modello ospite gira al **rate di clock** e i
%  params si aggiornano ogni ~341 passi. E' l'architettura (il 5,5x di area risparmiata), non un difetto.
  here = fileparts(mfilename('fullpath'));
  gen_b2_rom('Donatello');                       % ROM attiva = Donatello -> b2_rom_active.m

  % --- sorgenti VERI da inlinare (single-source: letti, non copiati) ---
  srcRom   = fileread(fullfile(here, 'b2_rom_active.m'));
  srcTypes = fileread(fullfile(here, 'snn_types.m'));
  srcFsm   = fileread(fullfile(here, 'snn_b2_fsm.m'));
  srcLut   = fileread(fullfile(here, 'snn_decode_lut.m'));
  srcHdl   = fileread(fullfile(here, 'snn_decode_hdl.m'));
  srcIidm  = fileread(fullfile(here, 'acc_iidm_open.m'));   % SP2: matematica IIDM (single source)
  srcAccT  = fileread(fullfile(here, 'acc_types.m'));       % SP3: tipi dell'IIDM (single source)
  % SP4-M-FSM: funzioni-fase della forma FSM (single source condiviso col model acc_iidm_fsm, che G2
  % valida a dmax=0 su 60000 control-step). La chart di Donatello_ACC_IIDM_M le inlina e le chiama negli
  % stati, sostituendo la sola fsm_div con l'handshake verso il blocco Divide HDL (G1: bit-identici).
  srcFDiv  = fileread(fullfile(here, 'fsm_div.m'));
  srcPrep  = fileread(fullfile(here, 'iidm_prep.m'));
  srcNd    = fileread(fullfile(here, 'iidm_nd.m'));
  srcUse   = fileread(fullfile(here, 'iidm_use.m'));
  srcTanh  = fileread(fullfile(here, 'iidm_tanh.m'));
  srcFinal = fileread(fullfile(here, 'iidm_final.m'));

  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  nrm = double(c.norm(:));                       % [S V DV VL]

  Ns = [16 32 64 128 256 512];
  % Il CAMPIONE usa il decode a 64 punti (dal 2026-07-14): stessa scelta del top deployato
  % `snn_top_b2`. Vedi DECODE_LUT_SWEEP.md. -> Donatello_Champion e' funzionalmente identico a
  % Donatello_LUT64: il primo e' il nome SEMANTICO (cosa si deploya), il secondo la variante di studio.
  NCHAMP = 64;
  names = [{'Donatello_Champion'}, arrayfun(@(N) sprintf('Donatello_LUT%d', N), Ns, 'UniformOutput', false)];
  calls = [{sprintf('snn_decode_lut(raw, %d)', NCHAMP)}, arrayfun(@(N) sprintf('snn_decode_lut(raw, %d)', N), Ns, 'UniformOutput', false)];
  decs  = [{srcLut}, repmat({srcLut}, 1, numel(Ns))];
  desc  = [{['IL CAMPIONE: e'' esattamente cio'' che va sull''FPGA (stesso decode del top deployato ' ...
             'snn_top_b2). Decode della sigmoide via LUT a 64 punti. Perche'' 64: lo studio ' ...
             'DECODE_LUT_SWEEP.md ha misurato che l''accuratezza e'' piatta (~84%) su N=16..512, e che 64 e'' ' ...
             'la LUT piu'' piccola il cui errore d''approssimazione su v0 (0.0114) resta SOTTO l''errore di ' ...
             'quantizzazione fixed gia'' accettato (0.028) -> il decode non diventa la fonte d''errore ' ...
             'dominante. Rispetto ai 256 punti usati fino al 2026-07-14: accuratezza identica ' ...
             '(83.98 vs 83.97) e -288 LUT sul top (4630 -> 4342). Nota: funzionalmente IDENTICO al ' ...
             'blocco Donatello_LUT64 (qui il nome dice cosa si deploya, li'' che e'' una variante di studio).']}, ...
           arrayfun(@(N) sprintf(['Decode della sigmoide via LUT a %d punti (snn_decode_lut). Variante ' ...
             'per lo studio del compromesso dimensione-LUT / accuratezza / risorse: l''accuratezza e'' ' ...
             'piatta (~84%%) su N=16..512 mentre le LUT di sintesi crescono da 520 a 1732 (vedi ' ...
             'document/DECODE_LUT_SWEEP.md). Il forward e'' identico in tutte le varianti.'], N), ...
             Ns, 'UniformOutput', false)];

  lib = 'snn_champions_lib'; libfile = fullfile(here, [lib '.slx']);
  assert(isfile(libfile), '%s inesistente: esegui prima build_library()', libfile);
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(libfile); set_param(lib, 'Lock', 'off');

  in_names  = {'s', 'v', 'dv', 'v_l'};
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for i = 1:numel(names)
    sub = [lib '/' names{i}];
    if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
    add_block('built-in/Subsystem', sub, 'Position', [40, 30 + (i-1)*80, 230, 70 + (i-1)*80], ...
              'Description', block_description(names{i}, desc{i}));
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']);
    chart.Script = chart_code(calls{i}, decs{i}, srcRom, srcTypes, srcFsm, nrm);
    for j = 1:4
      add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
      add_line(sub, [in_names{j} '/1'], ['SNN/' num2str(j)]);
    end
    for j = 1:5
      add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
      add_line(sub, ['SNN/' num2str(j)], [out_names{j} '/1']);
    end
    fprintf('  costruito %s\n', names{i});
  end

  % ---- SP2/SP3: blocco unico campione + plant ACC-IIDM open-loop, HDL-READY ----
  % Dal 2026-07-16 (SP3) l'IIDM e' fixed-point (acc_types) e il blocco genera VHDL come gli altri:
  % prima era in double e HDL Coder lo rifiutava (14 errori). Serve a dare il costo in silicio del
  % controllore COMPLETO (rete + legge di controllo), cioe' cio' che si confronta con un MPC.
  % ⚠️ HDL-ready NON vuol dire deployato: il bitstream PYNQ-Z1 resta la sola SNN.
  sub = [lib '/Donatello_ACC_IIDM'];
  if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position', [300, 30, 500, 70], ...
            'Description', acciidm_description(NCHAMP));
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN_ACC']);
  chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN_ACC']);
  chart.Script = acciidm_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcIidm, srcAccT, nrm);
  for j = 1:4
    add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
    add_line(sub, [in_names{j} '/1'], ['SNN_ACC/' num2str(j)]);
  end
  add_block('built-in/Outport', [sub '/accel'], 'Port', '1');
  add_line(sub, 'SNN_ACC/1', 'accel/1');
  fprintf('  costruito Donatello_ACC_IIDM (SP2/SP3, HDL-ready)\n');

  % ---- SP4-M-FSM: blocco M = stessa catena, ma le 5 divisioni SEQUENZIATE su UN blocco Divide HDL ----
  % Donatello_ACC_IIDM (sopra) resta il RIFERIMENTO: bit-identita' (G3) e baseline OOC. Qui la chart
  % orchestra un UNICO HDLMathLib/Divide via handshake (num,den,vin) -> (quot,vout), chiamando le
  % funzioni-fase condivise col model acc_iidm_fsm (G2: dmax=0 su 60000 control-step).
  % Perche': SP4-M config-based (resource sharing) si fermava a 9,5 MHz con area ESPLOSA (LUT x2,36,
  % FF x13,9) -> document/SP4_ACC_IIDM_FAST.md §Variante M. Obiettivo: >= 11,65 MHz con area ridotta.
  subM = [lib '/Donatello_ACC_IIDM_M'];
  if getSimulinkBlockHandle(subM) > 0, delete_block(subM); end
  add_block('built-in/Subsystem', subM, 'Position', [300, 100, 500, 160], ...
            'Description', acciidm_m_description(NCHAMP));
  add_block('simulink/User-Defined Functions/MATLAB Function', [subM '/IIDM_CTRL']);
  chartM = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [subM '/IIDM_CTRL']);
  chartM.Script = acciidm_m_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcAccT, ...
                                       srcFDiv, srcPrep, srcNd, srcUse, srcTanh, srcFinal, nrm);
  % SOLA CHART nel subsystem (4 ingressi, 1 uscita: identico a SP3). Niente blocco `Divide`, niente Unit
  % Delay, niente handshake, niente feedback: erano l'impalcatura di #1, morta il 2026-07-17 perche' un
  % blocco ACCANTO alla chart impone la conversione MATLAB-to-dataflow, che VIETA `tanh` fixed -- e `tanh`
  % e' nel cuore dell'IIDM (HDL_PHASE §9 · SP4_ACC_IIDM_FAST.md §Variante M-FSM).
  % Il time-mux lo fa la FSM dentro la chart: UNA sola chiamata a `fsm_div` nel sorgente => HDL Coder
  % genera UN divisore, riusato in 5 cicli. (Assunto da MISURARE in OOC, non da credere: se le LUT
  % restassero ~10846 come SP3, il tool non avrebbe condiviso e #2a non avrebbe senso.)
  for j = 1:4
    add_block('built-in/Inport', [subM '/' in_names{j}], 'Port', num2str(j));
    add_line(subM, [in_names{j} '/1'], ['IIDM_CTRL/' num2str(j)]);
  end
  add_block('built-in/Outport', [subM '/accel'], 'Port', '1');
  add_line(subM, 'IIDM_CTRL/1', 'accel/1');
  fprintf('  costruito Donatello_ACC_IIDM_M (SP4-M-FSM #2a: 5 divisioni su 1 divide() condivisa)\n');

  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, libfile);
  close_system(lib, 0);
  fprintf(['OK: %d blocchi SELF-CONTAINED HDL-ready (time-mux, I/O fisico, no start/done)' ...
           ' + Donatello_ACC_IIDM (HDL-ready, catena completa) in %s.slx\n'], numel(names), lib);
end


function d = block_description(name, decodeNote)
%BLOCK_DESCRIPTION  Testo della Description del blocco (visibile in Block Properties in Simulink).
%  Registro impersonale: descrive funzione, interfaccia, vincoli d'uso e limiti noti.
  L = {
    sprintf('%s - SNN car-following (champion Donatello), architettura B2 time-multiplexata.', name)
    ''
    'FUNZIONE'
    '  Stima i 5 parametri IDM del veicolo osservato a partire dallo stato di car-following.'
    ''
    'INGRESSI (grandezze fisiche)'
    '  s    [m]    spaziatura dal veicolo che precede'
    '  v    [m/s]  velocita'' del veicolo'
    '  dv   [m/s]  velocita'' relativa (v - v_l); saturata internamente a +-20'
    '  v_l  [m/s]  velocita'' del veicolo che precede'
    ''
    'USCITE (parametri IDM stimati)'
    '  v0 [m/s]  ·  T [s]  ·  s0 [m]  ·  a [m/s^2]  ·  b [m/s^2]'
    ''
    'TIPI DI DATO (vincolo)'
    '  Gli ingressi devono essere fixed-point con ALMENO 20 bit frazionari, ad esempio'
    '  fixdt(1,32,20). Il tipo double NON e'' ammesso: non e'' sintetizzabile e il blocco non'
    '  compila. Per sorgenti in double (es. le traiettorie di test_dataset.mat) interporre un'
    '  blocco "Data Type Conversion". Con meno di 20 bit frazionari il blocco funziona ma non'
    '  e'' bit-exact rispetto al riferimento software (la normalizzazione devia di 1 LSB circa'
    '  1 volta ogni 25 campioni, il che fa cambiare uno spike).'
    ''
    'SEMANTICA: 1 campione = 1 inferenza'
    '  Una inferenza viene avviata a ogni cambio degli ingressi (edge-triggered). Il blocco non'
    '  espone start/done. Le uscite mantengono l''ultimo valore calcolato fino all''inferenza'
    '  successiva.'
    ''
    'VINCOLO DI RATE'
    '  L''architettura time-multiplexata elabora un neurone per clock: una inferenza richiede'
    '  circa 341 campioni. Ogni ingresso va quindi mantenuto per almeno 341 passi di simulazione.'
    '  Il valore esatto e'' irrilevante: qualunque durata >= 341 e'' corretta. Sull''FPGA il vincolo'
    '  e'' soddisfatto con ampio margine (un control-step da 0.1 s dura 800.000 clock e l''inferenza'
    '  ne usa 341, pari allo 0,04%).'
    ''
    'LIMITE NOTO'
    '  Se due campioni consecutivi hanno tutti e quattro gli ingressi bit-identici, il cambio non'
    '  viene rilevato e una inferenza viene saltata.'
    ''
    'IMPLEMENTAZIONE'
    ['  ' decodeNote]
    '  Il forward e'' il B2 time-multiplexato, identico all''architettura del bitstream PYNQ-Z1.'
    '  Il blocco e'' SELF-CONTAINED: non richiede alcun file .m esterno. HDL Coder genera il VHDL'
    '  direttamente dal blocco (architettura time-mux, con DualPortRAM).'
    ''
    'VERIFICHE'
    '  run_block_hdl_gate   - copia il solo .slx in una cartella isolata, rimuove matlab/ dal path'
    '                         e lancia makehdl: dimostra che il VHDL si genera su un altro PC.'
    '  run_block_traj_test  - pilota il blocco con le traiettorie di test_dataset.mat e verifica'
    '                         che i parametri coincidano con il riferimento (dmax = 0).'
    ''
    'RIFERIMENTI'
    '  document/HDL_PHASE.md         §3.1 contratto d''interfaccia, §3.1.4 edge-trigger e rate'
    '  document/DECODE_LUT_SWEEP.md  §6 blocchi e verifiche'
    '  Rigenerazione: build_hdl_variants.m (NON modificare la chart a mano)'
  };
  d = strjoin(L, newline);
end


function code = chart_code(decodeCall, srcDecode, srcRom, srcTypes, srcFsm, nrm)
%CHART_CODE  Testo della chart: main + normalize locale + i sorgenti VERI come funzioni locali.
  Lmain = {
    'function [v0, T, s0, a, b] = SNN(s, v, dv, v_l)'
    '%#codegen'
    '% Donatello TIME-MUX (l''architettura del bitstream) - SELF-CONTAINED: zero dipendenze .m.'
    '%  I/O FISICO (fixed): s,v,dv,v_l -> v0,T,s0,a,b.  NIENTE start/done: FSM pilotata internamente.'
    '%  ~341 clock/inferenza (1 neurone/clock) -> i params si aggiornano ogni ~341 passi.'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent pv xprev started'
    '  if isempty(started)'
    '    pv = fi(zeros(5,1), 1, 21, 13);'
    '    xprev = xn; started = true;'
    '    go = true;                       % 1a inferenza all''avvio'
    '  else'
    '    % EDGE-TRIGGERED sul cambio d''ingresso: 1 campione = 1 inferenza, per QUALUNQUE hold >= 341'
    '    % clock. (Free-running sarebbe sbagliato: con hold>341 farebbe piu'' inferenze sullo stesso'
    '    %  ingresso e lo stato evolverebbe troppo in fretta.)'
    '    go = any(xn ~= xprev);'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    ['    pv = ' decodeCall ';']
    '  end'
    '  v0 = pv(1); T = pv(2); s0 = pv(3); a = pv(4); b = pv(5);'
    'end'
  };
  L = [Lmain(:); {''}; normalize_code(nrm); {''}; inlined_header()];
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm newline newline srcDecode];
end


function L = normalize_code(nrm)
%NORMALIZE_CODE  Righe della funzione locale `local_normalize` (fisico -> xn fixed).
%  UNICA fonte, condivisa da chart_code (blocchi HDL-ready) e da acciidm_chart_code (SP2):
%  duplicarla farebbe divergere i blocchi in silenzio alla prima modifica dei reciproci.
  M = @(x) sprintf('%.17g', x);
  L = {
    'function xn = local_normalize(s, v, dv, v_l, T)'
    '%LOCAL_NORMALIZE  fisico -> xn (fixed). Nel deployato la normalize gira in SW float e all''HDL'
    '%  arriva gia'' xn (HDL_PHASE §3.1); qui sta nel blocco per avere I/O fisico.'
    '%  RECIPROCI a Q?.30 (NON Q?.20): verificato che con Q?.20 l''arrotondamento di xn devia di 1 LSB'
    '%  dal path float ~1 volta su 25 step -> uno spike flippa -> i params divergono. Con Q?.30 e'
    '%  ingressi con >=20 bit frazionari, xn e'' IDENTICO al riferimento float (0 diff).'
    ['  invS   = fi(' M(1/nrm(1))      ', 1, 34, 30);']
    ['  invV   = fi(' M(1/nrm(2))      ', 1, 34, 30);']
    ['  inv2DV = fi(' M(1/(2*nrm(3)))  ', 1, 34, 30);']
    ['  invVL  = fi(' M(1/nrm(4))      ', 1, 34, 30);']
    ['  DVc    = fi(' M(nrm(3)) ', 1, 24, 13);   % 24-13-1 = 10 bit interi: DV=' M(nrm(3)) ' ci sta']
    '                                     % (con Q5.13/18bit saturerebbe a ~16 -> clamp sbagliato)'
    '  d = dv;                            % clamp a +-DV. NB: d(:) = ... per NON cambiare il tipo di d'
    '  if d >  DVc, d(:) =  DVc; end      %     (codegen: una variabile non puo'' cambiare tipo, HDL_PHASE §9)'
    '  if d < -DVc, d(:) = -DVc; end'
    '  xn = cast(zeros(4,1), ''like'', T.V);'
    '  xn(1) = cast(s * invS, ''like'', T.V);'
    '  xn(2) = cast(v * invV, ''like'', T.V);'
    '  xn(3) = cast((d + DVc) * inv2DV, ''like'', T.V);'
    '  xn(4) = cast(v_l * invVL, ''like'', T.V);'
    'end'
  };
  L = L(:);
end


function L = inlined_header()
%INLINED_HEADER  Intestazione della sezione dei sorgenti inlinati (condivisa dai due generatori).
  L = {
    '% ===================================================================================='
    '% Funzioni locali INLINATE dai sorgenti veri (build_hdl_variants le legge a build-time).'
    '% Le funzioni locali hanno precedenza sul path => il blocco e'' SELF-CONTAINED.'
    '% NON modificarle qui: si rigenerano con build_hdl_variants.'
    '% ===================================================================================='
  };
  L = L(:);
end


function code = acciidm_chart_code(N, srcRom, srcTypes, srcFsm, srcLut, srcIidm, srcAccT, nrm)
%ACCIIDM_CHART_CODE  SP2: SNN LUT-N (fixed) + ACC-IIDM open-loop (double), gated sul refresh param.
  Lmain = {
    'function accel = SNN_ACC(s, v, dv, v_l)'
    '%#codegen'
    '% SP2 - campione Donatello + ACC-IIDM open-loop. ENTRAMBI in fixed -> HDL-ready.'
    '%  Ingressi FIXED (>=20 bit frazionari); uscita accel (double). 1 cambio d''ingresso = 1'
    '%  control-step = DT 0.1 s; ogni ingresso va tenuto >=341 campioni (time-mux).'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent pv xprev started acc'
    '  if isempty(started)                % isempty(<persistent>) e'' l''unica forma che il codegen'
    '    pv = fi(zeros(5,1), 1, 21, 13);  % riconosce come prova di definizione: un test sul VALORE'
    '    xprev = xn; started = true;      % fallirebbe con "undefined on some execution paths".'
    '    Ta = acc_types(''fixed''); acc = cast(0, ''like'', Ta.out); go = true;'
    '  else'
    '    go = any(xn ~= xprev);           % edge-triggered: 1 campione = 1 inferenza'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    ['    pv = snn_decode_lut(raw, ' num2str(N) ');']
    '    % ⚠️ L''IIDM gira SOLO qui: una volta per control-step. A ogni clock vedrebbe Δv_l = 0 per'
    '    %    340 campioni su 341 -> il filtro OU stimerebbe a_l ~ 0, in silenzio (spec §5).'
    '    acc = acc_iidm_open(s, v, dv, v_l, pv(:), false, acc_types(''fixed''));'
    '  end'
    '  accel = acc;                       % tenuto fino al control-step successivo'
    'end'
  };
  L = [Lmain(:); {''}; normalize_code(nrm); {''}; inlined_header()];
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm ...
          newline newline srcLut newline newline srcIidm newline newline srcAccT];
end


function d = acciidm_description(N)
%ACCIIDM_DESCRIPTION  Description del blocco SP2 (visibile in Block Properties in Simulink).
  L = {
    sprintf('Donatello_ACC_IIDM - campione Donatello (LUT-%d) + modello ACC-IIDM open-loop.', N)
    ''
    'HDL-READY dal 2026-07-16 (SP3): HDL Coder genera il VHDL dal solo .slx, con DualPortRAM (cioe'''
    '   l''architettura time-mux del deployato). Fino a quella data l''IIDM girava in double e HDL'
    '   Coder rifiutava il blocco con 14 errori; ora l''IIDM e'' fixed-point (acc_types, Q10.8).'
    '   Non servirono LUT: sqrt/tanh/x^4 sono NATIVI in HDL Coder e la divisione passa con'
    '   RoundingMethod ''Zero''. Cancello: run_block_hdl_gate.'
    ''
    '⚠️ HDL-READY NON VUOL DIRE DEPLOYATO: il bitstream PYNQ-Z1 resta la sola SNN. Questo blocco da'''
    '   il costo in silicio del controllore COMPLETO (rete + legge di controllo), che e'' cio'' che si'
    '   confronta con un MPC. Dettagli: document/SP3_ACC_IIDM_HDL.md.'
    ''
    'FUNZIONE'
    '  Catena completa stato -> azione: la SNN stima i 5 parametri IDM, il modello ACC-IIDM li usa'
    '  per calcolare l''accelerazione. Serve a testare la rete dentro un modello di car-following.'
    ''
    'INGRESSI (fisici, fixed con >=20 bit frazionari - interporre un Data Type Conversion)'
    '  s [m] · v [m/s] · dv [m/s] (= v - v_l) · v_l [m/s]'
    'USCITA'
    '  accel [m/s^2]'
    ''
    'LOOP APERTO'
    '  Il blocco NON integra v ne'' s: li riceve. Il loop lo chiude il sistema che testa (la velocita'''
    '  effettiva puo'' essere alterata a valle). L''unico stato interno e'' il filtro OU che stima a_l.'
    ''
    'SEMANTICA E RATE'
    '  1 cambio d''ingresso = 1 control-step = DT 0.1 s. Ogni ingresso va tenuto per almeno ~341'
    '  campioni (la SNN e'' time-multiplexata: 1 neurone/clock). L''IIDM gira una volta per'
    '  control-step, quando i parametri si rinfrescano.'
    ''
    'RIFERIMENTI'
    '  docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md · document/SP2_ACC_IIDM.md'
    '  Rigenerazione: build_hdl_variants.m (NON modificare la chart a mano)'
  };
  d = strjoin(L, newline);
end


function code = acciidm_m_chart_code(N, srcRom, srcTypes, srcFsm, srcLut, srcAccT, srcFDiv, srcPrep, srcNd, srcUse, srcTanh, srcFinal, nrm)
%ACCIIDM_M_CHART_CODE  SP4-M-FSM: chart del blocco M. Macro-FSM:
%    IDLE -(edge-trigger)-> SNN (time-mux ~341 clk) -(valid)-> decode + iidm_prep
%      -> per k=1..5 { iidm_nd(k) -> emetti (num,den,vin) -> attendi vout -> iidm_use(k,quot) }
%      -> iidm_final -> accel, torna IDLE.
%  Le funzioni-fase sono INLINATE dai sorgenti VERI (single source col model acc_iidm_fsm, che G2 valida
%  a dmax=0 su 60000 control-step): la chart NON ricalcola la matematica -> non puo' divergere (§2.1).
  Lmain = {
    'function accel = IIDM_CTRL(s, v, dv, v_l)'
    '%#codegen'
    '% SP4-M-FSM #2a - Donatello + ACC-IIDM con le 5 divisioni sequenziate su UNA divide() condivisa.'
    '%  UNA sola chiamata a fsm_div in tutto il sorgente, dentro uno stato della FSM -> HDL Coder genera'
    '%  UN divisore, riusato in 5 cicli. `kdiv` e'' STATO, non indice di loop: un `for k=1:5` verrebbe'
    '%  SROTOLATO dal codegen -> 5 divisori (giusto nel model acc_iidm_fsm, LETALE qui).'
    '%  Nessun blocco accanto alla chart -> niente conversione MATLAB-to-dataflow -> tanh fixed NATIVA:'
    '%  e'' cio'' che ha ucciso #1 (blocco Divide esterno) -- HDL_PHASE §9.'
    '%  La matematica NON e'' qui: sta in iidm_prep/iidm_nd/iidm_use/iidm_final, le STESSE del model'
    '%  acc_iidm_fsm (G2: dmax=0 su 60000 control-step). Qui c''e'' solo l''orchestrazione.'
    '%'
    '%  UNO STADIO PER CICLO (misurato: la prima versione faceva decode+prep in un ciclo e nd+div+use in'
    '%  un altro -> path critico 701 livelli, Fmax 2,85 MHz, timing non chiuso). Il time-mux della FSM'
    '%  taglia l''AREA; l''Fmax la da'' il REGISTRO fra gli stadi: ogni fase fa UNA cosa e latcha il'
    '%  risultato, cosi'' il path piu'' lungo e'' al massimo quello di uno stadio (la divisione).'
    '  Tt = snn_types(''fixed'', 13);'
    '  Ta = acc_types(''fixed'');'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  % alf/vlp (stato del filtro OU) vivono QUI, nel top-level: HDL Coder vieta i persistent in una'
    '  % funzione non-entry-point chiamata in un condizionale, e iidm_prep e'' chiamata in due rami.'
    '  persistent pv xprev started acc phase kdiv st alf vlp rawl numl denl ql thl'
    '  if isempty(started)'
    '    pv = fi(zeros(5,1), 1, 21, 13);'
    '    xprev = xn; started = true;'
    '    acc = cast(0, ''like'', Ta.out);'
    '    phase = uint8(0); kdiv = uint8(1);'
    '    alf = cast(0, ''like'', Ta.acc); vlp = cast(v_l, ''like'', Ta.st);'
    '    % `pv(:)` (fi) e NON zeros(5,1) (double): due tipi diversi di `p` darebbero DUE specializzazioni'
    '    % di iidm_prep, in silenzio.'
    '    [st, alf, vlp] = iidm_prep(s, v, dv, v_l, pv(:), true, alf, vlp);'
    '    rawl = fi(zeros(5,1), 1, 21, 13);   % latch del readout SNN: spezza il path SNN -> decode'
    '    numl = cast(0, ''like'', Ta.acc); denl = cast(1, ''like'', Ta.acc); ql = cast(0, ''like'', Ta.acc);'
    '    % thl col TIPO NATIVO di tanh (NON cast a Ta.acc: butterebbe i bit frazionari del tanh prima'
    '    % del prodotto con bf -> bug §2.1). Il tipo lo da'' tanh stesso su un argomento di tipo Ta.acc.'
    '    thl = tanh(cast(0, ''like'', Ta.acc));'
    '    go = true;'
    '  else'
    '    go = any(xn ~= xprev);             % edge-triggered: 1 campione = 1 inferenza (§3.1.4)'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    '    rawl(:) = raw;                     % LATCH e basta: il decode e'' il ciclo dopo'
    '    phase = uint8(1);'
    '  end'
    '  if phase == 1                        % DECODE (un ciclo a se'')'
    ['    pv = snn_decode_lut(rawl, ' num2str(N) ');']
    '    phase = uint8(2);'
    '  elseif phase == 2                    % PREP (un ciclo a se'': guardie, sqrt, filtro OU)'
    '    [st, alf, vlp] = iidm_prep(s, v, dv, v_l, pv(:), false, alf, vlp);   % 1 volta per control-step (§5)'
    '    kdiv = uint8(1); phase = uint8(3);'
    '  elseif phase == 3                    % ND: SOLO gli operandi della divisione k'
    '    [numl, denl] = iidm_nd(kdiv, st);'
    '    phase = uint8(4);'
    '  elseif phase == 4                    % DIV: SOLO la divisione'
    '    ql = fsm_div(numl, denl);          % <== UNICA chiamata nel sorgente: UN divisore in HDL'
    '    phase = uint8(5);'
    '  elseif phase == 5                    % USE: SOLO il consumo del quoziente'
    '    st = iidm_use(kdiv, ql, st);'
    '    if kdiv >= 5'
    '      phase = uint8(6);'
    '    else'
    '      kdiv = kdiv + 1; phase = uint8(3);'
    '    end'
    '  elseif phase == 6                    % TANH: stadio a se'' -- era il PATH CRITICO (237 liv, 7,35 MHz)'
    '    thl(:) = iidm_tanh(st);'
    '    phase = uint8(7);'
    '  elseif phase == 7                    % FINAL: blend + clamp -> accel (tenuta fino al prossimo)'
    '    acc = iidm_final(st, thl);'
    '    phase = uint8(0);'
    '  end'
    '  accel = acc;'
    'end'
  };
  L = [Lmain(:); {''}; normalize_code(nrm); {''}; inlined_header()];
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm ...
          newline newline srcLut newline newline srcAccT newline newline srcFDiv ...
          newline newline srcPrep newline newline srcNd newline newline srcUse ...
          newline newline srcTanh newline newline srcFinal];
end


function d = acciidm_m_description(N)
%ACCIIDM_M_DESCRIPTION  Description del blocco SP4-M-FSM (visibile in Block Properties).
  L = {
    sprintf('Donatello_ACC_IIDM_M - Donatello (LUT-%d) + ACC-IIDM con le 5 divisioni SEQUENZIATE.', N)
    ''
    'COS''E'' (SP4-M-FSM #2a)'
    '  Variante di Donatello_ACC_IIDM: le 5 divisioni a divisore variabile dell''IIDM non sono piu'' 5'
    '  divisori combinatori INCATENATI (1077 livelli logici, Fmax 2,0 MHz), ma UNA sola divide()'
    '  riusata da una macchina a stati -- una divisione per ciclo. Scopo: TAGLIARE L''AREA tenendo'
    '  dmax=0. Il path critico resta una divisione combinatoria: questo blocco NON punta agli 11,65 MHz'
    '  (per quelli servirebbe un divisore sequenziale, studio #2b: SP4_ACC_IIDM_FAST.md).'
    ''
    'BIT-IDENTICO A Donatello_ACC_IIDM (SP3)'
    '  La matematica e'' la stessa, solo distribuita nel tempo: nessuna approssimazione. Garantito da'
    '  tre cancelli sul dataset intero:'
    '    G1  il blocco Divide (ShiftAdd, RndMeth Zero, Q10.8) e'' bit-identico a divide() di SP3'
    '        -> dmax=0 su 300.000 coppie (num,den) reali; sensibile (RndMeth Nearest -> 1 LSB).'
    '    G2  le funzioni-fase (iidm_prep/nd/use/final) == acc_iidm_open -> dmax=0 su 60.000/60.000'
    '        control-step; sensibile (q2 al posto di q3 -> 1990/2000 divergenti).'
    '    G3  questo blocco == il model acc_iidm_fsm (run_block_acciidm_m_test).'
    ''
    'INGRESSI (fisici, fixed con >=20 bit frazionari - interporre un Data Type Conversion)'
    '  s [m] · v [m/s] · dv [m/s] (= v - v_l) · v_l [m/s]'
    'USCITA'
    '  accel [m/s^2]'
    ''
    '⚠️ VINCOLO DI RATE (DIVERSO da Donatello_ACC_IIDM)'
    '  Una inferenza costa la SNN time-mux (~341 clock) PIU'' 5 cicli, uno per divisione. Ogni ingresso'
    '  va quindi tenuto per PIU'' campioni che nel blocco SP3 (~341): il valore esatto lo MISURA'
    '  run_block_acciidm_m_test (non e'' assunto). Sull''FPGA e'' irrilevante: un control-step da 0,1 s'
    '  dura 800.000 clock a 8 MHz.'
    ''
    'SEMANTICA'
    '  1 cambio d''ingresso = 1 inferenza (edge-triggered, niente start/done esposti: uno start'
    '  scollegato sarebbe un fallimento SILENZIOSO -- HDL_PHASE §3.1.2). Le uscite mantengono l''ultimo'
    '  valore fino all''inferenza successiva.'
    ''
    'RIFERIMENTI'
    '  docs/superpowers/specs/2026-07-16-acc-iidm-fsm-design.md · document/SP4_ACC_IIDM_FAST.md'
    '  Rigenerazione: build_hdl_variants.m (NON modificare la chart a mano)'
  };
  d = strjoin(L, newline);
end
