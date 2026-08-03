# SP4-M — ACC-IIDM time-mux (divisore condiviso) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o
> superpowers:executing-plans, task-by-task. Steps in checkbox (`- [ ]`).

**Goal:** recuperare l'Fmax dell'ACC-IIDM in fixed a **≥ 11,65 MHz** condividendo/sequenziando le 5 divisioni via
**resource sharing di HDL Coder** (un divisore riusato invece di 5 combinatori incatenati), **bit-identico a SP3
(`dmax = 0`)**.

**Architecture:** il blocco `Donatello_ACC_IIDM` è già l'IIDM fixed SP3 (`acc_types('fixed')`, `recipN=0` =
`divide()`). M **non cambia la sorgente** `acc_iidm_open`: applica il resource sharing come **configurazione HDL**
sul blocco. Il tool riusa hardware senza cambiare l'aritmetica → bit-identità **per costruzione** (da verificare).
Il **Task 1 è make-or-break**: se il resource sharing condivide *e* sequenzia i divisori (Fmax su, divisori giù)
→ M è config; **se no → FSM esplicita è un piano a sé** (non dettagliato qui, come L→M staged).

**Tech Stack:** MATLAB R2026a + HDL Coder (`hdlset_param`, `makehdl`) · Vivado 2026.1
(`C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`, `xc7z020clg400-1`) · Stateflow.

**Spec:** `docs/superpowers/specs/2026-07-16-acc-iidm-timemux-design.md`

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"` (Bash tool, path POSIX; la dir ha spazi, quota bene).
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, MAI nei `git add`**: `closed_loop_demo.slx`, `slblocks.m`, `axi/build/phase_b/results.csv`.
- **Verifiche sul DATASET, mai su un caso singolo** (riportare *quanti su quanti*).
- **Cancelli che devono restare verdi**: `run_plant_parity` (il **double non si muove di un bit** — e nel path
  resource-sharing la sorgente `acc_iidm_open` NON cambia, quindi è invariato per costruzione) ·
  `run_block_acciidm_test` · `run_block_closed_loop_test` · `run_block_hdl_gate`.
- **Numeri di riferimento (SP3, misurati):** catena IIDM `divide()` = **10846 LUT · 69 DSP · WNS −373 ns @8 MHz ·
  Fmax 2,0 MHz · 1077 livelli · path critico dentro l'IIDM (`acc_3_reg`)**. Bersaglio: **Fmax ≥ 11,65 MHz**.
- **Gotcha già pagati** (SP3, `document/SP3_ACC_IIDM_HDL.md`): la fimath è parte del tipo · niente riassegnazione
  di tipo · `if isempty(<persistent>)` letterale · no sovra-escape apici nelle chart · il messaggio VERO di un
  errore di chart si ha dando lo script a `codegen('-config:lib','SNN_ACC','-args',{a,a,a,a})` con `a=fi(0,1,32,20)`.

## File Structure
```
matlab/probe_acciidm_sharing.m   # NUOVO (scratch/diagnostico) — Task 1: prova le config di resource sharing,
                                 #   rigenera il VHDL del blocco isolato, riporta i file generati per la sintesi
scripts/synth_acc_iidm.tcl       # RIUSO — OOC su xc7z020 (LUT/DSP/Fmax/WNS/path critico)
matlab/build_hdl_variants.m      # MODIFICA (solo se Task 1 riesce) — bake della config sul blocco Donatello_ACC_IIDM_M
matlab/snn_champions_lib.slx     # rigenerato (solo se Task 1 riesce)
document/SP4_ACC_IIDM_FAST.md    # MODIFICA — aggiungere la sezione M (esito: config-based o → FSM)
document/SESSION_RESUME.md       # MODIFICA — stato M
```

---

## Task 1: VERIFICA il resource sharing di HDL Coder — make-or-break

**Files:** Create `matlab/probe_acciidm_sharing.m` (diagnostico); riuso `scripts/synth_acc_iidm.tcl`

L'obiettivo NON è ancora modificare la libreria: è **misurare** se il resource sharing condivide+sequenzia i 5
`divide()` del blocco esistente, mantenendo la funzione. Le config esatte di HDL Coder per condividere i divisori
sono ciò che questo task **scopre**; la sintesi OOC è il verdetto (ground truth), non un'opinione.

- [ ] **Step 1: scrivi `matlab/probe_acciidm_sharing.m`**

Genera il VHDL del blocco `Donatello_ACC_IIDM` in DUE modi — baseline (come SP3) e con resource sharing — in
cartelle separate, per confrontarli in sintesi. Il resource sharing si attiva con `hdlset_param` sul subsystem
del blocco prima di `makehdl`. Il parametro chiave è `SharingFactor` (quante istanze condividere); per
sequenziare serve che il tool schedi le operazioni condivise su cicli diversi (`ClockRatePipelining` /
oversampling). Si provano più combinazioni.

```matlab
function probe_acciidm_sharing()
%PROBE_ACCIIDM_SHARING  [SP4-M Task 1] Il resource sharing di HDL Coder condivide+sequenzia i 5 divide()
%  dell'ACC-IIDM? Genera il VHDL del blocco in piu' configurazioni, in cartelle separate, per la sintesi
%  OOC (verdetto: scripts/synth_acc_iidm.tcl). NON tocca la libreria committata.
  md = 'D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab';
  addpath(md);
  out = fullfile(md, 'hdl_sp4m'); if exist(out,'dir'), rmdir(out,'s'); end; mkdir(out);
  lib = 'snn_champions_lib';

  % config da provare: {tag, SharingFactor, ClockRatePipelining}
  cfgs = { 'baseline',  1,  'off'    % = SP3 (nessuna condivisione): riferimento
           'share5_cp', 5,  'on'     % condividi fino a 5 -> 1 divisore, sequenziato via clock-rate pipelining
           'share5',    5,  'off' }; % condividi senza clock-rate pipelining (vediamo se sequenzia lo stesso)

  for i = 1:size(cfgs,1)
    tag = cfgs{i,1}; sf = cfgs{i,2}; crp = cfgs{i,3};
    bdclose('all'); load_system(fullfile(md,[lib '.slx'])); set_param(lib,'Lock','off');
    mdl = ['m_' tag]; if bdIsLoaded(mdl), close_system(mdl,0); end
    new_system(mdl); load_system(mdl);
    add_block([lib '/Donatello_ACC_IIDM'], [mdl '/DUT']);
    add_block('simulink/Sources/Constant',[mdl '/i1'],'Value','10','OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_block('simulink/Sources/Constant',[mdl '/i2'],'Value','6', 'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_block('simulink/Sources/Constant',[mdl '/i3'],'Value','2', 'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_block('simulink/Sources/Constant',[mdl '/i4'],'Value','4', 'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    for j=1:4, add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]); end
    add_block('built-in/Outport',[mdl '/o'],'Port','1'); add_line(mdl,'DUT/1','o/1');
    set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
    % config di sharing sul DUT
    try, hdlset_param([mdl '/DUT'], 'SharingFactor', sf); catch e, fprintf('[%s] SharingFactor: %s\n',tag,e.message); end
    try, hdlset_param(mdl, 'ClockRatePipelining', crp); catch e, fprintf('[%s] ClockRatePipelining: %s\n',tag,e.message); end
    tgt = fullfile(out, tag);
    try
      set_param(mdl,'SimulationCommand','update');
      makehdl([mdl '/DUT'],'TargetLanguage','VHDL','TargetDirectory',tgt,'GenerateHDLTestBench','off');
      v = dir(fullfile(tgt,'**','*.vhd'));
      fprintf('>> %-10s SharingFactor=%d CRP=%s : VHDL OK (%d file, %d byte) -> %s\n', tag, sf, crp, numel(v), sum([v.bytes]), tgt);
    catch e
      fprintf('>> %-10s FALLITO: %s\n', tag, regexprep(e.message,'\s+',' '));
    end
    close_system(mdl,0);
  end
  close_system(lib,0);
  fprintf('\nVHDL per la sintesi OOC in %s (una cartella per config)\n', out);
end
```

- [ ] **Step 2: genera il VHDL nelle 3 config**

Run: `matlab -batch "cd('<matlabdir>'); probe_acciidm_sharing"`
Expected: 3 righe `>> <tag> ... VHDL OK` (o `FALLITO` con messaggio). Se `share5_cp`/`share5` FALLISCONO alla
generazione: leggi il messaggio; se `SharingFactor`/`ClockRatePipelining` non è un parametro valido per una
MATLAB Function chart, **è già un dato** (il resource sharing non si applica così → orienta verso la FSM).

- [ ] **Step 3: sintesi OOC delle config generate — IL VERDETTO**

Per ogni cartella prodotta (`baseline`, e le `share*` che hanno generato VHDL):
Run (Git Bash):
```bash
V="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
cd "<worktree>"
for t in baseline share5_cp share5; do
  [ -d "matlab/hdl_sp4m/$t" ] && "$V" -mode batch -notrace -source scripts/synth_acc_iidm.tcl \
     -tclargs "matlab/hdl_sp4m/$t" "matlab/hdl_sp4m/out_$t" "$t" 2>&1 | grep -E "^RESULT|^CRITPATH"
done
```
Expected: una riga `RESULT <tag> LUT=… DSP=… WNS=… Fmax=…` per config. **`baseline` deve riprodurre SP3** (~10846
LUT, ~2,0 MHz): è il controllo che il flusso è coerente. Poi guarda le `share*`.

- [ ] **Step 4: DECISIONE sui numeri**

Criterio di successo di M-v1 (config-based):
- **Fmax ≥ 11,65 MHz** su una config `share*`, **e**
- **conteggio divisori/DSP ridotto** e/o path critico **non più nelle divisioni incatenate** (leggi `CRITPATH`).

- Se **una `share*` centra il bersaglio** → **Task 1 riuscito**, si va al Task 2 (bake nella libreria + verifica
  funzionale). Annota la config vincente (`SharingFactor`, `ClockRatePipelining`).
- Se **nessuna** centra il bersaglio (Fmax < 11,65, o non condivide, o non sequenzia) → **Task 1 dà l'esito
  "config non basta"**: si **ferma qui il piano** e la **FSM esplicita diventa un piano a sé** (spec §4.1). NON
  improvvisare la FSM in questo task. Documenta i numeri (servono a giustificare la FSM) e salta al Task 3 (doc).

- [ ] **Step 5: Commit del diagnostico**

```bash
git add matlab/probe_acciidm_sharing.m
git commit -m "test(sp4-m): probe_acciidm_sharing - verifica resource sharing HDL Coder sui 5 divide() (make-or-break)"
```
(Il VHDL generato `matlab/hdl_sp4m/` è gitignorato come `hdl_sp3` — aggiungilo al `.gitignore` se non coperto.)

---

## Task 2: (SOLO se Task 1 riesce) bake nella libreria + verifica funzionale

**Files:** Modify `matlab/build_hdl_variants.m`, rigenera `matlab/snn_champions_lib.slx`

Applica la config di sharing vincente al blocco nel builder, così il blocco HDL-ready la porta con sé, e verifica
che la funzione sia **bit-identica** (il resource sharing non deve cambiare l'aritmetica).

- [ ] **Step 1: applica la config di sharing nel builder**

In `matlab/build_hdl_variants.m`, dopo la creazione del blocco `Donatello_ACC_IIDM` (dopo la riga
`fprintf('  costruito Donatello_ACC_IIDM (SP2/SP3, HDL-ready)\n');`), aggiungi la config HDL vincente del Task 1
(esempio con la config `share5_cp`; **sostituire coi valori VERI vincenti**):
```matlab
  % SP4-M: resource sharing dei 5 divide() -> 1 divisore sequenziato (Fmax >= 11.65 MHz). Config
  % vincente misurata in Task 1 (probe_acciidm_sharing + sintesi OOC). La sorgente acc_iidm_open NON
  % cambia: e' solo configurazione HDL sul blocco -> bit-identico a SP3 per costruzione.
  hdlset_param([lib '/Donatello_ACC_IIDM'], 'SharingFactor', 5);
  hdlset_param(lib, 'ClockRatePipelining', 'on');
```

- [ ] **Step 2: rigenera la libreria**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; disp('rigenerata')"`
Expected: `rigenerata`, nessun errore.

- [ ] **Step 3: dmax = 0 vs SP3 sul dataset (bit-identità)**

La config di sharing è HDL-only: la SIMULAZIONE del blocco è invariata, quindi `dmax` deve restare **0**.
Run: `matlab -batch "cd('<matlabdir>'); for t=[1 6 12 20 30], run_block_acciidm_test(12,t,400); end"`
Expected: `dmax(accel) = 0` su **5/5**. Se `dmax > 0` → la config ha cambiato la simulazione (non dovrebbe):
**fermarsi**, il resource sharing HDL non deve toccare il comportamento del modello.

- [ ] **Step 4: anello chiuso + gate HDL**

Run: `matlab -batch "cd('<matlabdir>'); run_block_closed_loop_test(1,40,400,'train'); run_block_hdl_gate('Donatello_ACC_IIDM')"`
Expected: anello chiuso `dmax = 0` + `GATE PASSATO` (VHDL + `DualPortRAM`).

- [ ] **Step 5: OOC di conferma dal blocco della libreria**

Rigenera il VHDL dal blocco (via `run_block_hdl_gate` o `makehdl`) e risintetizza per confermare che l'Fmax dalla
LIBRERIA coincide col Task 1:
Run: `matlab -batch "cd('<matlabdir>'); load_system('snn_champions_lib'); makehdl('snn_champions_lib/Donatello_ACC_IIDM','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp4m','lib'),'GenerateHDLTestBench','off'); close_system('snn_champions_lib',0)"`
poi `vivado ... synth_acc_iidm.tcl -tclargs matlab/hdl_sp4m/lib matlab/hdl_sp4m/out_lib MLIB | grep RESULT`
Expected: `Fmax ≥ 11,65 MHz`, coerente col Task 1.

- [ ] **Step 6: Commit**

```bash
git add matlab/build_hdl_variants.m matlab/snn_champions_lib.slx
git commit -m "feat(sp4-m): Donatello_ACC_IIDM time-mux via resource sharing (Fmax >= 11.65 MHz, dmax=0)"
```

---

## Task 3: documentazione + stato

**Files:** Modify `document/SP4_ACC_IIDM_FAST.md`, `document/SESSION_RESUME.md`

- [ ] **Step 1: aggiorna `document/SP4_ACC_IIDM_FAST.md`**

Aggiungi una sezione **`## Variante M — time-mux (divisore condiviso)`** con:
- il meccanismo usato (resource sharing config, oppure "config non basta → FSM è il prossimo piano");
- la tabella OOC: `baseline` (=SP3) vs `share*` — LUT/DSP/Fmax/WNS/path critico;
- il verdetto: M-v1 centra 11,65 MHz? di quanto scendono i divisori? `dmax=0` confermato.
Numeri VERI dai Task 1-2, mai segnaposto.

- [ ] **Step 2: aggiorna `document/SESSION_RESUME.md`**

Nella sezione SP4: da "prossimo = M" a "M-v1 fatto (config-based)" **oppure** "M-v1: resource sharing non basta →
FSM esplicita = prossimo piano" (a seconda del Task 1). Se rilevante, nota la **v2** (sequenziare tutto) come
confronto successivo.

- [ ] **Step 3: cancelli finali + Commit + push**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity; run_block_acciidm_test(12,1,400); run_block_hdl_gate('Donatello_ACC_IIDM'); run_block_hdl_gate('Donatello_Champion'); disp('>>>> VERDI <<<<')"`
Expected: `ALL PLANT PARITY PASS` · `dmax=0` · `GATE PASSATO` ×2 · `VERDI`.
```bash
git add document/SP4_ACC_IIDM_FAST.md document/SESSION_RESUME.md
git commit -m "docs(sp4-m): esito time-mux (resource sharing) + stato"
git push origin Simulink_Importer
```

---

## Self-review (copertura della spec)
- **§1 scopo** (Fmax ≥ 11,65 via divisore condiviso, dmax=0): Task 1 (misura) + Task 2 (bit-identità). ✓
- **§4.1 meccanismo** (resource sharing PRIMA, verifica; FSM fallback = piano a sé): Task 1 Steps 1-4 (esperimento
  + decisione); il fallback NON è dettagliato qui, come richiesto. ✓
- **§4.2 granularità v1** (solo le 5 divisioni): Task 1 condivide i `divide()`, il resto invariato. ✓
- **§4.3 v2** (sequenziare tutto, dopo): fuori da questo piano; nota nel Task 3 Step 2. ✓
- **§5 verifica** (dmax=0 vs SP3 · closed-loop · hdl_gate · OOC Fmax≥11,65 + divisori giù): Task 2 Steps 3-5. ✓
- **§6 fuori scope** (overlap, slack-minima, bitstream): nessun task li tocca. ✓
- **run_plant_parity invariato**: il path resource-sharing non tocca `acc_iidm_open` (config sul blocco) →
  invariato per costruzione; comunque incluso nel Task 3 Step 3. ✓
- **Coerenza**: `Donatello_ACC_IIDM` (blocco esistente) · `scripts/synth_acc_iidm.tcl` (RESULT/CRITPATH) ·
  `run_block_acciidm_test`/`run_block_closed_loop_test`/`run_block_hdl_gate` — tutti nomi reali del progetto. ✓
