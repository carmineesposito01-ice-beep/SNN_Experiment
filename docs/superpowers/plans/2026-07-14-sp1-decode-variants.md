# SP1 — Libreria champion con varianti di decode (LUT sweep) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere a `snn_champions_lib.slx` 6 blocchi `Donatello_LUT{N}` (forward B2 fixed-point + decode sigmoide a LUT di N punti, N∈{16,32,64,128,256,512}, HDL-ready) e caratterizzare la curva **accuratezza-vs-dimensione LUT** sul dataset, per scegliere il compromesso.

**Architecture:** il decode a LUT viene generalizzato in `snn_decode_lut(raw, N)` (N = `coder.const`). Lo sweep di accuratezza riusa il **MEX del forward** (B1.5-a): il forward B2 fixed di Donatello produce il `raw` una volta sola, poi si applica il decode-LUT-N per ogni N (l'effetto della dimensione LUT è tutto nel decode). I blocchi di libreria sono sottosistemi streaming (`xn[4], start → params[5], done`) che HDL Coder sintetizza.

**Tech Stack:** MATLAB R2026a (Fixed-Point Designer, `fi`), HDL Coder (`codegen -config hdl`), Vivado 2026.1 (stima risorse), Simulink (libreria). Riusa `snn_traj_fixed_r16_mex` (B1.5-a).

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"`.
- **Non toccare** `snn_decode_hdl.m` (lo usa il B2 di Fase B): `snn_decode_lut` è NUOVO e va **verificato bit-identico** a `snn_decode_hdl` per N=256 (nessuna regressione al percorso deployato).
- **Core congelato bit-identico** (`run_parity_tests`/`run_b2_parity` verdi dopo ogni modifica al core — qui non si tocca il core).
- **Lavoro Vivado/HDL Coder = checkpoint-driven** (run lunghi in background; ci si ferma a far validare).
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei non miei** (`closed_loop_demo.slx`, `slblocks.m`): **non toccarli** nei `git add`.

## File Structure
```
matlab/snn_decode_lut.m                     # Task 1 — decode LUT parametrico in N (generalizza snn_decode_hdl)
matlab/run_lut_sweep.m                      # Task 2 — accuratezza vs N (MEX forward + decode-LUT-N)
matlab/axi/build/lut_sweep/results_lut.csv  # Task 2/6 — dati grounding
matlab/build_hdl_variants.m                 # Task 4 — aggiunge i 6 blocchi Donatello_LUT{N} a snn_champions_lib.slx
matlab/axi/build/lut_sweep/util_lut<N>.rpt  # Task 3 — risorse decode LUT-N (Vivado)
scripts/figs_lut_sweep.py                   # Task 6 — figura curva accuratezza/risorse-vs-N
```

---

## Task 1: `snn_decode_lut(raw, N)` — decode LUT parametrico

**Files:** Create `matlab/snn_decode_lut.m`

Generalizza `snn_decode_hdl` rendendo la dimensione LUT un parametro `coder.const`. Costanti Donatello baked (lo sweep è Donatello-only). Scala indice = N/16 (potenza di 2 → shift).

- [ ] **Step 1: scrivi `snn_decode_lut.m`**
```matlab
function p = snn_decode_lut(raw, N) %#codegen
%SNN_DECODE_LUT  Decode Donatello con sigmoide via LUT a N punti su [-8,8) + interp lineare.
%  Generalizza snn_decode_hdl (N=256). N = coder.const, potenza di 2 (scala indice = N/16).
  Traw = numerictype(1,21,13); Tadj = numerictype(1,18,13); Titau = numerictype(1,18,16);
  Ts   = numerictype(1,16,14); Tp   = numerictype(1,21,13); Tsc  = numerictype(0,22,13);
  offset = coder.const(fi([-0.40404 -0.39012 1.7718 2.6884 -0.95578].', Traw));
  invtau = coder.const(fi([0.1 1/3 0.1 1/3 1/3].', Titau));
  lo     = coder.const(fi([8 0.5 1 0.3 0.5].', Tp));
  hilo   = coder.const(fi([37 2 4 2.2 2.5].', Tp));
  scale  = coder.const(N / 16);                                   % punti per unita'
  sgtab  = coder.const(fi(1 ./ (1 + exp(-(-8 + (0:N-1) / scale))), Ts));  % 1xN
  Tsm    = numerictype(0, 8, 0);                                  % moltiplicatore scala (<=32)
  p = fi(zeros(5,1), Tp);
  for i = 1:5
    adj    = fi((raw(i) - offset(i)) * invtau(i), Tadj);
    scaled = fi((adj + fi(8, Tadj)) * fi(scale, Tsm), Tsc);       % (adj+8)*scale in [0,N]
    k = int32(floor(scaled));
    if k < int32(0),     k = int32(0);     end
    if k > int32(N - 2), k = int32(N - 2); end
    frac = fi(scaled - fi(double(k), Tsc), Ts);
    s0 = sgtab(k + 1); s1 = sgtab(k + 2);
    s  = fi(s0 + frac * fi(s1 - s0, Ts), Ts);
    p(i) = fi(lo(i) + hilo(i) * s, Tp);
  end
end
```

- [ ] **Step 2: regressione — N=256 bit-identico a snn_decode_hdl**
```matlab
% MATLAB batch
raws = fi(randn(5, 200) * 5, numerictype(1,21,13));   % raw plausibili Q7.13
nmis = 0;
for t = 1:200
  a = snn_decode_hdl(raws(:,t)); b = snn_decode_lut(raws(:,t), 256);
  if any(storedInteger(a(:)) ~= storedInteger(b(:))), nmis = nmis + 1; end
end
fprintf('N=256 vs snn_decode_hdl: %d mismatch su 200\n', nmis);
assert(nmis == 0, 'snn_decode_lut(.,256) NON bit-identico a snn_decode_hdl');
```
Expected: **0 mismatch**. Se ≠0 → indagare (larghezze Tsc/Tsm, scala) prima di procedere.

- [ ] **Step 3: gira per tutti gli N (nessun errore, params in range fisico)**
```matlab
for N = [16 32 64 128 256 512]
  p = snn_decode_lut(fi([26.5 1.6 2.4 1.0 1.7].', numerictype(1,21,13)), N);
  fprintf('N=%3d: params = %s\n', N, mat2str(double(p).',4));
end
```
Expected: 6 righe, params plausibili (v0~8..45, ecc.), nessun errore.

- [ ] **Step 4: Commit**
```bash
git add matlab/snn_decode_lut.m
git commit -m "feat(sp1): snn_decode_lut(raw,N) - decode LUT parametrico in N (N=256 bit-identico a snn_decode_hdl)"
```

---

## Task 2: `run_lut_sweep` — accuratezza vs dimensione LUT

**Files:** Create `matlab/run_lut_sweep.m`, output `matlab/axi/build/lut_sweep/results_lut.csv`

Il forward B2 fixed di Donatello (via il MEX di B1.5-a) produce il `raw` per step **una volta**; per ogni N si applica `snn_decode_lut` e si aggrega come il riferimento (media 2a metà). Metriche: NRMSE/accuratezza vs GT e Δ vs LUT-512 (near-exact) → curva del ginocchio.

- [ ] **Step 1: scrivi `run_lut_sweep.m`**
```matlab
function run_lut_sweep(nmax)
%RUN_LUT_SWEEP  Accuratezza dei params di Donatello al variare della dimensione LUT del decode.
%  Forward B2 fixed via snn_traj_fixed_r16_mex (raw calcolato UNA volta); decode-LUT-N per ogni N.
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  if nargin < 1, nmax = numel(tr); else, nmax = min(nmax, numel(tr)); end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs), 1));
  W = champ_weights(c); rng = double(c.param_hi(:) - c.param_lo(:));
  Ns = [16 32 64 128 256 512];
  Traw = numerictype(1,21,13);
  acc = zeros(numel(Ns),1); nrmse = zeros(numel(Ns),5); dmax512 = zeros(numel(Ns),1);
  % raw per traiettoria (una volta), + params per N
  Praw = cell(nmax,1);
  for k = 1:nmax, Praw{k} = snn_traj_fixed_r16_mex(tr{k}.val, W); end
  P512 = agg_params(Praw, 512, Traw, nmax);   % baseline near-exact
  for iN = 1:numel(Ns)
    PN = agg_params(Praw, Ns(iN), Traw, nmax);
    gt = cell2mat(cellfun(@(k) double(tr{k}.gt_params(:)).', num2cell(1:nmax).','UniformOutput',false));
    se = mean((PN - gt).^2, 1).';
    nrmse(iN,:) = (sqrt(se) ./ rng).';
    acc(iN) = 100 * (1 - mean(nrmse(iN,:)));
    dmax512(iN) = max(abs(PN(:) - P512(:)));
  end
  outdir = fullfile(here,'axi','build','lut_sweep'); if ~exist(outdir,'dir'), mkdir(outdir); end
  fid = fopen(fullfile(outdir,'results_lut.csv'),'w'); fprintf(fid,'N,acc,dmax_vs_512\n');
  fprintf('%-5s | %-7s | %-12s\n','N','acc%','dmax vs 512');
  for iN = 1:numel(Ns)
    fprintf('%-5d | %6.2f | %.4f\n', Ns(iN), acc(iN), dmax512(iN));
    fprintf(fid,'%d,%.4f,%.4f\n', Ns(iN), acc(iN), dmax512(iN));
  end
  fclose(fid); fprintf('scritto %s\n', fullfile(outdir,'results_lut.csv'));
end

function Pagg = agg_params(Praw, N, Traw, nmax)
% decode-LUT-N per ogni step di ogni traiettoria, poi media 2a meta' -> (nmax x 5)
  Pagg = zeros(nmax, 5);
  for k = 1:nmax
    R = Praw{k}; M = size(R,1); Pk = zeros(M,5);
    for s = 1:M
      Pk(s,:) = double(snn_decode_lut(fi(R(s,:).', Traw), N)).';
    end
    Pagg(k,:) = mean(Pk(floor(M/2)+1:M, :), 1);
  end
end
```
> Nota velocità: il decode-LUT-N è `fi` interpretato ma leggero (5 lookup/step). Se lo sweep completo (60×~1000×6) risultasse lento, il **contingency** è compilare `snn_decode_lut` in MEX per-N (stesso pattern di `build_traj_mex`); per un test rapido usare `run_lut_sweep(6)` prima del run completo.

- [ ] **Step 2: test rapido su 6 traiettorie**

Run: `matlab -batch "cd('<matlabdir>'); run_lut_sweep(6)"`
Expected: 6 righe (N=16..512). `acc%` **cresce** con N e **satura** verso 256/512; `dmax_vs_512` **decresce** con N (→ ~0 a 512). Se N piccola non degrada → indagare (LUT non applicata / raw sbagliato).

- [ ] **Step 3: Commit** (dopo che i numeri tornano)
```bash
git add matlab/run_lut_sweep.m
git commit -m "feat(sp1): run_lut_sweep - accuratezza params vs dimensione LUT (forward MEX + decode-LUT-N)"
```

---

## Task 3: Stima risorse HW per N — CHECKPOINT-DRIVEN

**Files:** Create `matlab/axi/build/lut_sweep/util_lut<N>.rpt` (output Vivado)

Il costo HW della LUT cresce con N (memoria della tabella). Sintetizzare **OOC** il solo stadio decode LUT-N (codegen HDL → Vivado synth) per un paio di N estremi + il centrale, per la curva risorse-vs-N.

- [ ] **Step 1:** genera l'RTL del decode LUT-N (HDL Coder su `snn_decode_lut` con `N` const) per N∈{16, 256, 512}; sintesi OOC su `xc7z020clg400-1`; estrai `util` (LUT/BRAM). **Checkpoint:** atteso LUT/BRAM crescenti con N (512 ~2× tabella di 256); far validare.
- [ ] **Step 2: Commit** dei report util.
```bash
git add matlab/axi/build/lut_sweep/util_lut*.rpt
git commit -m "feat(sp1): risorse HW decode LUT-N (N=16/256/512) per la curva accuratezza-vs-risorse"
```

---

## Task 4: `build_hdl_variants` — i 6 blocchi in libreria — CHECKPOINT-DRIVEN

**Files:** Create `matlab/build_hdl_variants.m`; modifica `matlab/snn_champions_lib.slx` (rigenerato)

Aggiunge a `snn_champions_lib.slx` 6 sottosistemi `Donatello_LUT{N}` streaming (`xn[4], start → params[5], done`), la cui MATLAB Function esegue il forward B2 (`snn_b2_fsm`, ROM Donatello) + `snn_decode_lut(raw, N)`. Segue il pattern di `build_library.m` (add_block/add_line + Stateflow.EMChart script).

- [ ] **Step 1:** scrivi `build_hdl_variants.m` che, per ogni N, crea il sottosistema con porte `xn`(4)+`start` → `params`(5)+`done` e una MATLAB Function che chiama `snn_b2_fsm` + `snn_decode_lut(·, N)`; salva la libreria. *(Packaging: la ROM Donatello via `gen_b2_rom('Donatello')`→`b2_rom_active`; decidere in esecuzione se inlinare per self-containment o referenziare — default referenziato, come il B2.)*
- [ ] **Step 2: Checkpoint** — apri `snn_champions_lib.slx`, verifica i 6 blocchi presenti e trascinabili; una simulazione breve di un blocco dà params plausibili (== `snn_decode_lut` sul raw del MEX). Far validare.
- [ ] **Step 3: Commit**
```bash
git add matlab/build_hdl_variants.m matlab/snn_champions_lib.slx
git commit -m "feat(sp1): build_hdl_variants - 6 blocchi Donatello_LUT{N} (B2 + decode LUT-N) in snn_champions_lib"
```

---

## Task 5: Verifica HDL-ready (VHDL) — CHECKPOINT-DRIVEN

**Files:** output `matlab/codegen/` (gitignored)

Per ogni `Donatello_LUT{N}`: avviare HDL Coder e confermare che il VHDL sia generato **senza errori e nel modo previsto** (decode = LUT sintetizzata, non `exp`). Almeno N=256 arriva a **sintesi Vivado** (conferma risorse coerenti con Task 3).

- [ ] **Step 1:** HDL Coder (`codegen -config hdl` o il flow HDL del blocco) su ciascun N; verifica 0 errori e che la LUT appaia come tabella (ROM) nel VHDL. **Checkpoint:** se un N non genera → consultare la skill `fpga-expert` e indagare (tipi/costanti), non aggirare. Far validare.
- [ ] **Step 2: Commit** (log/nota di verifica; RTL è gitignored).
```bash
git commit -m "feat(sp1): verifica HDL Coder dei blocchi Donatello_LUT{N} (VHDL generato, LUT sintetizzata)" --allow-empty
```

---

## Task 6: Consolidamento + figura

**Files:** `matlab/axi/build/lut_sweep/results_lut.csv` (aggiornato), Create `scripts/figs_lut_sweep.py`

- [ ] **Step 1:** integra in `results_lut.csv` le risorse (Task 3) accanto all'accuratezza (Task 2) per N.
- [ ] **Step 2:** `scripts/figs_lut_sweep.py` (matplotlib, sfondo chiaro): curva **accuratezza-vs-N** e **risorse-vs-N** con il ginocchio evidenziato. (Nessun `np.linalg`/LAPACK.)
- [ ] **Step 3: Commit**
```bash
git add matlab/axi/build/lut_sweep/results_lut.csv scripts/figs_lut_sweep.py
git commit -m "feat(sp1): consolida curva accuratezza/risorse-vs-dimensione-LUT + figura"
git push origin Simulink_Importer
```

---

## Self-review (copertura spec SP1)
- **snn_decode_lut parametrico (§4.2):** Task 1 (+ regressione N=256 == snn_decode_hdl). ✓
- **6 blocchi Donatello_LUT{N} in libreria (§4.1, §4.2):** Task 4. ✓
- **Confronto accuratezza-vs-dimensione, 2 baseline (§4.3):** Task 2 (double-exp via GT; LUT-512 near-exact per isolare la dimensione) + Task 3 (risorse). ✓
- **Verifica HDL-ready (§4.4):** Task 5. ✓
- **Criteri di successo (§4.5):** Task 1 step 2 (bit-identico), Task 4/5 (blocchi + VHDL), Task 2/6 (curva). ✓
- **Fuori scope:** exp sugli altri 3 (esistono), SP2, sintesi di TUTTI gli N (Task 3 fa N rappresentativi). ✓
- **Realismo:** Task 1-2 MATLAB testabili; Task 3-5 (Vivado/Simulink/HDL Coder) **checkpoint-driven** — esiti validati con l'utente, non assunti. Contingency velocità decode = MEX per-N.

## Handoff d'esecuzione
Alla fine: **(1) Subagent-Driven** (un subagent per task, review tra task) o **(2) Inline** (executing-plans, checkpoint). I task 3-5 sono a checkpoint umano (Vivado/Simulink/HDL Coder).
