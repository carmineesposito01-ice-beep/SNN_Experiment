# Studio di quantizzazione (nfrac unico) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Caratterizzare il trade-off di quantizzazione della SNN Donatello — le quattro curve (accuratezza · risorse · potenza · Fmax) vs `nfrac` — trovare il ginocchio, validarlo in car-following, e dare a ogni livello scelto la sua **configurazione canonica** (Fmax massimo via passo adattivo). Tutto isolato in `matlab/Quantizzation_Study/`.

**Architecture:** Riuso `run_fixed_sweep` (accuratezza vs nfrac, già corretto) e il tooling io-timed dello Studio A (`synth_point.tcl` + `impl_point.tcl`, che danno risorse+potenza+Fmax con flag di validità WNS≤0). Il nuovo codice è: la **parametrizzazione `nfrac`** del forward (oggi hardcoda Q?.13), il **driver di sweep su nfrac**, la **bisezione del Fmax**, e l'analisi/figure. Regola d'oro: **non tocco nessun originale** — copio in `Quantizzation_Study/` con prefisso `qz_` e modifico solo lì; il tooling `.tcl` che NON modifico lo riuso dal suo path.

**Tech Stack:** MATLAB R2026a (`matlab.exe -batch`), HDL Coder (`makehdl`), Vivado 2026.1 (`vivado.bat`, via `synth_point.tcl`/`impl_point.tcl`), Git Bash, Python (matplotlib) per le figure.

**Convenzioni:**
- `MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"` ; `VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"`.
- Scratch di sintesi su path **senza spazi**: `D:/zbd_qz`. Commit conventional **senza** `Co-Authored-By`.
- Cartella di lavoro: `matlab/Quantizzation_Study/` (di seguito `QZ/`). Spec: `docs/superpowers/specs/2026-07-24-quantization-study-design.md`.

---

## Task 0: Setup cartella + cancello di isolamento

**Files:**
- Create: `matlab/Quantizzation_Study/` (dir), `matlab/Quantizzation_Study/.gitignore`

- [ ] **Step 1: Crea la cartella e il .gitignore degli artefatti**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
mkdir -p Quantizzation_Study
printf '*.slx\n*.mexw64\nb2_rom_active.m\nslprj/\ncodegen/\n' > Quantizzation_Study/.gitignore  # i TSV e le figure sono dati/output -> si committano
ls -la Quantizzation_Study
```
Expected: la cartella esiste col `.gitignore`.

- [ ] **Step 2: Registra lo stato "pulito" degli originali (baseline del cancello isolamento)**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git rev-parse HEAD > /tmp/qz_base_commit.txt
echo "baseline: $(cat /tmp/qz_base_commit.txt)"
```
Expected: stampa lo SHA corrente. Alla fine (Task 8) `git diff` sugli originali dovrà essere vuoto.

*(Nessun commit: solo scaffolding.)*

---

## Task 1: Accuratezza vs `nfrac` (copia di `run_fixed_sweep`, griglia estesa)

**Files:**
- Create: `matlab/Quantizzation_Study/qz_run_fixed_sweep.m`

- [ ] **Step 1: Copia `run_fixed_sweep.m` e modifica solo la griglia + l'output**

Copia byte-esatta, poi due modifiche mirate: la griglia `fracs` e la scrittura del risultato in TSV.
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
sed -e 's/function run_fixed_sweep()/function qz_run_fixed_sweep()/' \
    -e 's/fracs = \[5 7 9 11 13\];/fracs = [5 7 8 9 10 11 12 13];/' \
    run_fixed_sweep.m > Quantizzation_Study/qz_run_fixed_sweep.m
```
Poi, con Edit, aggiungi in fondo al corpo (prima dell'`end` della funzione principale) la scrittura TSV
`QZ/acc_sweep.tsv` con colonne `champion  nfrac  maxd`. Il resto (loop core `fi`, `snn_normalize`, `snn_decode`)
resta identico all'originale — è già corretto e gira sul dataset.

- [ ] **Step 2: Esegui e verifica la curva accuratezza sul dataset**

```bash
"$MATLAB" -batch "addpath(pwd); addpath(fullfile(pwd,'Quantizzation_Study')); qz_run_fixed_sweep" 2>&1 | tail -20
```
Expected: la tabella champion × nfrac di max|d|, **monotòna decrescente** al crescere di nfrac (a nfrac=13 vicino al floor double ~2e-6). File `Quantizzation_Study/acc_sweep.tsv` scritto.
⚠️ Se il core `fi` interpretato è troppo lento: MEXare copiando `snn_traj_fixed`+`build_traj_mex` in `qz_` e usando il MEX (mai ridurre il dataset).

- [ ] **Step 3: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study/qz_run_fixed_sweep.m matlab/Quantizzation_Study/.gitignore
git commit -m "feat(qz): accuratezza vs nfrac (qz_run_fixed_sweep, griglia estesa 5..13)"
```

---

## Task 2: Blocco a `nfrac` variabile + cancello bit-exact

**Files:**
- Create: `matlab/Quantizzation_Study/qz_gen_block_vhdl.m`

Oggi il forward `snn_b2_fsm.m` hardcoda `snn_types('fixed', 13)`. `qz_gen_block_vhdl(nfrac, outdir)` costruisce il blocco Donatello a quel `nfrac` in un **modello temporaneo** (NON tocca `snn_champions_lib.slx`) e ne genera il VHDL — riusando i mattoni condivisi già estratti (`mount_split`/`snn_chart_code`/`dec_chart_code`) e sostituendo `13→nfrac` nella copia in memoria del sorgente forward.

- [ ] **Step 1: Scrivi `qz_gen_block_vhdl.m`**

```matlab
function outdir = qz_gen_block_vhdl(nfrac, outdir)
%QZ_GEN_BLOCK_VHDL  Genera il VHDL del blocco Donatello (splitpipe, LUT-64) a un dato nfrac, in un
%  modello temporaneo (la libreria snn_champions_lib.slx NON viene toccata). Riusa i mattoni condivisi.
  mroot = fileparts(fileparts(mfilename('fullpath')));   % .../matlab
  gen_b2_rom('Donatello');
  srcRom   = fileread(fullfile(mroot,'b2_rom_active.m'));
  srcTypes = fileread(fullfile(mroot,'snn_types.m'));
  srcLut   = [fileread(fullfile(mroot,'snn_decode_lut.m')) newline newline ...
              fileread(fullfile(mroot,'decode_a.m'))  newline newline fileread(fullfile(mroot,'decode_a1.m')) newline newline ...
              fileread(fullfile(mroot,'decode_a2.m')) newline newline fileread(fullfile(mroot,'decode_b.m'))  newline newline ...
              fileread(fullfile(mroot,'decode_b1.m')) newline newline fileread(fullfile(mroot,'decode_b2.m')) newline newline ...
              fileread(fullfile(mroot,'decode_c.m'))  newline newline fileread(fullfile(mroot,'decode_c1.m')) newline newline ...
              fileread(fullfile(mroot,'decode_c2.m'))];
  % forward corrente (R9) con nfrac PARAMETRIZZATO: sostituisci l'unico 13 hardcoded
  srcFsm = fileread(fullfile(mroot,'snn_b2_fsm.m'));
  srcFsm = regexprep(srcFsm, "snn_types\('fixed',\s*13\)", sprintf("snn_types('fixed', %d)", nfrac));
  assert(contains(srcFsm, sprintf("snn_types('fixed', %d)", nfrac)), 'sostituzione nfrac fallita');
  d = load(fullfile(mroot,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  nrm = double(c.norm(:));

  mdl = 'qz_gen_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl); cleanup = onCleanup(@() close_system(mdl,0)); %#ok<NASGU>
  sub = [mdl '/Donatello']; add_block('built-in/Subsystem', sub);
  in_names={'s','v','dv','v_l'}; out_names={'v0','T','s0','a','b'};
  mount_split(sub, in_names, out_names, ...
    snn_chart_code(srcRom, srcTypes, srcFsm, nrm, true), ...
    dec_chart_code(srcLut, 'p5', 64, 'shared'));      % p5 = decode del deployato (FAST); vedi nota
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  rtl_gen_dut_local(sub, outdir);                     % makehdl del subsystem -> VHDL in outdir
end
```
> Nota decode: lo studio quant varia la **precisione del forward SNN** (nfrac), a decode fissato. Uso `p5`
> (il decode del blocco di riferimento). `rtl_gen_dut_local` = piccola copia di `rtl_gen_dut` che genera da un
> subsystem arbitrario (aggiungila come funzione locale, riusando la logica di `matlab/rtl_gen_dut.m`).

- [ ] **Step 2: Cancello — la parametrizzazione a `nfrac=13` è no-op (byte-identità del sorgente)**

A `nfrac=13` la sostituzione `13→13` NON deve cambiare nulla: il forward resta **byte-identico** all'originale
→ il VHDL è quello che genererebbe il forward hardcoded, e la correttezza è quella — già provata — del **mirror
`snn_b2_fsm ↔ snn_core`** (`run_b2_parity` 0/240000). *(Non si confronta con `Donatello_FAST`: quello usa lo
snapshot `snn_b2_fsm_R9`, che può differire dal forward corrente — sarebbe un falso mismatch.)*
Aggiungi in `qz_gen_block_vhdl`, **subito dopo** la `regexprep`, l'assert di no-op:
```matlab
  if nfrac == 13
    assert(isequal(srcFsm, fileread(fullfile(mroot,'snn_b2_fsm.m'))), 'param a 13 NON e'' no-op');
  end
```
Poi genera a 13 e verifica che passi + produca il VHDL:
```bash
"$MATLAB" -batch "addpath(pwd); addpath(fullfile(pwd,'Quantizzation_Study')); qz_gen_block_vhdl(13,'D:/zbd_qz/n13'); assert(~isempty(dir('D:/zbd_qz/n13/**/SNN.vhd')),'SNN.vhd assente'); disp('gen 13 OK')"
```
Expected: `gen 13 OK` (assert no-op superato, `SNN.vhd` presente). La correttezza a `nfrac<13` si legge dalla
**curva accuratezza** (Task 1), che è la misura diretta dell'effetto della quantizzazione.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_gen_block_vhdl.m
git commit -m "feat(qz): generazione VHDL del blocco Donatello a nfrac variabile (bit-exact a nfrac=13)"
```

---

## Task 3: Sintesi — risorse / potenza / Fmax vs `nfrac` (driver)

**Files:**
- Create: `matlab/Quantizzation_Study/qz_sweep_nfrac.sh`

Riusa **as-is** (non modificati) `study_tradeoff/common/{pin_determinism,synth_point,impl_point}.tcl`. Per ogni
`nfrac`: genera il VHDL (Task 2), poi `synth_point` → dcp, poi `impl_point` (`io`, vincolo deploy 125 ns) →
risorse+potenza+Fmax. Stessa parsing-by-position del log di `sweep_phase2.sh`.

- [ ] **Step 1: Scrivi `qz_sweep_nfrac.sh`**

```bash
#!/usr/bin/env bash
# Sweep di sintesi io-timed su nfrac (vincolo deploy fisso): risorse+potenza+Fmax per ogni nfrac.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
COMMON="$REPO/matlab/study_tradeoff/common"
PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
DEPLOY=125.000 ; TOP=Donatello
OUT=/d/zbd_qz/sweep ; mkdir -p "$OUT"
TSV="$REPO/matlab/Quantizzation_Study/res_sweep.tsv"
printf "nfrac\tWNS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tPtot_W\tPdyn_W\tPsta_W\n" > "$TSV"
for f in 5 7 8 9 10 11 12 13; do
  vd="D:/zbd_qz/n$f"
  "$MATLAB" -batch "addpath('$REPO/matlab'); addpath('$REPO/matlab/Quantizzation_Study'); qz_gen_block_vhdl($f,'$vd')" > "$OUT/gen_n$f.log" 2>&1
  src=$(dirname "$(find "$vd" -name 'SNN.vhd' | head -1)")
  [ -n "$src" ] || { echo "nfrac=$f: VHDL assente"; continue; }
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$OUT/n$f/synth" "pt" "$DEPLOY" "$TOP" > "$OUT/n$f/synth.log" 2>&1
  dcp="$OUT/n$f/synth/post_synth.dcp"; [ -f "$dcp" ] || { echo "nfrac=$f: synth ERR"; continue; }
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$DEPLOY" "$OUT/n$f/impl" "" "io" > "$OUT/n$f/impl.log" 2>&1
  L="$OUT/n$f/impl.log"
  g(){ grep -m1 "$1" "$L" | sed -E "$2"; }
  wns=$(g '^IMPL: WNS='   's/.*WNS=([-0-9.]+).*/\1/')
  del=$(g '^IMPL: ritardo=' 's/.*ritardo=([0-9.]+).*/\1/')
  fmx=$(g '^IMPL: ritardo=' 's/.*Fmax=([0-9.]+).*/\1/')
  lut=$(g '^IMPL-RES Slice LUTs' 's/.*= *//'); ff=$(g '^IMPL-RES Slice Registers' 's/.*= *//')
  dsp=$(g '^IMPL-RES DSPs' 's/.*= *//'); bram=$(g '^IMPL-RES Block RAM Tile' 's/.*= *//')
  pt=$(g 'IMPL-POWER Total On-Chip' 's/.*= *//'); pd=$(g 'IMPL-POWER Dynamic' 's/.*= *//'); ps=$(g 'IMPL-POWER Device Static' 's/.*= *//')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$f" "${wns:-NA}" "${del:-NA}" "${fmx:-NA}" "${lut:-NA}" "${ff:-NA}" "${dsp:-NA}" "${bram:-NA}" "${pt:-NA}" "${pd:-NA}" "${ps:-NA}" | tee -a "$TSV"
done
echo "=== res_sweep.tsv ===" ; column -t -s$'\t' "$TSV"
```

- [ ] **Step 2: Esegui in background (sintesi = lenta) e verifica il TSV**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
bash matlab/Quantizzation_Study/qz_sweep_nfrac.sh   # lanciare in background; ~8 nfrac x (synth+impl)
```
Expected: `res_sweep.tsv` con 8 righe; **LUT/FF/potenza monotòni decrescenti** al calare di `nfrac`; DSP/BRAM ~costanti. Ogni riga con `WNS` letto.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_sweep_nfrac.sh matlab/Quantizzation_Study/res_sweep.tsv
git commit -m "feat(qz): sweep sintesi io-timed vs nfrac (risorse+potenza+Fmax @deploy)"
```

---

## Task 4: Ginocchio + livelli candidati

**Files:**
- Create: `matlab/Quantizzation_Study/qz_knee.m`

- [ ] **Step 1: Scrivi `qz_knee.m` — incrocia accuratezza e risorse, propone i livelli**

```matlab
function levels = qz_knee()
%QZ_KNEE  Legge acc_sweep.tsv + res_sweep.tsv, stampa la tabella incrociata e propone i livelli:
%  il nfrac MINIMO dove max|d| e' ancora sotto una soglia comportamentale (default 0.05, il valore
%  sotto cui il car-following non degrada -- da confermare in Task 5), + un livello di margine (+2 bit).
  here = fileparts(mfilename('fullpath'));
  A = readtable(fullfile(here,'acc_sweep.tsv'),'FileType','text');   % champion nfrac maxd
  R = readtable(fullfile(here,'res_sweep.tsv'),'FileType','text');   % nfrac ... LUT ...
  % accuratezza peggiore fra i champion, per nfrac
  fr = unique(A.nfrac);
  worst = arrayfun(@(f) max(A.maxd(A.nfrac==f)), fr);
  fprintf('nfrac | max|d| (worst champ) | LUT | Ptot_W\n');
  for i=1:numel(fr)
    r = R(R.nfrac==fr(i),:);
    fprintf('%5d | %10.4g | %5s | %s\n', fr(i), worst(i), string(r.LUT), string(r.Ptot_W));
  end
  THR = 0.05;
  knee = min(fr(worst <= THR));
  levels = unique([knee, min(knee+2,13), 13]);   % ginocchio + margine + full-precision
  fprintf('GINOCCHIO (soglia max|d|<=%.3g): nfrac=%d ; livelli candidati per il menu: %s\n', THR, knee, mat2str(levels));
end
```

- [ ] **Step 2: Esegui e leggi i livelli**

```bash
"$MATLAB" -batch "addpath(fullfile(pwd,'Quantizzation_Study')); levels = qz_knee(); disp(levels)"
```
Expected: la tabella incrociata + una riga `GINOCCHIO … livelli candidati: [...]`. Annota i `levels`.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_knee.m
git commit -m "feat(qz): individuazione ginocchio + livelli candidati (accuratezza x risorse)"
```

---

## Task 5: Validazione car-following al ginocchio

**Files:**
- Create: `matlab/Quantizzation_Study/qz_cl_validate.m`

- [ ] **Step 1: Scrivi `qz_cl_validate.m` — anello chiuso per i livelli candidati**

Riusa il kernel closed-loop esistente (`snn_cl_step` + plant, dallo studio SP2/anello) copiandone la chiamata:
per ogni `nfrac` candidato, gira l'anello sul dataset col core a quel `nfrac` (`snn_types('fixed',nfrac)`) e
riporta la metrica car-following (errore di inseguimento / gap) **vs** il riferimento full-precision.
```matlab
function qz_cl_validate(levels)
%QZ_CL_VALIDATE  Car-following in anello chiuso per ciascun nfrac candidato; confronto vs full-precision.
%  Metrica: max|Δgap| e RMSE del gap sull'intero dataset (mai un caso singolo).
  mroot = fileparts(fileparts(mfilename('fullpath')));
  ds = load(fullfile(mroot,'test_dataset.mat')); tr = ds.trajectories;
  ref = qz_run_closed_loop(13, tr);                    % riferimento full-precision
  fprintf('nfrac | max|Δgap| | RMSE gap  (vs full-precision)\n');
  for f = levels(:).'
    cur = qz_run_closed_loop(f, tr);
    dgap = max(abs(cur.gap - ref.gap)); rmse = sqrt(mean((cur.gap - ref.gap).^2));
    fprintf('%5d | %9.4g | %9.4g\n', f, dgap, rmse);
  end
end
```
> `qz_run_closed_loop(nfrac, tr)` = copia mirata dell'anello esistente (`snn_cl_step`/plant), con
> `T = snn_types('fixed', nfrac)`. Restituisce la traiettoria di gap sul dataset intero.

- [ ] **Step 2: Esegui e conferma il ginocchio**

```bash
"$MATLAB" -batch "addpath(pwd); addpath(fullfile(pwd,'Quantizzation_Study')); qz_cl_validate([qz_knee()])" 2>&1 | tail -12
```
Expected: per il `nfrac` del ginocchio, `max|Δgap|`/`RMSE` **trascurabili** (car-following non degradato). Se il ginocchio degrada il gap, salire di 1 bit e ri-verificare (il gate corregge la scelta).

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_cl_validate.m
git commit -m "test(qz): validazione car-following in anello ai livelli candidati"
```

---

## Task 6: Configurazione canonica — Fmax massimo per ogni livello (bisezione)

**Files:**
- Create: `matlab/Quantizzation_Study/qz_fmax_bisect.sh`

- [ ] **Step 1: Scrivi `qz_fmax_bisect.sh` — passo adattivo sul vincolo di clock**

```bash
#!/usr/bin/env bash
# Per un dato nfrac, trova il Fmax MASSIMO stringendo il periodo a passo adattivo (limite su step_min).
#   qz_fmax_bisect.sh <nfrac> <P0_ns> <step0_ns> <step_min_ns>
set -uo pipefail
NF="$1"; P0="$2"; STEP0="$3"; STEPMIN="$4"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
COMMON="$REPO/matlab/study_tradeoff/common"
PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
OUT="/d/zbd_qz/fmax/n$NF"; mkdir -p "$OUT" ; TOP=Donatello
vd="D:/zbd_qz/n$NF"; [ -d "$vd" ] || "$MATLAB" -batch "addpath('$REPO/matlab'); addpath('$REPO/matlab/Quantizzation_Study'); qz_gen_block_vhdl($NF,'$vd')" >/dev/null 2>&1
src=$(dirname "$(find "$vd" -name 'SNN.vhd' | head -1)")
# UNA sola sintesi (dcp), poi molte implementazioni a periodi diversi (l'impl accetta il periodo)
"$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$OUT/synth" "pt" "$P0" "$TOP" >"$OUT/synth.log" 2>&1
dcp="$OUT/synth/post_synth.dcp"; [ -f "$dcp" ] || { echo "synth ERR"; exit 1; }
slack_at(){ # <P> -> echo WNS
  local P="$1" od="$OUT/P$P"; mkdir -p "$od"
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$P" "$od" "" "io" >"$od/impl.log" 2>&1
  grep -m1 '^IMPL: WNS=' "$od/impl.log" | sed -E 's/.*WNS=([-0-9.]+).*/\1/'
}
P="$P0"; step="$STEP0"; best="$P0"
while awk -v s="$step" -v m="$STEPMIN" 'BEGIN{exit !(s>=m)}'; do
  Ptry=$(awk -v p="$P" -v s="$step" 'BEGIN{printf "%.3f",p-s}')
  wns=$(slack_at "$Ptry")
  if awk -v w="$wns" 'BEGIN{exit !(w+0>=0)}'; then best="$Ptry"; P="$Ptry"; st="ok"; else step=$(awk -v s="$step" 'BEGIN{printf "%.3f",s/2}'); st="neg->step/2"; fi
  printf "  P=%-8s WNS=%-8s -> %s (best=%s step=%s)\n" "$Ptry" "$wns" "$st" "$best" "$step"
done
fmax=$(awk -v b="$best" 'BEGIN{printf "%.3f",1000.0/b}')
echo "nfrac=$NF  CONFIG CANONICA: P_max=$best ns  Fmax_max=$fmax MHz"
echo -e "$NF\t$best\t$fmax" >> "$REPO/matlab/Quantizzation_Study/canonical.tsv"
```

- [ ] **Step 2: Esegui per ogni livello (P0 dal Fmax-deploy del Task 3, step_min esplicito)**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
printf "nfrac\tP_max_ns\tFmax_max_MHz\n" > matlab/Quantizzation_Study/canonical.tsv
# per ciascun nfrac in `levels`: P0 = un periodo con slack >=0 (es. delay@deploy dal res_sweep), step0=4, step_min=0.25
bash matlab/Quantizzation_Study/qz_fmax_bisect.sh 9  20.0 4 0.25   # esempio: livello ginocchio
# ... ripeti per gli altri livelli in `levels` ...
column -t -s$'\t' matlab/Quantizzation_Study/canonical.tsv
```
Expected: per ogni livello, la convergenza a passo dimezzato (come da esempio utente: neg → step/2) fino a `step<step_min`, e una riga in `canonical.tsv` con `Fmax_max`. Ogni `P_max` è l'ultimo a WNS≥0.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_fmax_bisect.sh matlab/Quantizzation_Study/canonical.tsv
git commit -m "feat(qz): configurazione canonica per livello (Fmax massimo, bisezione a passo adattivo)"
```

---

## Task 7: Figure + documento dello studio

**Files:**
- Create: `matlab/Quantizzation_Study/qz_figs.py`, `document/QUANTIZATION_STUDY.md`

- [ ] **Step 1: Scrivi `qz_figs.py` — le quattro curve vs nfrac + ginocchio**

Legge `acc_sweep.tsv`, `res_sweep.tsv`, `canonical.tsv`; produce quattro PNG (accuratezza · LUT/FF · potenza ·
Fmax vs nfrac) in `Quantizzation_Study/figures/`, con il ginocchio marcato (linea verticale). Stile di
`scripts/figs_lut_sweep.py` (riusarne l'impostazione assi/colori). Solo matplotlib (no dipendenze esotiche).

- [ ] **Step 2: Genera le figure**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/Quantizzation_Study"
python qz_figs.py
ls figures/
```
Expected: quattro PNG in `figures/`.

- [ ] **Step 3: Scrivi `document/QUANTIZATION_STUDY.md`**

Doc grounded sui TSV: scopo, metodo (le 4 curve, il ginocchio, la config canonica), i dati (tabelle dai TSV),
le figure, e la sezione onestà (Fmax=margine → la config canonica è caratterizzazione del limite; potenza
static-dominata). Stile di `document/DECODE_LUT_SWEEP.md`. Chiude con i **livelli finali** (nfrac + Fmax_max)
pronti per il menu quantizzazione.

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study/qz_figs.py document/QUANTIZATION_STUDY.md
git commit -m "docs(qz): quattro figure + documento dello studio di quantizzazione"
```

---

## Task 8: Cancello di isolamento + chiusura

- [ ] **Step 1: Verifica che NESSUN originale sia stato toccato**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
echo "=== file modificati fuori da Quantizzation_Study/ e document/ (deve essere vuoto/atteso) ==="
git diff --stat "$(cat /tmp/qz_base_commit.txt)"..HEAD -- matlab/ ':(exclude)matlab/Quantizzation_Study/**' | grep -vE 'Quantizzation_Study' || echo "(nessun originale toccato)"
git status --porcelain
```
Expected: **nessun** file sotto `matlab/` fuori da `Quantizzation_Study/` risulta modificato → isolamento rispettato.

- [ ] **Step 2: Aggiorna lo stato di ripresa**

Aggiungi in `document/SESSION_RESUME.md` (backlog) una riga: studio di quantizzazione **FATTO**, con i livelli
finali e i puntatori (`Quantizzation_Study/`, `document/QUANTIZATION_STUDY.md`); nota che il **menu
quantizzazione** del blocco è la Fase successiva.

- [ ] **Step 3: Commit finale**

```bash
git add document/SESSION_RESUME.md
git commit -m "docs(qz): studio di quantizzazione completo nello stato di ripresa"
```

---

## Self-Review (svolto in scrittura)

- **Spec coverage:** §4 quattro curve → Task 1 (accuratezza) + Task 3 (risorse/potenza/Fmax). §5.2 blocco a nfrac → Task 2 (+ cancello bit-exact). §5.4 ginocchio → Task 4. §5.5 car-following → Task 5. §5.6 config canonica bisezione → Task 6. §6 figure/output → Task 7. §3.1 isolamento → Task 0 + Task 8 (cancello). §8 future work per-campo → non implementato per scelta (registrato in spec). Tutto coperto.
- **Placeholder scan:** codice reale per il nuovo (`qz_gen_block_vhdl`, `qz_sweep_nfrac.sh`, `qz_fmax_bisect.sh`, `qz_knee`); i riusi sono "copia + modifica mirata" con lo `sed`/Edit indicato. `qz_run_closed_loop`/`qz_figs.py` descritti puntando alla fonte esistente da copiare (`snn_cl_step`, `figs_lut_sweep.py`).
- **Consistenza nomi:** `nfrac`, `Quantizzation_Study/`, prefisso `qz_`, TSV `acc_sweep`/`res_sweep`/`canonical`, TOP `Donatello`, decode `p5` coerenti fra i task.

## Note di rischio (dalla spec §9)
- La parametrizzazione `13→nfrac` è blindata dal cancello bit-exact (Task 2 Step 2).
- Sintesi lente: Task 3 e 6 vanno in background; `qz_fmax_bisect` fa **una** synth + molte impl (più veloce).
- Se `snn_cl_step` non è il nome esatto del kernel closed-loop, usare `run_block_closed_loop_test` come fonte da copiare (verificare in Task 5).
