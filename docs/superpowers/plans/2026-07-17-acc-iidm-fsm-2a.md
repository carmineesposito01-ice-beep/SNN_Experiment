# SP4-M-FSM #2a — la FSM riusa UNA `divide()` (1 divisore condiviso) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o
> superpowers:executing-plans, task-by-task. Steps in checkbox (`- [ ]`).

**Goal:** semplificare `Donatello_ACC_IIDM_M` a **sola chart** con una FSM che riusa **UNA** `divide()` per le
5 divisioni (1 divisore condiviso), e **MISURARE in OOC Fmax e area** — il dato mai ottenuto.

**Architecture:** il blocco torna 4 ingressi / 1 uscita come SP3 (via blocco `Divide`, Unit Delay, handshake,
feedback → niente conversione dataflow → `tanh` fixed nativa → il VHDL si genera). Nel codice della chart c'è
**una sola** chiamata a `fsm_div` dentro uno stato della FSM: `kdiv` è **stato**, non indice di loop.
Bit-identità **garantita per costruzione** (`fsm_div` *è* la `divide()` di SP3). Funzioni-fase, model e
cancelli: **invariati**.

**Tech Stack:** MATLAB R2026a + HDL Coder · Fixed-Point Designer · Vivado 2026.1 (`xc7z020clg400-1`).

**Spec:** `docs/superpowers/specs/2026-07-17-acc-iidm-fsm-2a-design.md`
**Contesto (perché #1 è morto):** `document/SP4_ACC_IIDM_FAST.md` §Variante M-FSM · `document/HDL_PHASE.md` §9

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"` (Bash, path POSIX, quotare: la dir ha spazi). Lavoro lungo → **background** + checkpoint.
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, MAI nei `git add`**: `matlab/closed_loop_demo.slx`, `matlab/slblocks.m`, `matlab/*.mexw64`.
- **Cancelli:** dataset intero, `assert`, provati sensibili. Riportare *quanti su quanti*.
- **Numeri di riferimento (misurati):** SP3 catena IIDM = **10846 LUT · 1653 FF · 69 DSP · WNS −373 ns ·
  Fmax 2,0 MHz · 1077 livelli**, con **CARRY4 = 820 (76%)** dai 5 divisori. M-v1 config = **25557 LUT ·
  22922 FF · 38 DSP · 9,51 MHz** (area esplosa). Bersaglio di #2a: **area ≪ SP3 e ≪ M-v1**, Fmax **misurata**.
- **NON toccare** `snn_types`/`acc_types`/`acc_iidm_open`/le funzioni-fase: sono validati e fuori scope.

## File Structure
```
matlab/build_hdl_variants.m        # MODIFICA: Donatello_ACC_IIDM_M -> sola chart + FSM 1-divide/ciclo
matlab/run_block_acciidm_m_test.m  # MODIFICA minima: hold di default coerente con la latenza attesa (~346)
matlab/iidm_prep.m|iidm_nd.m|iidm_use.m|iidm_final.m|fsm_div.m   # INVARIATI (single-source, validati G2)
matlab/acc_iidm_fsm.m|fsm_step.m|run_acciidm_m_dataset.m         # INVARIATI (il model non cambia)
matlab/run_block_hdl_gate.m · scripts/synth_acc_iidm.tcl         # RIUSO (G5 · G6)
document/SP4_ACC_IIDM_FAST.md · document/SESSION_RESUME.md       # MODIFICA (Task 5)
```

---

## Task 1: il blocco torna sola chart, con la FSM che riusa una `divide()`

**Files:** Modify `matlab/build_hdl_variants.m`

- [ ] **Step 1: sostituisci la costruzione del blocco M**

In `build_hdl_variants.m`, il blocco `Donatello_ACC_IIDM_M` va ricostruito **senza** `DIV`, `z_q`, `z_v`, le
linee di feedback, l'`hdlset_param(...,'Architecture',...)` e i `set_param` sui tipi di `quot`/`vout` (erano
tutti al servizio del blocco `Divide` di #1). Deve restare **solo la chart**, come il blocco SP3 sopra:

```matlab
  subM = [lib '/Donatello_ACC_IIDM_M'];
  if getSimulinkBlockHandle(subM) > 0, delete_block(subM); end
  add_block('built-in/Subsystem', subM, 'Position', [300, 100, 500, 160], ...
            'Description', acciidm_m_description(NCHAMP));
  add_block('simulink/User-Defined Functions/MATLAB Function', [subM '/IIDM_CTRL']);
  chartM = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [subM '/IIDM_CTRL']);
  chartM.Script = acciidm_m_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcAccT, ...
                                       srcFDiv, srcPrep, srcNd, srcUse, srcFinal, nrm);
  for j = 1:4
    add_block('built-in/Inport', [subM '/' in_names{j}], 'Port', num2str(j));
    add_line(subM, [in_names{j} '/1'], ['IIDM_CTRL/' num2str(j)]);
  end
  add_block('built-in/Outport', [subM '/accel'], 'Port', '1');
  add_line(subM, 'IIDM_CTRL/1', 'accel/1');
  fprintf('  costruito Donatello_ACC_IIDM_M (SP4-M-FSM #2a: 5 divisioni su 1 divide() condivisa)\n');
```

- [ ] **Step 2: sostituisci il corpo della chart (`acciidm_m_chart_code`, la parte `Lmain`)**

`kdiv` è **variabile di STATO**: NON usare `for k = 1:5` (il codegen lo srotola → 5 divisori: giusto per il
model, **letale** qui). Una sola chiamata a `fsm_div` in tutto il sorgente:

```matlab
  Lmain = {
    'function accel = IIDM_CTRL(s, v, dv, v_l)'
    '%#codegen'
    '% SP4-M-FSM #2a - Donatello + ACC-IIDM con le 5 divisioni sequenziate su UNA divide() condivisa.'
    '%  UNA sola chiamata a fsm_div in tutto il sorgente, dentro uno stato della FSM -> HDL Coder genera'
    '%  UN divisore, riusato in 5 cicli (kdiv e'' STATO, non indice di loop: un for k=1:5 verrebbe'
    '%  SROTOLATO -> 5 divisori). Nessun blocco accanto alla chart -> niente conversione dataflow ->'
    '%  tanh fixed nativa (HDL_PHASE §9). La matematica NON e'' qui: sta nelle funzioni-fase (G2).'
    '  Tt = snn_types(''fixed'', 13);'
    '  Ta = acc_types(''fixed'');'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent pv xprev started acc phase kdiv st alf vlp'
    '  if isempty(started)'
    '    pv = fi(zeros(5,1), 1, 21, 13);'
    '    xprev = xn; started = true;'
    '    acc = cast(0, ''like'', Ta.out);'
    '    phase = uint8(0); kdiv = uint8(1);'
    '    alf = cast(0, ''like'', Ta.acc); vlp = cast(v_l, ''like'', Ta.st);'
    '    % `pv(:)` (fi) e NON zeros(5,1) (double): due tipi diversi di `p` darebbero DUE specializzazioni'
    '    % di iidm_prep, in silenzio.'
    '    [st, alf, vlp] = iidm_prep(s, v, dv, v_l, pv(:), true, alf, vlp);'
    '    go = true;'
    '  else'
    '    go = any(xn ~= xprev);             % edge-triggered: 1 campione = 1 inferenza (§3.1.4)'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    ['    pv = snn_decode_lut(raw, ' num2str(N) ');']
    '    [st, alf, vlp] = iidm_prep(s, v, dv, v_l, pv(:), false, alf, vlp);   % 1 volta per control-step (§5)'
    '    kdiv = uint8(1); phase = uint8(1);'
    '  end'
    '  if phase == 1                        % RUN: UNA divisione per ciclo'
    '    [num, den] = iidm_nd(kdiv, st);'
    '    q = fsm_div(num, den);             % <== UNICA chiamata nel sorgente: UN divisore in HDL'
    '    st = iidm_use(kdiv, q, st);'
    '    if kdiv >= 5'
    '      acc = iidm_final(st);            % DONE: accel tenuta fino al control-step successivo'
    '      phase = uint8(0);'
    '    else'
    '      kdiv = kdiv + 1;'
    '    end'
    '  end'
    '  accel = acc;'
    'end'
  };
```

- [ ] **Step 3: aggiorna la Description (`acciidm_m_description`)**

Il vincolo di rate cambia (~346 clk atteso, non ~510) e l'architettura non ha più il blocco Divide. Sostituisci
il paragrafo `COS''E''` e il `⚠️ VINCOLO DI RATE` con:
```matlab
    'COS''E'' (SP4-M-FSM #2a)'
    '  Variante di Donatello_ACC_IIDM: le 5 divisioni a divisore variabile non sono piu'' 5 divisori'
    '  combinatori INCATENATI (1077 livelli, Fmax 2,0 MHz), ma UNA sola divide() riusata da una macchina'
    '  a stati, una divisione per ciclo. Scopo: tagliare l''area tenendo dmax=0.'
    ''
    '⚠️ VINCOLO DI RATE (DIVERSO da Donatello_ACC_IIDM)'
    '  Una inferenza costa la SNN time-mux (~341 clock) PIU'' 5 cicli (uno per divisione). Ogni ingresso'
    '  va tenuto per piu'' campioni che nel blocco SP3: il valore esatto lo MISURA'
    '  run_block_acciidm_m_test (non e'' assunto). Sull''FPGA e'' irrilevante: un control-step da 0,1 s'
    '  dura 800.000 clock a 8 MHz.'
```

- [ ] **Step 4: rigenera la libreria e verifica che la chart COMPILI**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; bdclose('all'); load_system('snn_champions_lib'); mdl='tstM'; new_system(mdl); load_system(mdl); add_block('snn_champions_lib/Donatello_ACC_IIDM_M',[mdl '/DUT']); vals={'10','6','2','4'}; for j=1:4; add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)],'Value',vals{j},'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1'); add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]); end; add_block('built-in/Outport',[mdl '/o'],'Port','1'); add_line(mdl,'DUT/1','o/1'); set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','800','SaveOutput','on','SaveFormat','Array'); set_param(mdl,'SimulationCommand','update'); disp('CHART COMPILA'); so=sim(mdl); y=so.get('yout'); fprintf('accel finale=%.6g | primo passo non-zero=%d\n', y(end), find(y~=0,1)); close_system(mdl,0)"`
Expected: `CHART COMPILA` e un `primo passo non-zero` intorno a **~346** (era 510 con l'handshake di #1).
> Se la chart non compila: il messaggio VERO si ottiene da `codegen`, non da Simulink (che stampa solo
> "Errors occurred during parsing of ..."). Vedi `document/SP2_ACC_IIDM.md` §Gotcha.

- [ ] **Step 5: Commit**
```bash
git add matlab/build_hdl_variants.m matlab/snn_champions_lib.slx
git commit -m "feat(sp4-m-fsm-2a): blocco M = sola chart + FSM che riusa UNA divide() (1 divisore)"
```

---

## Task 2: G2 + G3/G4 — la semplificazione non deve muovere un bit

**Files:** Modify `matlab/run_block_acciidm_m_test.m`

- [ ] **Step 1: allinea il default di `hold` alla nuova latenza**

In `run_block_acciidm_m_test.m` cambia il default `hold = 700` → `hold = 500` (> ~346, con margine) e nel
commento della funzione sostituisci "~510 clk in totale" con "~346 clk (341 SNN + 5 divisioni)". La latenza
resta **misurata** dal test (`lat = chg(1)`), non assunta: il default serve solo a dare margine.

- [ ] **Step 2: G3/G4 su 5 traiettorie**

Run: `matlab -batch "cd('<matlabdir>'); for t=[1 6 12 20 30]; run_block_acciidm_m_test(12, t, 500); end; disp('>>> G3/G4: 5/5 PASSATE <<<')"`
Expected per ogni traiettoria: `G4: latenza = <~346> clock ; ingresso costante -> 1 sola inferenza` e
`dmax vs model=0 | vs SP3=0`, poi `>>> G3/G4: 5/5 PASSATE <<<`.
> `dmax != 0` qui significherebbe che la FSM in-chart non riproduce il model: guarda l'orchestrazione
> (`kdiv`/`phase`/latch di `st`), NON la matematica — quella la copre G2.

- [ ] **Step 3: G2 sul dataset intero (il model non è cambiato: deve restare verde)**

Run: `matlab -batch "cd('<matlabdir>'); run_acciidm_m_dataset()"`  (~13 min)
Expected: `dmax=0 | divergenti 0/60000 control-step (60 traiettorie)` → `G2 PASSATO`.

- [ ] **Step 4: Commit**
```bash
git add matlab/run_block_acciidm_m_test.m
git commit -m "test(sp4-m-fsm-2a): G3/G4 su 5 traj (dmax=0 vs model e SP3) + latenza misurata; G2 0/60000"
```

---

## Task 3: G5 — il cancello che #1 non superava

**Files:** riuso `matlab/run_block_hdl_gate.m` (nessuna modifica attesa)

- [ ] **Step 1: gate self-contained sul blocco M**

Run: `matlab -batch "cd('<matlabdir>'); run_block_hdl_gate('Donatello_ACC_IIDM_M')"`
Expected: `isolamento OK` · elenco dei `.vhd` · `time-mux (DualPortRAM presente): true` ·
`=== GATE PASSATO: Donatello_ACC_IIDM_M e' self-contained e HDL-ready ===`.
> **È il punto di svolta rispetto a #1**: qui #1 falliva con *"Struct in expression 'T' has an empty-typed
> field … MATLAB-to-dataflow"* e poi *"tanh is not supported for numerictype(1,19,8)"*. Se `tanh` ricompare,
> significa che nel subsystem è rimasto un blocco accanto alla chart (`HDL_PHASE.md` §9): controlla che
> `DIV`/`z_q`/`z_v` siano davvero spariti dal Task 1.

- [ ] **Step 2: G5 anche su SP3 e Champion (nessuna regressione)**

Run: `matlab -batch "cd('<matlabdir>'); run_block_hdl_gate('Donatello_ACC_IIDM'); bdclose('all'); run_block_hdl_gate('Donatello_Champion')"`
Expected: `GATE PASSATO` per entrambi.

---

## Task 4: G6 — OOC: **il punto del piano** (Fmax e area MISURATE)

**Files:** riuso `scripts/synth_acc_iidm.tcl`

- [ ] **Step 1: genera il VHDL del blocco M**

Run: `matlab -batch "cd('<matlabdir>'); load_system('snn_champions_lib'); makehdl('snn_champions_lib/Donatello_ACC_IIDM_M','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp4m2a','m'),'GenerateHDLTestBench','off'); close_system('snn_champions_lib',0)"`
Expected: `HDL code generation complete`, con `DualPortRAM_generic.vhd` fra i file.
Aggiungi `matlab/hdl_sp4m2a/` a `.gitignore` (accanto a `matlab/hdl_sp4m/`).

- [ ] **Step 2: sintesi OOC (background: minuti)**

Run: `"C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -notrace -log <scratch>/viv_2a.log -journal <scratch>/viv_2a.jou -source scripts/synth_acc_iidm.tcl -tclargs "matlab/hdl_sp4m2a/m" "matlab/hdl_sp4m2a/out" "fsm2a"` (dalla root del worktree), poi `grep -E "^RESULT|^CRITPATH"`.
Expected: righe `RESULT fsm2a LUT=… FF=… DSP=… WNS=… Fmax=…` e `CRITPATH fsm2a from=… to=… logic_levels=… delay=…`.

- [ ] **Step 3: verifica l'ASSUNTO "1 chiamata = 1 divisore" — non crederlo, misuralo**

Confronta `RESULT fsm2a` con i riferimenti misurati:
| | LUT | Fmax | lettura |
|---|---|---|---|
| SP3 (5 divisori incatenati) | 10846 | 2,0 MHz | baseline |
| M-v1 config (1 div + clock-rate pipelining) | 25557 | 9,51 MHz | area esplosa |
| **#2a atteso** | **≪ 10846** | ~9,5 MHz (path = 1 divisione) | 1 divisore condiviso |

- **LUT ≈ 10846 (o più)** → HDL Coder **NON** ha condiviso: ha generato 5 divisori (o li ha srotolati).
  **L'assunto è falso e #2a non ha senso**: fermarsi, documentare il numero, e la strada resta #2b.
  Diagnosi: `CRITPATH` e il conteggio dei divisori nel VHDL (`grep -c "quotient" matlab/hdl_sp4m2a/m/**/*.vhd`,
  confrontato con lo stesso conteggio sul VHDL di SP3).
- **LUT sensibilmente < 10846** → l'assunto regge: **#2a ha tagliato l'area a `dmax=0`**.
- **Fmax < 11,65** → **atteso, NON è un fallimento** (spec §6): è il dato che qualifica #2b.

- [ ] **Step 4: checkpoint utente coi numeri** — riporta `RESULT`/`CRITPATH` e il confronto con SP3/M-v1
  **prima** di proseguire. È la decisione su #2b, e non è tua.

---

## Task 5: doc + cancelli finali + push

**Files:** Modify `document/SP4_ACC_IIDM_FAST.md`, `document/SESSION_RESUME.md`, `.gitignore`

- [ ] **Step 1: cancelli finali (tutti verdi)**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity; run_acciidm_m_dataset(2); run_block_acciidm_m_test(12,1,500); run_block_hdl_gate('Donatello_ACC_IIDM_M'); run_block_hdl_gate('Donatello_Champion'); disp('>>>> VERDI <<<<')"`
Expected: `ALL PLANT PARITY PASS` · `G2 PASSATO` · `G3/G4 PASSATI` · `GATE PASSATO` ×2 · `VERDI`.

- [ ] **Step 2: `document/SP4_ACC_IIDM_FAST.md`** — aggiungi `### Variante M-FSM #2a (esito)` **dopo**
  §Variante M-FSM: architettura (sola chart, 1 `divide()` riusata), tabella OOC **SP3 vs M-v1 vs #2a**
  (LUT/FF/DSP/Fmax/CRITPATH, numeri VERI dal Task 4), latenza misurata, esito dell'assunto "1 chiamata = 1
  divisore", e la decisione su #2b presa **coi numeri**. Aggiorna la tabella delle strade in testa al file.

- [ ] **Step 3: `document/SESSION_RESUME.md`** — blocco ▶ (stato in una riga + azione pendente) e sezione
  `## SP4`: da "resta #2" a "#2a fatto (Fmax=…, area=…, dmax=0)" + la decisione su #2b.

- [ ] **Step 4: Commit + push**
```bash
git add document/SP4_ACC_IIDM_FAST.md document/SESSION_RESUME.md .gitignore
git commit -m "docs(sp4-m-fsm-2a): esito #2a (Fmax/area misurate, dmax=0) + decisione su #2b"
git push origin Simulink_Importer
```

---

## Self-review (copertura della spec)
- **§1 scopo** (area giù + `dmax=0` + produrre il dato): Task 4 (G6) · Task 2 (G2/G3/G4). ✓
- **§3 architettura** (sola chart, 4 in/1 out, via Divide/UnitDelay/handshake): Task 1 Step 1-2. ✓
- **§3 assunto "1 chiamata = 1 divisore" DA MISURARE**: Task 4 Step 3 (criterio esplicito in entrambi i versi). ✓
- **§4 data flow** (FSM 1 divisione/ciclo, `kdiv` stato non loop, DT inline): Task 1 Step 2 (+ warning). ✓
- **§4 latenza ~346 misurata**: Task 1 Step 4 (primo passo non-zero) + Task 2 Step 1-2 (G4 la misura). ✓
- **§5 bit-identità**: Task 2 (G2 dataset + G3 vs model **e** vs SP3). ✓
- **§6 cancelli G2/G3/G4/G5/G6/G7 + criterio di successo**: Task 2 · Task 3 · Task 4 · Task 5 Step 1. ✓
- **§7 file** (invariati: funzioni-fase, model, cancelli): rispettato — si toccano solo `build_hdl_variants`,
  `run_block_acciidm_m_test` (default `hold`), doc, `.gitignore`. ✓
- **§8 fuori scope** (#2b, overlap, bitstream, `snn_types`/`acc_types`): nessun task li tocca; #2b è una
  **decisione dell'utente** al checkpoint del Task 4 Step 4. ✓
- **Coerenza nomi**: `Donatello_ACC_IIDM_M` · `IIDM_CTRL` · `fsm_div`/`iidm_nd`/`iidm_use`/`iidm_final`/
  `iidm_prep` · `run_block_acciidm_m_test` · `run_acciidm_m_dataset` · G2..G7 — coerenti col codice esistente. ✓
