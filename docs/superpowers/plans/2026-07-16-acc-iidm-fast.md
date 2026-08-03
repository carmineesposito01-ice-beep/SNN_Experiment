# SP4 — ACC-IIDM fast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** recuperare l'Fmax dell'ACC-IIDM in fixed (oggi 2,0 MHz, timing non chiude @8 MHz) a **≥ 11,65 MHz**
(pari alla SNN), sostituendo le 5 divisioni digit-recurrence combinatorie.

**Architecture:** studio A/B, **Variante L prima**. L = ogni `1/x` → `sqrt` nativa (dove serve) + **reciproco a
LUT 1-D** (i divisori sono limitati lontano da zero) + moltiplica; l'IIDM resta combinatorio in un clock. Il
reciproco-LUT **approssima** `1/x` → dimensione LUT scelta con uno **sweep vs budget** (come il decode). Questo
piano copre L end-to-end (fino alla sintesi OOC + decisione); **M (time-mux) avrà il suo piano** dopo i dati di L,
perché la sua struttura FSM dipende da cosa mostra la misura di L (in particolare se la `sqrt` residua è il collo).

**Tech Stack:** MATLAB R2026a · Fixed-Point Designer (`fi`, `coder.const`) · Stateflow · HDL Coder · Vivado
2026.1 (`C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`, `xc7z020clg400-1`).

**Spec:** `docs/superpowers/specs/2026-07-16-acc-iidm-fast-design.md`

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"`
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, MAI nei `git add`**: `closed_loop_demo.slx`, `slblocks.m`, `axi/build/phase_b/results.csv`.
- **Verifiche sul DATASET, mai su un caso singolo** (riportare *quanti su quanti*).
- **Cancelli che devono restare verdi**: `run_plant_parity` (il **double non si muove di un bit**) ·
  `run_block_acciidm_test` · `run_block_closed_loop_test` · `run_block_hdl_gate` · `run_block_sync_check`.
- **Gotcha già pagati (non ri-scoprirli):** la **fimath è parte del tipo** (nei prototipi di `acc_types`, non
  `setfimath` sparse) · **niente riassegnazione di tipo** (nomi nuovi, non `x = cast(x,…)`) ·
  `if isempty(<persistent>)` **letterale** · **no sovra-escape apici** nelle stringhe di chart (`''fixed''` non
  `''''fixed''''`) · il messaggio VERO di un errore di chart si ha estraendo lo script e dandolo a
  `codegen('-config:lib','SNN_ACC','-args',{a,a,a,a})` con `a = fi(0,1,32,20)` (Simulink mostra solo la
  propagazione).

## File Structure
```
matlab/acc_recip_lut.m           # NUOVO — reciproco 1/x via LUT 1-D a N punti su [lo,hi] + interp (modello: snn_decode_lut.m)
matlab/acc_types.m               # MODIFICA — campo recipN: 0 = divide() (SP3), >0 = reciproco-LUT a N punti (L)
matlab/acc_iidm_open.m           # MODIFICA — acc_div sceglie divide() o reciproco-LUT secondo T.recipN
matlab/run_acc_recip_sweep.m     # NUOVO — sweep dimensione LUT reciproco vs budget E_snn (come run_acc_fixed_sweep)
matlab/build_hdl_variants.m      # MODIFICA — blocco Donatello_ACC_IIDM_L (variante reciproco-LUT)
matlab/snn_champions_lib.slx     # rigenerato
document/SP4_ACC_IIDM_FAST.md    # NUOVO — doc di processo, tabella A/B coi numeri OOC, decisione
```

---

## Task 1: `acc_recip_lut` — il reciproco a LUT 1-D

**Files:** Create `matlab/acc_recip_lut.m`

Modello: `snn_decode_lut.m` (tabella `coder.const` + indice scalato + clamp + interp lineare). Qui la tabella è
`1/x` su `[lo,hi]`. `lo,hi,N` sono `coder.const` (il chiamante passa letterali) → HDL Coder ripiega la tabella.

- [ ] **Step 1: scrivi `matlab/acc_recip_lut.m`**

```matlab
function y = acc_recip_lut(x, lo, hi, N) %#codegen
%ACC_RECIP_LUT  1/x via LUT 1-D a N punti su [lo,hi) + interpolazione lineare. Modello: snn_decode_lut.
%  Per l'ACC-IIDM fixed (SP4 variante L): i divisori sono LIMITATI lontano da zero, quindi 1/x e' liscio
%  e limitato -> una LUT piccola basta. lo,hi,N sono coder.const (il chiamante passa letterali) e la
%  tabella e' coder.const -> HDL Coder la ripiega (nessuna divisione in hardware).
%  x fuori [lo,hi] viene saturato agli estremi (i range sono garantiti dai clamp dell'IIDM).
  Tx = numerictype(1, 24, 13);      % ingresso/uscita reciproco: 1/0.5=2 max, 10 bit interi abbondano
  Ty = numerictype(1, 24, 20);      % 1/x <= 1/0.5 = 2 -> pochi bit interi, molti frazionari
  lo_ = coder.const(fi(lo, Tx)); hi_ = coder.const(fi(hi, Tx));
  step  = coder.const((hi - lo) / (N - 1));
  invst = coder.const(1 / step);                                  % punti per unita'
  tab   = coder.const(fi(1 ./ (lo + (0:N-1) * step), Ty));        % 1xN: 1/x_i
  Tsm   = numerictype(0, 24, 13);                                 % moltiplicatore scala
  xs = fi(x, Tx);
  if xs < lo_, xs(:) = lo_; end
  if xs > hi_, xs(:) = hi_; end
  pos = fi((xs - lo_) * fi(invst, Tsm), numerictype(0, 32, 13));  % (x-lo)/step in [0,N-1)
  k = int32(floor(pos));
  if k < int32(0),     k = int32(0);     end
  if k > int32(N - 2), k = int32(N - 2); end
  frac = fi(pos - fi(double(k), numerictype(0, 32, 13)), Ty);
  y0 = tab(k + 1); y1 = tab(k + 2);
  y = fi(y0 + frac * fi(y1 - y0, Ty), Ty);
end
```

- [ ] **Step 2: verifica accuratezza standalone sui range veri dei divisori**

Run:
```
matlab -batch "cd('<matlabdir>');
R = {'v0',8,45; 's_safe',2,150; 'b',0.5,3; 'sab',0.87,1.32; '2s_safe',4,300};
for i=1:size(R,1)
  lo=R{i,2}; hi=R{i,3}; xs=linspace(lo,hi,500);
  for N=[16 32 64 128 256]
    e=arrayfun(@(x) abs(double(acc_recip_lut(x,lo,hi,N))-1/x), xs);
    if N==64, fprintf('%-8s N=%-4d  max|err 1/x|=%.3e  rel=%.2f%%\n', R{i,1}, N, max(e), 100*max(e.*xs)); end
  end
end"
```
Expected: per ogni divisore, `max|err 1/x|` che **cala** al crescere di N. Serve solo a confermare che la LUT
è sensata (l'errore in **accel** lo misura lo sweep del Task 3, questo è un sanity check su `1/x`).
Se `max|err|` NON cala con N → la costruzione della tabella/indice è sbagliata: **fermarsi** e confrontare con
`snn_decode_lut.m` (indice, clamp, interp), non aggiustare i tipi a caso.

- [ ] **Step 3: Commit**

```bash
git add matlab/acc_recip_lut.m
git commit -m "feat(sp4): acc_recip_lut - reciproco 1/x via LUT 1-D (modello snn_decode_lut) per la variante L"
```

---

## Task 2: `acc_types.recipN` + `acc_iidm_open` sceglie reciproco-LUT o divide()

**Files:** Modify `matlab/acc_types.m`, `matlab/acc_iidm_open.m`

`recipN = 0` → `divide()` (riferimento SP3). `recipN = N > 0` → reciproco-LUT a N punti (variante L). Così le due
strade vivono nella **stessa** `acc_iidm_open` (single source) e si scelgono coi tipi.

- [ ] **Step 1: aggiungi il campo `recipN` a `acc_types`**

In `matlab/acc_types.m`, cambia la firma e aggiungi il campo. Sostituisci `function T = acc_types(dt, nfrac)`
con:
```matlab
function T = acc_types(dt, nfrac, recipN)
```
e, subito dopo `if nargin < 2, nfrac = 8; end` (la riga del default nfrac), aggiungi:
```matlab
  % recipN: strategia di divisione del path fixed. 0 = divide() digit-recurrence (SP3, combinatorio
  % profondo). >0 = reciproco a LUT a recipN punti + moltiplica (SP4 variante L). Vive nei tipi cosi'
  % la scelta e' coder.const e single-source. Default 0 = comportamento SP3 invariato.
  if nargin < 3, recipN = 0; end
```
e nel ramo `case 'fixed'`, dopo la costruzione della struct `T`, aggiungi (prima di `end`):
```matlab
      T.recipN = recipN;
```
e nel ramo `case 'double'`, aggiungi al struct `T.recipN = 0;` (il double non usa reciproci).

- [ ] **Step 2: `acc_div` sceglie la strategia; passa i range**

In `matlab/acc_iidm_open.m`, sostituisci la funzione locale `acc_div`:
```matlab
function q = acc_div(T, isFx, num, den)
  if isFx
    q = divide(numerictype(T.acc), num, den);
  else
    q = num / den;
  end
end
```
con:
```matlab
function q = acc_div(T, isFx, num, den, lo, hi)
%ACC_DIV  num/den type-parametrica. Fixed: T.recipN==0 -> divide() (SP3); T.recipN>0 -> reciproco-LUT
%  (SP4 var. L). lo,hi = range GARANTITO di `den` (dai clamp dell'IIDM) per dimensionare la LUT.
  if isFx
    if T.recipN > 0
      q = cast(num * acc_recip_lut(den, lo, hi, T.recipN), 'like', T.acc);
    else
      q = divide(numerictype(T.acc), num, den);
    end
  else
    q = num / den;
  end
end
```

- [ ] **Step 3: passa i range misurati ai 5 siti di divisione**

In `matlab/acc_iidm_open.m`, aggiorna le 5 chiamate `acc_div` a divisore variabile coi range (spec §3). Il
sesto (`alf`, divisore `DT` costante) **non** cambia — `DT=0.1` è costante, resta `/DT`. Sostituisci:
```matlab
  s_star = cast(s0f + max(vq*Tf_ + acc_div(T, isFx, vq*dq, 2*sab), 0), 'like', T.st);
```
con:
```matlab
  s_star = cast(s0f + max(vq*Tf_ + acc_div(T, isFx, vq*dq, 2*sab, 1.74, 2.64), 0), 'like', T.st);
```
(`2*sab`, sab∈[0.87,1.32] → 2·sab∈[1.74,2.64]). Sostituisci:
```matlab
  v_free = cast(af*(1 - min(acc_div(T, isFx, vq, v0f), 10)^4), 'like', T.acc);
```
con:
```matlab
  v_free = cast(af*(1 - min(acc_div(T, isFx, vq, v0f, 8, 45), 10)^4), 'like', T.acc);
```
Sostituisci:
```matlab
  z = cast(min(acc_div(T, isFx, s_star, s_safe), 20), 'like', T.acc);
```
con:
```matlab
  z = cast(min(acc_div(T, isFx, s_star, s_safe, 2, 150), 20), 'like', T.acc);
```
Sostituisci:
```matlab
  a_cah = cast(a_l_bar - acc_div(T, isFx, max(dq,0)^2, 2*s_safe + 1e-6), 'like', T.acc);
```
con:
```matlab
  a_cah = cast(a_l_bar - acc_div(T, isFx, max(dq,0)^2, 2*s_safe + 1e-6, 4, 300), 'like', T.acc);
```
Sostituisci:
```matlab
  dd = cast(acc_div(T, isFx, a_iidm - a_cah, bf + 1e-6), 'like', T.acc);
```
con:
```matlab
  dd = cast(acc_div(T, isFx, a_iidm - a_cah, bf + 1e-6, 0.5, 3), 'like', T.acc);
```

- [ ] **Step 4: il double NON si è mosso, e il fixed SP3 (recipN=0) è invariato**

Run: `matlab -batch "cd('<matlabdir>'); build_plant_lib; clear PLANT acc_iidm_open acc_types; run_plant_parity"`
Expected: `ALL PLANT PARITY PASS`, `0.00e+00` su 3/3 (il double usa il ramo `num/den`, invariato).
Run: `matlab -batch "cd('<matlabdir>'); run_block_acciidm_test(12,1,400)"`
Expected: `dmax(accel) = 0` — il blocco usa `acc_types('fixed')` con `recipN=0` di default → **ancora divide()**,
quindi identico a SP3. Se `dmax > 0`: l'aggiunta di `lo,hi`/`recipN` ha toccato il ramo `recipN=0`. **Fermarsi**,
`git diff` — il ramo `else` di `acc_div` deve essere byte-identico a prima.

- [ ] **Step 5: Commit**

```bash
git add matlab/acc_types.m matlab/acc_iidm_open.m matlab/cf_plant_lib.slx
git commit -m "feat(sp4): acc_div sceglie divide() o reciproco-LUT via T.recipN; range dei divisori ai siti

recipN=0 (default) = comportamento SP3 invariato (run_plant_parity 0.00e+00, acciidm_test dmax=0).
recipN>0 = variante L (reciproco-LUT). I 5 divisori portano il loro range misurato per la LUT."
```

---

## Task 3: sweep della dimensione LUT reciproco vs budget

**Files:** Create `matlab/run_acc_recip_sweep.m`

Stesso criterio di `run_acc_fixed_sweep` (SP3): l'errore che il reciproco-LUT aggiunge in `accel` deve restare
**sotto** il budget `E_snn` (footprint della quantizzazione della rete, p99 0.272 / max 1.484). Si sceglie la N
più piccola che passa.

- [ ] **Step 1: scrivi `matlab/run_acc_recip_sweep.m`**

```matlab
function [best, tab] = run_acc_recip_sweep(Ns, nTraj)
%RUN_ACC_RECIP_SWEEP  [SP4-L] Quanti punti serve la LUT del reciproco?
%  E_L(N) = |accel(IIDM fixed, reciproco-LUT a N) - accel(IIDM fixed, divide() SP3)| a parita' di
%  parametri. Passa se E_L < budget E_snn (p99 0.272 / max 1.484, footprint quantizzazione rete, SP3).
%  Si sceglie la N minima che passa. LENTO (fi interpretato): lanciarlo in background sul dataset intero.
  if nargin < 1 || isempty(Ns), Ns = [16 32 64 128 256]; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W = champ_weights(c); Tp = numerictype(1,21,13);
  Tdiv = acc_types('fixed');                    % recipN=0 -> divide() SP3 (riferimento)
  nTraj = min(nTraj, numel(tr));
  bud_p99 = 0.272054; bud_max = 1.48433;        % E_snn misurato in SP3 (run_acc_fixed_sweep)
  fprintf('budget E_snn: p99=%.6g max=%.6g [m/s^2]\n\n%-6s %12s %12s %8s\n', bud_p99, bud_max, ...
          'N', 'E_L p99', 'E_L max', 'passa');
  tab = zeros(numel(Ns), 3);
  for j = 1:numel(Ns)
    Trl = acc_types('fixed', 8, Ns(j)); E = [];
    for i = 1:nTraj
      val = double(tr{i}.val); R = double(snn_traj_fixed_r16_mex(val, W));
      P = zeros(size(val,2),5);
      for k=1:size(val,2), P(k,:)=double(snn_decode_lut(fi(R(k,:).',Tp),64)).'; end
      clear acc_iidm_open; aD = zeros(size(val,2),1);
      for k=1:size(val,2), aD(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k),P(k,:).',k==1,Tdiv)); end
      clear acc_iidm_open; aL = zeros(size(val,2),1);
      for k=1:size(val,2), aL(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k),P(k,:).',k==1,Trl)); end
      E = [E; abs(aL - aD)]; %#ok<AGROW>
    end
    tab(j,:) = [Ns(j), prctile(E,99), max(E)];
    fprintf('%-6d %12.6g %12.6g %8s\n', Ns(j), tab(j,2), tab(j,3), string(tab(j,2)<bud_p99 && tab(j,3)<bud_max));
  end
  k = find(tab(:,2) < bud_p99 & tab(:,3) < bud_max, 1);
  assert(~isempty(k), ['nessuna N in [%s] rispetta il budget: il reciproco-LUT sarebbe la fonte ' ...
         'd''errore dominante. NON allargare il budget: alzare N o rivedere i range.'], mat2str(Ns));
  best = tab(k,1);
  fprintf('\n>>> MINIMO N reciproco-LUT che rispetta il budget: %d <<<\n', best);
end
```

- [ ] **Step 2: esegui lo sweep sul dataset intero (background)**

Run (background): `matlab -batch "cd('<matlabdir>'); run_acc_recip_sweep([16 32 64 128 256], 60)" > recip_sweep.log 2>&1 &`
Attendere il completamento. Expected: `E_L` che **cala** al crescere di N, e una N minima che passa.
Se **nessuna** N passa nemmeno a 256 → **fermarsi**: o i range `lo,hi` sono sbagliati (troncano il divisore) o
un divisore ha 1/x troppo ripido per una LUT uniforme (candidato: `s_safe∈[2,150]`). È un **dato per la
decisione**: se L non regge il budget, M diventa la strada. NON allargare il budget.

- [ ] **Step 3: fissa la N scelta come default della variante L**

Annota la N vincente; sarà passata dal builder al Task 4 (non si cambia il default di `acc_types`, che resta
`recipN=0` = SP3). Registra `best` e la tabella in `document/SP4_ACC_IIDM_FAST.md` al Task 6.

- [ ] **Step 4: Commit**

```bash
git add matlab/run_acc_recip_sweep.m
git commit -m "test(sp4): run_acc_recip_sweep - dimensione LUT reciproco vs budget E_snn (come il decode)"
```

---

## Task 4: blocco `Donatello_ACC_IIDM_L` + verifica sul dataset

**Files:** Modify `matlab/build_hdl_variants.m`; rigenera `matlab/snn_champions_lib.slx`

Un blocco separato per la variante L (il blocco SP3 resta il riferimento). La chart passa `acc_types('fixed', 8,
<Nbest>)` all'IIDM.

- [ ] **Step 1: aggiungi il blocco L in `build_hdl_variants.m`**

Dopo la costruzione di `Donatello_ACC_IIDM` (blocco SP3), aggiungi un blocco gemello che chiama la chart con
`recipN = <Nbest>`. Riusa `acciidm_chart_code`, ma con una variante che sostituisce nella chart la riga
`acc_types(''fixed'')` con `acc_types(''fixed'', 8, <Nbest>)`. Concretamente, dopo il blocco SP3:
```matlab
  % ---- SP4 variante L: IIDM con reciproco-LUT (recipN = Nbest dallo sweep) ----
  NRECIP = 64;   % <-- sostituire con la N vincente di run_acc_recip_sweep (Task 3)
  subL = [lib '/Donatello_ACC_IIDM_L'];
  if getSimulinkBlockHandle(subL) > 0, delete_block(subL); end
  add_block('built-in/Subsystem', subL, 'Position', [300, 130, 500, 170], ...
            'Description', acciidm_description(NCHAMP));
  add_block('simulink/User-Defined Functions/MATLAB Function', [subL '/SNN_ACC']);
  chartL = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [subL '/SNN_ACC']);
  scriptL = acciidm_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcIidm, srcAccT, nrm);
  % inietta il reciproco-LUT: acc_types('fixed') -> acc_types('fixed', 8, NRECIP), e inlina acc_recip_lut
  scriptL = strrep(scriptL, 'acc_types(''fixed'')', sprintf('acc_types(''fixed'', 8, %d)', NRECIP));
  scriptL = [scriptL newline newline fileread(fullfile(here, 'acc_recip_lut.m'))];
  chartL.Script = scriptL;
  for j = 1:4
    add_block('built-in/Inport', [subL '/' in_names{j}], 'Port', num2str(j));
    add_line(subL, [in_names{j} '/1'], ['SNN_ACC/' num2str(j)]);
  end
  add_block('built-in/Outport', [subL '/accel'], 'Port', '1');
  add_line(subL, 'SNN_ACC/1', 'accel/1');
  fprintf('  costruito Donatello_ACC_IIDM_L (SP4, reciproco-LUT N=%d)\n', NRECIP);
```
Aggiungi `srcAccT` alla lista dei sorgenti letti se non già presente (Task SP3 lo aggiunge già). Nota: la chart L
inlina **anche** `acc_recip_lut` (self-contained).

- [ ] **Step 2: rigenera la libreria e verifica che il blocco esista e simuli**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; load_system('snn_champions_lib'); fprintf('L=%d\n', getSimulinkBlockHandle('snn_champions_lib/Donatello_ACC_IIDM_L')>0); close_system('snn_champions_lib',0)"`
Expected: `L=1`, nessun errore di build.
Se la chart non compila: messaggio vero via `codegen` sullo script della chart (Convenzioni).

- [ ] **Step 3: verifica sul dataset — L vs riferimento SP3, entro budget**

Estendi/riusa `run_block_acciidm_test` per pilotare `Donatello_ACC_IIDM_L`. Aggiungi in
`matlab/run_block_acciidm_test.m` un secondo argomento opzionale `blockName` (default `Donatello_ACC_IIDM`) e
usalo nel `drive_acciidm` al posto della stringa fissa `'snn_champions_lib/Donatello_ACC_IIDM'`. Poi:
Run: `matlab -batch "cd('<matlabdir>'); for t=[1 6 12 20 30], run_block_acciidm_test(12,t,400,'Donatello_ACC_IIDM_L'); end"`
Expected: `dmax(accel)` **> 0 ma sotto il budget** (L approssima: non è bit-identico). Il criterio è
`dmax ≤ E_snn.max = 1.484`; atteso ~ l'`E_L.max` dello sweep. Se `dmax > 1.484` → il blocco usa una N diversa da
quella dello sweep, o i range della chart divergono: **fermarsi**, confrontare N e range.

- [ ] **Step 4: anello chiuso + gate HDL restano verdi**

Run: `matlab -batch "cd('<matlabdir>'); run_block_closed_loop_test(1,40,400,'train'); run_block_hdl_gate('Donatello_ACC_IIDM_L')"`
Expected: anello chiuso `dmax` piccolo e stabile (l'anello usa `snn_cl_step` = riferimento SP3; qui verifichiamo
solo che il blocco L **giri** in anello senza divergere) + `GATE PASSATO` (VHDL + `DualPortRAM`).

> NB: l'anello chiuso confronta col riferimento fixed SP3, non con L → un `dmax > 0` piccolo è atteso per L. Se
> serve un anello L-vs-L, è un cancello a sé; per ora basta che L **non diverga** (gap limitato, niente NaN).

- [ ] **Step 5: `run_block_sync_check` copre il nuovo sorgente**

`acc_recip_lut.m` è ora inlinato nel blocco L. Aggiungi `acc_recip_lut.m` alla lista `srcSp2` (o una nuova
`srcSp4`) di `matlab/run_block_sync_check.m`, con il controllo `contains(s,'acc_recip_lut(')` per il solo blocco L.
Run: `matlab -batch "cd('<matlabdir>'); run_block_sync_check"`
Expected: blocchi controllati includono `Donatello_ACC_IIDM_L`, **0 stale**.

- [ ] **Step 6: Commit**

```bash
git add matlab/build_hdl_variants.m matlab/run_block_acciidm_test.m matlab/run_block_sync_check.m matlab/snn_champions_lib.slx
git commit -m "feat(sp4): blocco Donatello_ACC_IIDM_L (reciproco-LUT) + verifica sul dataset entro budget"
```

---

## Task 5: sintesi OOC di L — il numero che decide

**Files:** riuso `scripts/synth_acc_iidm.tcl`

- [ ] **Step 1: genera il VHDL di L e sintetizza OOC**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; load_system('snn_champions_lib'); makehdl('snn_champions_lib/Donatello_ACC_IIDM_L','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp4','L'),'GenerateHDLTestBench','off'); close_system('snn_champions_lib',0)"`
Expected: albero VHDL in `matlab/hdl_sp4/L`, 0 errori.
Run (Git Bash):
```bash
V="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
cd "<worktree>"
"$V" -mode batch -notrace -source scripts/synth_acc_iidm.tcl -tclargs matlab/hdl_sp4/L matlab/hdl_sp4/out_L L | grep -E "RESULT|CRITPATH"
```
Expected: `RESULT L LUT=… Fmax=…` + `CRITPATH L …`.

- [ ] **Step 2: confronta col riferimento SP3 e col bersaglio**

Riferimento SP3 (misurato): catena con `divide()` = **2,0 MHz, 10846 LUT, 1077 livelli** (path nei divisori).
Bersaglio: **≥ 11,65 MHz**. Leggi Fmax e il path critico di L:
- Se **Fmax ≥ 11,65 MHz** → L centra il bersaglio: la sqrt residua **non** è il collo. Ottimo dato.
- Se **Fmax < 11,65 MHz** → guarda `CRITPATH L`: se il path è ora nella `sqrt` (cerca `sqrt`/carry nel nome dei
  segnali), è **il dato che motiva M** (time-mux, che sequenzia anche la sqrt). NON è un fallimento: è la risposta
  alla domanda «basta L?».

- [ ] **Step 3: Commit (se lo script è cambiato) + registra i numeri**

I numeri OOC di L vanno nel doc (Task 6). Se `synth_acc_iidm.tcl` non è cambiato, niente commit qui.

---

## Task 6: documentazione + decisione + kickoff M

**Files:** Create `document/SP4_ACC_IIDM_FAST.md`; Modify `document/SESSION_RESUME.md`, `matlab/README.md`

- [ ] **Step 1: crea `document/SP4_ACC_IIDM_FAST.md`**

Struttura (riempire coi numeri VERI dei Task 3 e 5, mai segnaposto):
```markdown
# SP4 — ACC-IIDM fast

> Doc di processo. Spec: docs/superpowers/specs/2026-07-16-acc-iidm-fast-design.md.

## Problema (SP3, misurato)
[1077 livelli, CARRY4=820 (76%) dai divisori digit-recurrence combinatori incatenati]

## Variante L — reciproci a LUT
[acc_recip_lut 1-D; range dei divisori; N scelta dallo sweep + tabella E_L vs budget E_snn]

## Numeri OOC (xc7z020 @8 MHz)
| variante | LUT | DSP | Fmax | WNS | liv.logici | path critico |
| SP3 divide() | 10846 | 69 | 2.0 MHz | -373 ns | 1077 | divisori |
| L reciproco-LUT | … | … | … | … | … | … |
[+ verdetto: L centra 11.65 MHz? la sqrt e' il collo?]

## Decisione
[L basta / serve M — sui dati]
```

- [ ] **Step 2: aggiorna `SESSION_RESUME.md` e `README.md`**

In `SESSION_RESUME.md`: aggiungi lo stato SP4-L (fatto, coi numeri OOC) e il prossimo (M o chiuso).
In `matlab/README.md`: aggiungi `acc_recip_lut.m` fra i core, `run_acc_recip_sweep.m` fra i cancelli, e il blocco
`Donatello_ACC_IIDM_L` nella sezione librerie.

- [ ] **Step 3: cancelli finali + Commit + push**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity; run_block_acciidm_test(12,1,400); run_block_sync_check; run_block_hdl_gate('Donatello_Champion'); run_block_hdl_gate('Donatello_ACC_IIDM_L'); disp('>>>> VERDI <<<<')"`
Expected: `ALL PLANT PARITY PASS` · `dmax=0` (blocco SP3 default) · `0 stale` · `GATE PASSATO` ×2 · `VERDI`.
```bash
git add document/SP4_ACC_IIDM_FAST.md document/SESSION_RESUME.md matlab/README.md
git commit -m "docs(sp4): SP4_ACC_IIDM_FAST.md - variante L (reciproco-LUT), numeri OOC, decisione L-vs-M"
git push origin Simulink_Importer
```

- [ ] **Step 4: kickoff M (se i dati lo indicano)**

Sulla base del Task 5: se L **non** centra 11,65 MHz (o la `sqrt`/altro resta il collo), **M** è giustificato.
M è un **piano a sé** (time-mux FSM dell'IIDM) da scrivere con `writing-plans`, informato dai numeri di L: in
particolare, se il path critico di L è la `sqrt`, M deve sequenziare anche quella. Se L **centra** 11,65 MHz,
M resta un confronto opzionale (l'utente lo preferisce ma la decisione è sui dati). Annota la raccomandazione nel
doc.

---

## Self-review (copertura della spec)
- **§1 scopo** (Fmax ≥ 11,65 MHz): Task 5 (misura) + Task 6 (decisione). ✓
- **§2 problema misurato** (divisori, 76% carry): citato Task 6 Step 1; è il movente, non un task. ✓
- **§3 range divisori**: Task 2 Step 3 (i 5 range ai siti) + Task 1 Step 2 (sanity su ogni range). ✓
- **§4 variante L** (reciproco-LUT, sab 1-D via sqrt nativa, sweep): Task 1-4. **M**: Task 6 Step 4 (piano a sé). ✓
- **§5 verifica** (L a budget, closed-loop, hdl_gate, OOC): Task 3 (sweep) · Task 4 (dataset+loop+gate) · Task 5 (OOC). ✓
- **§6 fuori scope** (overlap, slack-minima, bitstream): rispettato — nessun task li tocca. ✓
- **Coerenza tipi/firme**: `acc_recip_lut(x,lo,hi,N)` — stessa firma in Task 1, 2 (dentro acc_div), 4 (inline). ✓
  `acc_types(dt,nfrac,recipN)` — Task 2 la definisce, Task 3/4 la usano con `recipN>0`. ✓
  `acc_div(T,isFx,num,den,lo,hi)` — Task 2 la definisce (6 arg), i 5 siti la chiamano coi range. ✓
- **run_plant_parity invariato** (double non si muove): Task 2 Step 4. ✓ **recipN=0 = SP3 invariato**: Task 2 Step 4. ✓
