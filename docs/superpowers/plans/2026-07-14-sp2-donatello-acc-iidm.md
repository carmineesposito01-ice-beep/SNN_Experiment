# SP2 — `Donatello_ACC_IIDM` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere a `snn_champions_lib.slx` il blocco **`Donatello_ACC_IIDM`** (`s,v,dv,v_l → accel`): campione Donatello **LUT-64** + modello **ACC-IIDM open-loop**, plug&play, di **sola simulazione**.

**Architecture:** la matematica dell'IIDM viene **estratta** dal plant esistente in `acc_iidm_open.m` (funzione unica, open-loop) e il plant closed-loop viene **rifattorizzato per usarla** → il cancello esistente `run_plant_parity` (vs golden Python) **dimostra che l'estrazione è fedele**, senza secondo riferimento e senza due copie che divergono. Il blocco inlina i sorgenti veri come funzioni locali (stesso schema dei `Donatello_*`).

**Tech Stack:** MATLAB R2026a (Fixed-Point Designer, `fi`), Simulink (libreria), MEX (`snn_traj_fixed_r16_mex`). Spec: `docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`.

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"`.
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, NON toccarli nei `git add`**: `closed_loop_demo.slx`, `slblocks.m`, `axi/build/phase_b/results.csv`.
- **Verifiche sul DATASET, mai su un caso singolo** (regola utente 2026-07-14): riportare sempre *quanti su quanti*.
- **Cancelli che devono restare verdi**: `run_plant_parity` · `run_b2_parity_dataset('Donatello')` · `run_block_sync_check` · `run_block_traj_test`.

## File Structure
```
matlab/acc_iidm_open.m           # NUOVO — ACC-IIDM open-loop: accel = f(s,v,dv,v_l,p). NON integra. Unica fonte della matematica IIDM.
matlab/build_plant_lib.m         # MODIFICA — il plant closed-loop usa acc_iidm_open + integrazione (single source)
matlab/build_hdl_variants.m      # MODIFICA — aggiunge il blocco Donatello_ACC_IIDM
matlab/run_block_acciidm_test.m  # NUOVO — verifica sul dataset: blocco vs riferimento, dmax=0 (+ prova che il test ha potere)
matlab/run_block_sync_check.m    # MODIFICA — include acc_iidm_open fra i sorgenti inlinati da controllare
matlab/snn_champions_lib.slx     # rigenerato
matlab/cf_plant_lib.slx          # rigenerato
document/SP2_ACC_IIDM.md         # NUOVO — doc di processo del blocco (SP2 non e' piu' "lo studio della LUT")
```

---

## Task 1: `acc_iidm_open` — la matematica IIDM, open-loop

**Files:** Create `matlab/acc_iidm_open.m`

Estrazione **verbatim** della parte `acc_iidm_accel` da `build_plant_lib.m:plant_code()` (righe 55-77), togliendo l'integrazione e prendendo `s,v,dv` dagli ingressi. Il filtro OU di `a_l` resta (è il controllore ACC, non il loop del veicolo).

- [ ] **Step 1: scrivi `matlab/acc_iidm_open.m`**

```matlab
function accel = acc_iidm_open(s, v, dv, v_l, p, rst) %#codegen
%ACC_IIDM_OPEN  ACC-IIDM **open-loop**: accel = f(stato, parametri). NON integra v ne' s.
%  s, v, dv, v_l : stato fornito DA FUORI (il loop lo chiude il sistema che testa)
%  p             : [v0; T; s0; a; b]
%  rst           : true -> azzera lo stato del filtro OU (inizio di una nuova traiettoria)
%
%  E' l'UNICA fonte della matematica ACC-IIDM del progetto: la usa sia questo blocco sia il plant
%  closed-loop `cf_plant_lib/ACC_IIDM` (che aggiunge solo l'integrazione). Cancello che lo verifica:
%  `run_plant_parity` (vs golden Python).
%
%  ⚠️ DA CHIAMARE **UNA VOLTA PER CONTROL-STEP** (DT = 0.1 s): il filtro OU stima a_l da Δv_l/DT.
%     Chiamarla a ogni clock farebbe vedere Δv_l = 0 per 340 campioni su 341 -> a_l ~ 0, in silenzio.
%     Vedi docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md §5.
  DT = 0.1; ALPHA = exp(-DT/1.0); COOL = 0.99;
  v0 = max(p(1), 1e-3); T = max(p(2), 1e-3); s0 = p(3); a = max(p(4), 1e-3); b = max(p(5), 1e-3);

  persistent alf vlp started
  if isempty(started), started = false; end
  if ~started || rst
    alf = 0; vlp = v_l; started = true;
  end
  % stima a_l (filtro OU su differenze finite del leader)
  alf = ALPHA*alf + (1-ALPHA)*((v_l - vlp)/DT); vlp = v_l;

  % --- acc_iidm_accel: IIDM base + CAH + blend ACC (verbatim da build_plant_lib:plant_code) ---
  sab = max(sqrt(a*b), 1e-6);
  s_star = s0 + max(v*T + v*dv/(2*sab), 0);
  s_safe = max(s, 2.0);
  v_free = a*(1 - min(v/v0, 10)^4);
  z = min(s_star/s_safe, 20);
  below = (v <= v0);
  a_z = a*(1 - z^2);
  if z < 1
    if below, a_iidm = v_free*(1 - z^2); else, a_iidm = v_free; end
  else
    if below, a_iidm = a_z; else, a_iidm = v_free + a_z; end
  end
  a_l_bar = min(alf, a);
  a_cah = a_l_bar - max(dv,0)^2/(2*s_safe + 1e-6);
  a_cah = min(max(a_cah, -9), a);
  dd = (a_iidm - a_cah)/(b + 1e-6);
  a_blend = (1-COOL)*a_iidm + COOL*(a_cah + b*tanh(dd));
  if a_iidm >= a_cah, accel = a_iidm; else, accel = a_blend; end
  accel = min(max(accel, -9), a);
end
```

- [ ] **Step 2: verifica che compili e dia un numero plausibile**

Run: `matlab -batch "cd('<matlabdir>'); a = acc_iidm_open(30, 20, 2, 18, [30;1.5;2;1.5;2], true); fprintf('accel = %.4f\n', a); assert(a >= -9 && a <= 1.5)"`
Expected: `accel = <valore in [-9, 1.5]>`, nessun errore.

- [ ] **Step 3: Commit**

```bash
git add matlab/acc_iidm_open.m
git commit -m "feat(sp2): acc_iidm_open - ACC-IIDM open-loop (accel=f(stato,params), niente integrazione)"
```

---

## Task 2: il plant esistente usa `acc_iidm_open` (single source) — **il cancello prova l'estrazione**

**Files:** Modify `matlab/build_plant_lib.m` (funzione `plant_code`), rigenera `matlab/cf_plant_lib.slx`

Se il plant closed-loop e il blocco SP2 avessero **due copie** della matematica IIDM, divergerebbero (è successo con l'FSM inlinata: `HDL_PHASE.md` §2.1). Qui il plant diventa **`acc_iidm_open` + integrazione**, e `run_plant_parity` (vs golden Python) diventa la prova che l'estrazione del Task 1 è fedele.

- [ ] **Step 1: fai girare il cancello PRIMA di toccare (baseline)**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity"`
Expected: passa (nessun errore). **Annota l'output**: è la baseline da riprodurre esattamente.

- [ ] **Step 2: sostituisci `plant_code()` in `build_plant_lib.m`**

Il testo generato diventa (la chart inlina `acc_iidm_open` come funzione locale, letta a build-time):

```matlab
function code = plant_code()
%PLANT_CODE  Testo della MATLAB Function ACC-IIDM closed-loop = acc_iidm_open + integrazione.
%  La matematica NON e' duplicata qui: acc_iidm_open.m viene letto a build-time e inlinato come
%  funzione locale (le locali hanno precedenza sul path -> blocco self-contained, zero deriva).
  here = fileparts(mfilename('fullpath'));
  src = fileread(fullfile(here, 'acc_iidm_open.m'));
  L = {
    'function out = PLANT(in)'
    '%#codegen'
    '% Plant ACC-IIDM self-contained. in=[v_l;v0;T;s0;a;b] (6x1), out=[s;v;accel] (3x1).'
    '% accel = acc_iidm_open(...) (UNICA fonte della matematica IIDM) + integrazione balistica.'
    '  DT = 0.1; NORM_S_MAX = 150;'
    '  vl = in(1); v0 = max(in(2),1e-3); T = max(in(3),1e-3);'
    '  s0 = in(4); a = max(in(5),1e-3); b = max(in(6),1e-3);'
    '  persistent s v started'
    '  if isempty(started), started = false; end'
    '  rst = ~started;'
    '  if ~started'
    '    v = 0.8*v0; s = s0 + v*T; started = true;'
    '  end'
    '  dv = v - vl;'
    '  accel = acc_iidm_open(s, v, dv, vl, [v0; T; s0; a; b], rst);'
    '  % --- integrazione balistica (s usa la v vecchia) ---'
    '  v_old = v;'
    '  v = min(max(v + accel*DT, 0), 1.2*v0);'
    '  s = min(max(s + (vl - v_old)*DT, 0.5*s0), NORM_S_MAX);'
    '  out = [s; v; accel];'
    'end'
    ''
    '% ==== funzione locale INLINATA dal sorgente vero (build_plant_lib la legge a build-time) ===='
  };
  code = [strjoin(L, newline) newline newline src];
end
```

- [ ] **Step 3: rigenera la libreria plant e rilancia il cancello**

Run: `matlab -batch "cd('<matlabdir>'); build_plant_lib; clear PLANT acc_iidm_open; run_plant_parity"`
Expected: **stesso esito della baseline dello Step 1**. Se cambia anche di poco → l'estrazione NON è fedele: fermarsi e confrontare `acc_iidm_open` con le righe 55-77 della vecchia `plant_code`, **non** aggiustare le tolleranze.

- [ ] **Step 4: Commit**

```bash
git add matlab/build_plant_lib.m matlab/cf_plant_lib.slx
git commit -m "refactor(plant): ACC_IIDM closed-loop = acc_iidm_open + integrazione (single source, niente matematica duplicata); run_plant_parity invariato"
```

---

## Task 3: il blocco `Donatello_ACC_IIDM`

**Files:** Modify `matlab/build_hdl_variants.m`; rigenera `matlab/snn_champions_lib.slx`

Blocco unico: SNN LUT-64 (fixed, edge-triggered) + IIDM open-loop (double) **gated sul refresh dei parametri**.

- [ ] **Step 1: in `build_hdl_variants.m`, leggi anche il sorgente dell'IIDM**

Dopo `srcHdl = fileread(fullfile(here, 'snn_decode_hdl.m'));` aggiungi:

```matlab
  srcIidm = fileread(fullfile(here, 'acc_iidm_open.m'));   % SP2: matematica IIDM (single source)
```

- [ ] **Step 2: aggiungi la costruzione del blocco, in fondo al `for` dei blocchi (prima di `set_param(lib, 'EnableLBRepository', 'on')`)**

```matlab
  % ---- SP2: blocco unico campione + plant ACC-IIDM open-loop (SOLA SIMULAZIONE) ----
  sub = [lib '/Donatello_ACC_IIDM'];
  if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position', [300, 30, 500, 70], ...
            'Description', acciidm_description());
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN_ACC']);
  chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN_ACC']);
  chart.Script = acciidm_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcIidm, nrm);
  for j = 1:4
    add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
    add_line(sub, [in_names{j} '/1'], ['SNN_ACC/' num2str(j)]);
  end
  add_block('built-in/Outport', [sub '/accel'], 'Port', '1');
  add_line(sub, 'SNN_ACC/1', 'accel/1');
  fprintf('  costruito Donatello_ACC_IIDM (SP2, sola simulazione)\n');
```

- [ ] **Step 3: aggiungi le due funzioni locali in fondo a `build_hdl_variants.m`**

```matlab
function code = acciidm_chart_code(N, srcRom, srcTypes, srcFsm, srcLut, srcIidm, nrm)
%ACCIIDM_CHART_CODE  SP2: SNN LUT-N (fixed) + ACC-IIDM open-loop (double), gated sul refresh param.
  M = @(x) sprintf('%.17g', x);
  L = {
    'function accel = SNN_ACC(s, v, dv, v_l)'
    '%#codegen'
    '% SP2 - campione Donatello + ACC-IIDM open-loop. SOLA SIMULAZIONE (mescola fixed e double).'
    '%  Ingressi FIXED (>=20 bit frazionari); uscita accel (double). 1 cambio d''ingresso = 1'
    '%  control-step = DT 0.1 s; ogni ingresso va tenuto >=341 campioni (time-mux).'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent pv xprev started acc'
    '  if isempty(started)'
    '    pv = fi(zeros(5,1), 1, 21, 13); xprev = xn; started = true; acc = 0;'
    '    go = true;'
    '  else'
    '    go = any(xn ~= xprev);          % edge-triggered: 1 campione = 1 inferenza'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    ['    pv = snn_decode_lut(raw, ' num2str(N) ');']
    '    % ⚠️ L''IIDM gira SOLO qui: una volta per control-step. A ogni clock vedrebbe dv_l = 0 per'
    '    %    340 campioni su 341 -> il filtro OU stimerebbe a_l ~ 0, in silenzio (spec §5).'
    '    acc = acc_iidm_open(double(s), double(v), double(dv), double(v_l), double(pv(:)), false);'
    '  end'
    '  accel = acc;                      % tenuto fino al control-step successivo'
    'end'
    ''
    'function xn = local_normalize(s, v, dv, v_l, T)'
    ['  invS   = fi(' M(1/nrm(1))     ', 1, 34, 30);']
    ['  invV   = fi(' M(1/nrm(2))     ', 1, 34, 30);']
    ['  inv2DV = fi(' M(1/(2*nrm(3))) ', 1, 34, 30);']
    ['  invVL  = fi(' M(1/nrm(4))     ', 1, 34, 30);']
    ['  DVc    = fi(' M(nrm(3))       ', 1, 24, 13);']
    '  d = dv;'
    '  if d >  DVc, d(:) =  DVc; end'
    '  if d < -DVc, d(:) = -DVc; end'
    '  xn = cast(zeros(4,1), ''like'', T.V);'
    '  xn(1) = cast(s * invS, ''like'', T.V);'
    '  xn(2) = cast(v * invV, ''like'', T.V);'
    '  xn(3) = cast((d + DVc) * inv2DV, ''like'', T.V);'
    '  xn(4) = cast(v_l * invVL, ''like'', T.V);'
    'end'
    ''
    '% ==== funzioni locali INLINATE dai sorgenti veri (lette a build-time) ===='
  };
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm ...
          newline newline srcLut newline newline srcIidm];
end

function d = acciidm_description()
  L = {
    'Donatello_ACC_IIDM - campione Donatello (LUT-64) + modello ACC-IIDM open-loop.'
    ''
    '⚠️ BLOCCO DI SOLA SIMULAZIONE: NON e'' sintetizzabile (mescola la SNN in fixed con l''IIDM in'
    '   double). L''artefatto HDL-ready e'' Donatello_Champion.'
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
```

- [ ] **Step 4: rigenera e verifica che il blocco esista e simuli**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; load_system('snn_champions_lib'); disp(getSimulinkBlockHandle('snn_champions_lib/Donatello_ACC_IIDM') > 0); close_system('snn_champions_lib',0)"`
Expected: `1` (il blocco esiste), nessun errore di build.

- [ ] **Step 5: verifica che i cancelli esistenti NON siano rotti**

Run: `matlab -batch "cd('<matlabdir>'); run_block_sync_check; run_block_traj_test(10,'Donatello_Champion',400,1)"`
Expected: `BLOCCHI SINCRONIZZATI` + `dmax = 0`.

- [ ] **Step 6: Commit**

```bash
git add matlab/build_hdl_variants.m matlab/snn_champions_lib.slx
git commit -m "feat(sp2): blocco Donatello_ACC_IIDM (campione LUT-64 + ACC-IIDM open-loop, IIDM gated sul refresh param)"
```

---

## Task 4: verifica sul DATASET + **prova che il test ha potere**

**Files:** Create `matlab/run_block_acciidm_test.m`

Il criterio è `dmax = 0` sul dataset. Ma un test che non fallirebbe mai è inutile (lezione 2026-07-14: i cancelli storici stampavano e basta): quindi il test **si dimostra sensibile** al gating sbagliato prima di essere creduto.

- [ ] **Step 1: scrivi `matlab/run_block_acciidm_test.m`**

```matlab
function dmax = run_block_acciidm_test(K, trajIdx, hold)
%RUN_BLOCK_ACCIIDM_TEST  [SP2] Il blocco Donatello_ACC_IIDM riproduce la catena di riferimento?
%  Riferimento: MEX (normalize float + snn_core) -> snn_decode_lut(.,64) -> acc_iidm_open.
%  Blocco: la stessa catena dentro Simulink. Atteso: **dmax = 0** su ogni control-step.
%
%  Copre implicitamente il gating dell'IIDM (spec §5): se l'IIDM girasse a ogni clock, il filtro OU
%  vedrebbe dv_l = 0 per 340 campioni su 341, a_l -> ~0 e accel divergerebbe -> questo test fallisce.
  if nargin < 1 || isempty(K), K = 12; end
  if nargin < 2 || isempty(trajIdx), trajIdx = 1; end
  if nargin < 3 || isempty(hold), hold = 400; end       % qualunque valore >= latenza (~341)
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  W  = champ_weights(c); Tp = numerictype(1,21,13);
  val = double(tr{trajIdx}.val);

  % --- riferimento: stessa catena, in MATLAB ---
  Rmex = double(snn_traj_fixed_r16_mex(tr{trajIdx}.val, W));
  clear acc_iidm_open;
  a_ref = zeros(K,1);
  for k = 1:K
    p = double(snn_decode_lut(fi(Rmex(k,:).', Tp), 64));
    a_ref(k) = acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1);
  end

  % --- blocco ---
  P = drive_acciidm(val(:,1:K), hold, K*hold + 20);
  lat = 340;                                            % latenza del primo done (misurata)
  idx = hold * (0:K-1).' + lat + 1;
  idx = idx(idx <= size(P,1));
  a_blk = P(idx);
  n = min(numel(a_blk), K);
  assert(n == K, 'attesi %d aggiornamenti di accel, trovati %d', K, n);

  dmax = max(abs(a_blk(1:n) - a_ref(1:n)));
  fprintf('Donatello_ACC_IIDM traj=%d hold=%d su %d control-step: dmax(accel) = %.4g\n', ...
          trajIdx, hold, n, dmax);
  assert(dmax == 0, 'il blocco NON riproduce la catena di riferimento (dmax=%.4g)', dmax);
  fprintf('=== SP2 TEST PASSATO: catena bit-exact ===\n');
end

function A = drive_acciidm(seq, hold, stopT)
  K = size(seq,2);
  assignin('base', 'stim_sp2', [(0:K-1).'*hold, seq.']);
  mdl = 'sp2_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_ACC_IIDM', [mdl '/DUT']);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName', 'stim_sp2', ...
            'SampleTime','1', 'Interpolate','off', 'OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs','4');
  add_line(mdl, 'src/1', 'dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');       % >=20 bit frazionari (HDL_PHASE §3.1.3)
    add_line(mdl, ['dm/' num2str(j)], ['c' num2str(j) '/1']);
    add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace', [mdl '/Aw'], 'VariableName','Aw','SaveFormat','Array');
  add_line(mdl, 'DUT/1', 'Aw/1');
  set_param(mdl, 'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so = sim(mdl); A = double(so.get('Aw')); close_system(mdl, 0);
end
```

- [ ] **Step 2: esegui il test — deve passare**

Run: `matlab -batch "cd('<matlabdir>'); run_block_acciidm_test(12, 1, 400)"`
Expected: `dmax(accel) = 0` + `SP2 TEST PASSATO`.
Se `dmax > 0`: **non aggiustare la tolleranza**. Confronta la catena: (a) i params del blocco vs `snn_decode_lut(.,64)` sul raw del MEX (usa `run_block_traj_test(12,'Donatello_LUT64',400,1)` → deve dare 0); se quella passa, il difetto è nell'IIDM o nel gating.

- [ ] **Step 3: PROVA CHE IL TEST HA POTERE (mis-gating)**

Un test che non può fallire non è un test. Costruisci a mano una variante mis-gated e verifica che il test la **becchi**:

```matlab
% in una dir scratch: copia la chart del blocco e sposta la chiamata all'IIDM FUORI da `if valid`
% (cioe' facendola girare a ogni clock), rigenera solo quel blocco e rilancia il test.
```
Run: come Step 2, sulla variante mis-gated.
Expected: **il test FALLISCE** (`dmax > 0`, per a_l ≈ 0). Se passasse lo stesso, il test è cieco → va rafforzato prima di fidarsene.

- [ ] **Step 4: dataset — piu' traiettorie (regola: mai un caso singolo)**

Run: `matlab -batch "cd('<matlabdir>'); for t=[1 6 12 20 30], run_block_acciidm_test(12,t,400); end"`
Expected: `dmax(accel) = 0` su **tutte e 5**.

- [ ] **Step 5: Commit**

```bash
git add matlab/run_block_acciidm_test.m
git commit -m "test(sp2): run_block_acciidm_test - catena blocco vs riferimento sul dataset (dmax=0); verificato che becca il mis-gating dell'IIDM"
```

---

## Task 5: cancello di sincronia + documentazione

**Files:** Modify `matlab/run_block_sync_check.m`, `matlab/README.md`; Create `document/SP2_ACC_IIDM.md`

- [ ] **Step 1: `run_block_sync_check` deve coprire anche il nuovo sorgente**

In `matlab/run_block_sync_check.m` sostituisci la riga dei sorgenti:

```matlab
  srcs = {'snn_b2_fsm.m', 'snn_types.m', 'b2_rom_active.m'};   % inlinati in TUTTI i blocchi HDL-ready
```
con:
```matlab
  srcs = {'snn_b2_fsm.m', 'snn_types.m', 'b2_rom_active.m'};   % inlinati in TUTTI i blocchi HDL-ready
  srcSp2 = {'acc_iidm_open.m'};                                % in piu': solo in Donatello_ACC_IIDM (SP2)
```
e, dentro il `for` sui blocchi, dopo il calcolo di `stale`:
```matlab
    if contains(s, 'acc_iidm_open(')            % il blocco SP2 inlina anche l'IIDM
      for k = 1:numel(srcSp2)
        if ~contains(s, nrm(fileread(fullfile(here, srcSp2{k})))), stale{end+1} = srcSp2{k}; end %#ok<AGROW>
      end
    end
```
⚠️ La riga `if ~contains(s, 'snn_b2_fsm(xn, start)'), continue; end` **non** va cambiata: il blocco SP2 contiene comunque l'FSM, quindi viene controllato.

- [ ] **Step 2: esegui il cancello**

Run: `matlab -batch "cd('<matlabdir>'); run_block_sync_check"`
Expected: **8 blocchi controllati, 0 stale** (i 7 `Donatello_*` + `Donatello_ACC_IIDM`).

- [ ] **Step 3: crea `document/SP2_ACC_IIDM.md`**

```markdown
# SP2 — `Donatello_ACC_IIDM`: campione + plant ACC-IIDM open-loop

> Doc di processo del blocco. Spec: `docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`.

## Cos'e'
Blocco unico `s,v,dv,v_l → accel`: campione Donatello **LUT-64** (fixed, cycle-accurate) + **ACC-IIDM
open-loop** (double). **Sola simulazione: NON sintetizzabile** — l'artefatto HDL-ready resta `Donatello_Champion`.

## Interfaccia e uso
| | |
|---|---|
| Ingressi | `s, v, dv, v_l` fisici, **fixed con ≥20 bit frazionari** (Data Type Conversion **fuori**: se il blocco diventera' HDL-ready l'interfaccia non cambia) |
| Uscita | `accel` (double), tenuta fino al control-step successivo |
| Semantica | **1 cambio d'ingresso = 1 control-step = DT 0.1 s**; ogni ingresso tenuto **≥ ~341 campioni** |
| Loop | **aperto**: il blocco non integra `v` ne' `s` |

## Il punto critico: il gating dell'IIDM
`DT` sopravvive solo nel filtro OU che stima `a_l` (`alf = ALPHA*alf + (1-ALPHA)*(Δv_l/DT)`). L'IIDM gira
**una volta per control-step** (sul refresh dei parametri): a ogni clock vedrebbe `Δv_l = 0` per 340 campioni
su 341 → **`a_l ≈ 0`**, in silenzio. Il test `run_block_acciidm_test` e' stato verificato **sensibile** a questo
errore (una variante mis-gated lo fa fallire).

## Single source
La matematica ACC-IIDM sta **solo** in `matlab/acc_iidm_open.m`: la usano sia questo blocco sia il plant
closed-loop `cf_plant_lib/ACC_IIDM` (= open-loop + integrazione). Il cancello `run_plant_parity` (vs golden
Python) verifica entrambi. Niente copie che divergono (lezione: `HDL_PHASE.md` §2.1).

## Verifiche
| cancello | criterio |
|---|---|
| `run_block_acciidm_test(K, traj, hold)` | `dmax(accel) = 0` vs riferimento (MEX + decode-64 + `acc_iidm_open`) |
| `run_plant_parity` | plant closed-loop vs golden Python: invariato dopo il refactor |
| `run_block_sync_check` | il blocco inlina i sorgenti **attuali** (incluso `acc_iidm_open`) |

## Fuori scope
ACC-IIDM su FPGA (fixed): e' un SP a se' — `sqrt(a·b)` e le divisioni sono lo stesso genere di problema che
per la sigmoide ha richiesto una LUT. Chiudere il loop dentro il blocco. Altri champion, altri plant.
```

- [ ] **Step 4: aggiorna `matlab/README.md`** — nella sezione «Librerie Simulink», dopo la riga di `build_hdl_variants`, aggiungi:

```markdown
Il builder aggiunge anche **`Donatello_ACC_IIDM`** (SP2): campione LUT-64 + ACC-IIDM **open-loop**,
`s,v,dv,v_l → accel`. ⚠️ **Sola simulazione: NON sintetizzabile** (fixed + double). Doc: `../document/SP2_ACC_IIDM.md`.
```
e nella sezione «Test / verifica» aggiungi `run_block_acciidm_test.m` accanto agli altri cancelli nuovi.

- [ ] **Step 5: Commit + push**

```bash
git add matlab/run_block_sync_check.m matlab/README.md document/SP2_ACC_IIDM.md
git commit -m "docs(sp2): SP2_ACC_IIDM.md + README + sync check esteso ad acc_iidm_open"
git push origin Simulink_Importer
```

---

## Self-review (copertura della spec)
- **§3 decisioni** (LUT-64 · IIDM double · blocco unico · solo `accel` · ingressi fixed · loop aperto): Task 3. ✓
- **§4 design** (nome, collocazione, semantica, stato interno, sorgente dell'IIDM): Task 1 + Task 3. ✓
- **§5 gating**: Task 3 Step 2 (il codice) + Task 4 Step 3 (**la prova che il test lo becca**). ✓
- **§6 verifiche sul dataset**: Task 4 (dmax=0 su 5 traiettorie) · sync check: Task 5. ✓
  *Nota: la verifica «loop aperto = niente stato di velocita'» della spec §6 e' coperta strutturalmente (il blocco
  non ha `persistent` di `v`/`s`: si legge nella chart) e funzionalmente dal dmax=0 (il riferimento riceve lo stato
  da fuori). Non serve un test dedicato.*
- **§7 fuori scope**: dichiarato in `document/SP2_ACC_IIDM.md`. ✓
- **Realismo**: nessun Vivado in questo piano (il blocco non e' sintetizzabile per costruzione) → tutti i task sono
  eseguibili e verificabili in MATLAB/Simulink.
