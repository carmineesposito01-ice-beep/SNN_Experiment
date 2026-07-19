# IIDM — divisore PIPELINATO (rianimare SP4 #1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alzare l'`Fmax` del controllore `Donatello_ACC_IIDM_M` oltre i 15,67 MHz sostituendo la `divide()`
combinatoria in-chart con un **blocco `HDLMathLib/Divide` PIPELINATO** esterno (handshake), **bit-exact**
(`dmax = 0`), poi iterare probe-first sul collo successivo.

**Architecture:** La chart `IIDM_CTRL` mantiene la sua FSM a stadi (DECODE→PREP→ND→**DIV**→USE→TANH→FINAL) e
la matematica condivisa col model (`iidm_prep/nd/use/final`). Cambia **solo lo stadio DIV**: da una chiamata
`fsm_div(numl,denl)` a una coppia **ISSUE → WAIT** che dialoga col blocco esterno via `(num,den,vin)` →
`(quot,vout)`. Il feedback passa per due **Unit Delay** (`z_q`,`z_v`) che rendono esplicito il loop.

**Tech Stack:** MATLAB R2026a + Simulink/Stateflow · HDL Coder (`makehdl`, `HDLMathLib/Divide`) · Vivado
2026.1 OOC su xc7z020 @8 MHz · xsim (con **Git Bash in testa al PATH**).

**Spec:** `docs/superpowers/specs/2026-07-19-iidm-pipelined-divider-design.md`

---

## File Structure

| file | responsabilità | azione |
|---|---|---|
| `matlab/build_hdl_variants.m` | genera i blocchi di libreria: `acciidm_m_chart_code` (sorgente chart) + cablaggio del subsystem `Donatello_ACC_IIDM_M` | **Modify** (le sole 2 zone: chart stadio DIV, cablaggio blocco) |
| `matlab/run_iidm_round.m` | harness di round: build+G3/G4 → parity → B-1 (RTL fresco) → gen VHDL per OOC | **Create** |
| `matlab/hdl_iidm/RESULTS.txt` | curva `Fmax`(round) + collo + area, come `hdl_snn/RESULTS.txt` per 2d | **Create** |
| `scripts/synth_acc_iidm.tcl` | sintesi OOC (top `DUT`) — invariato, si riusa | — |

**Invarianti che NON si toccano:** `acc_iidm_fsm.m` e le funzioni-fase (`iidm_prep/nd/use/final/tanh`),
`snn_b2_fsm.m` (SNN 8-stadi, bancata a 99 MHz), `acc_iidm_open.m` (riferimento SP3).

---

## Task 1: Baseline misurato + G1 sulla config esatta

**Files:** nessuna modifica al codice — solo misure che de-riscano il resto.

- [ ] **Step 1: Misurare la latenza ATTUALE e il margine di `hold`**

Il rischio n.1 della spec: la latenza non è stata ri-misurata dopo il pipelining SNN di 2d, e gli harness
usano `hold = 500`. Va **misurata**, non assunta.

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); dmax = run_block_acciidm_m_test(12, 1, 500); fprintf('G3/G4 dmax = %g\n', dmax)"
```

Expected: stampa la **latenza misurata** (`latenza = N clock`) e `dmax = 0`.
**Se `dmax ~= 0` o la latenza è >= 500** → il `hold` è troppo stretto: ripetere con `hold = 900` e usare
**quel** valore in tutti gli step successivi (annotarlo).

- [ ] **Step 2: G1 — il blocco `Divide` è bit-identico a `divide()` NELLA config che useremo**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); P = collect_div_pairs(); fprintf('coppie: %d\n', size(P,1)); d = probe_divide_bitexact(P, 'Zero', 'Zero'); assert(d == 0, 'G1 FALLITO: dmax=%g', d)"
```

Expected: `dmax = 0` su ~300.000 coppie (in ~44 s).
*(`latMode='Zero'` = combinatorio: bit-identico al pipelinato — la pipeline sposta i bit nel TEMPO, non li
cambia — e gira in 1 passo invece di ~50. È la scorciatoia già usata e documentata da SP4.)*

- [ ] **Step 3: Prova di SENSIBILITÀ del cancello (se non discrimina, non è un cancello)**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); P = collect_div_pairs(); d = probe_divide_bitexact(P, 'Zero', 'Nearest'); assert(d > 0, 'G1 NON discrimina il rounding!'); fprintf('sensibilita OK: rnd=Nearest -> dmax=%g\n', d)"
```

Expected: `dmax > 0` — cambiando `RndMeth` il cancello **deve** divergere.

- [ ] **Step 4: Registrare il baseline e committare**

Creare `matlab/hdl_iidm/RESULTS.txt` con l'intestazione e la riga di baseline (Fmax 15,673 dal run
`r9ctrl`, collo = divisore `ql_7`):

```
# Studio IIDM - divisore pipelinato (rianimazione SP4 #1). OOC xc7z020 @8 MHz, top DUT.
# Bit-exact ad ogni round: G3/G4 (blocco==model==SP3) + parity 0/60000 (SNN) + B-1 0/3000 (RTL==blocco).
# G1 (blocco Divide == divide(), 300k coppie) provato per la config Max/Zero/fixdt(1,19,8).
#
# round | leva                                  | Fmax(MHz) | LUT  | FF   | DSP | collo
# ------|---------------------------------------|-----------|------|------|-----|---------------------------
  R0    | baseline (divide() combinatoria)      | 15.673    | 8230 | 3183 | 69  | divisore IIDM ql_7 (204 liv)
```

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/hdl_iidm/RESULTS.txt
git commit -m "test(iidm): baseline + G1 bit-identita blocco Divide (config Max/Zero/Q10.8) + sensibilita"
```

---

## Task 2: Handshake nello stadio DIV della chart

**Files:** Modify `matlab/build_hdl_variants.m` (funzione `acciidm_m_chart_code`)

- [ ] **Step 1: Firma della chart — da 4in/1out a 6in/4out**

Sostituire la riga della firma:

```matlab
    'function accel = IIDM_CTRL(s, v, dv, v_l)'
```

con:

```matlab
    'function [accel, num, den, vin] = IIDM_CTRL(s, v, dv, v_l, quot, vout)'
```

- [ ] **Step 2: Default sicuri delle uscite di handshake, ad OGNI chiamata**

Subito dopo `'  xprev = xn;'` (prima di `[raw, valid] = snn_b2_fsm(...)`), inserire:

```matlab
    '  % Handshake verso il blocco Divide: default OGNI ciclo (vin=false => il Divide non campiona).'
    '  num = cast(0, ''like'', Ta.acc); den = cast(1, ''like'', Ta.acc); vin = false;'
```

*(`den = 1` e non 0: un denominatore nullo in un ciclo idle è una divisione per zero inutile da propagare.)*

- [ ] **Step 3: Stadio DIV -> ISSUE, e nuovo stadio 8 = WAIT**

Sostituire il blocco dello stadio 4:

```matlab
    '  elseif phase == 4                    % DIV: SOLO la divisione'
    '    ql = fsm_div(numl, denl);          % <== UNICA chiamata nel sorgente: UN divisore in HDL'
    '    phase = uint8(5);'
```

con:

```matlab
    '  elseif phase == 4                    % DIV-ISSUE: emette gli operandi al blocco Divide esterno'
    '    num = numl; den = denl; vin = true;'
    '    phase = uint8(8);'
    '  elseif phase == 8                    % DIV-WAIT: il quoziente torna dopo la latenza del Divide'
    '    if vout                            % (la FSM ATTENDE: niente conteggio a mano della latenza)'
    '      % cast ''like'' Ta.acc: il segnale di ritorno ha il numerictype giusto ma NON la fimath di'
    '      % acc_types, e la fimath e'' parte del tipo (SP3 §2). Il VALORE non cambia.'
    '      ql(:) = cast(quot, ''like'', Ta.acc);'
    '      phase = uint8(5);'
    '    end'
```

Nota: `ql(:)` (subscript) e non `ql =`, per **non** cambiare il tipo di `ql` (idioma del progetto).
Gli stadi 5/6/7 restano **invariati**: `iidm_use(kdiv, ql, st)` consuma `ql` esattamente come prima.

- [ ] **Step 4: Verificare che il sorgente della chart si generi senza errori di sintassi**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); s = which('build_hdl_variants'); assert(~isempty(s)); fprintf('build_hdl_variants trovato: %s\n', s)"
```

Expected: nessun errore. *(La prova vera è Task 3, che costruisce e simula il blocco.)*

---

## Task 3: Cablaggio del subsystem (blocco Divide + Unit Delay + tipi porte)

**Files:** Modify `matlab/build_hdl_variants.m` (zona di costruzione di `Donatello_ACC_IIDM_M`)

- [ ] **Step 1: Fissare i tipi delle porte di RITORNO (gotcha #1 di SP4)**

Subito dopo l'assegnazione `chartM.Script = acciidm_m_chart_code(...)`, inserire:

```matlab
  % Tipi delle porte di RITORNO dal Divide: una chart creata da script crea i dati come DOUBLE, ma dal
  % blocco arrivano `vout` (boolean) e `quot` (fixdt) -> Simulink rifiuta con "boolean ... is driving a
  % signal of data type double". Vanno fissati esplicitamente (gli altri input ereditano). [SP4 f430aad0]
  dVout = chartM.find('-isa','Stateflow.Data','-and','Name','vout');
  if ~isempty(dVout), dVout.DataType = 'boolean'; end
  dQuot = chartM.find('-isa','Stateflow.Data','-and','Name','quot');
  if ~isempty(dQuot), dQuot.DataType = 'Inherit: Same as Simulink'; end
```

- [ ] **Step 2: Il blocco Divide + i due Unit Delay + il cablaggio**

Sostituire il cablaggio attuale (che collega solo i 4 inport e l'outport `accel`):

```matlab
  for j = 1:4
    add_block('built-in/Inport', [subM '/' in_names{j}], 'Port', num2str(j));
    add_line(subM, [in_names{j} '/1'], ['IIDM_CTRL/' num2str(j)]);
  end
  add_block('built-in/Outport', [subM '/accel'], 'Port', '1');
  add_line(subM, 'IIDM_CTRL/1', 'accel/1');
```

con:

```matlab
  % L'UNICO divisore, condiviso dalle 5 divisioni. latencyMode 'Max' = PIPELINATO: e' cio' che deve alzare
  % l'Fmax, ed e' anche cio' che ROMPE il loop algebrico del feedback (con 'Zero' sarebbe combinatorio ->
  % loop algebrico + nessun guadagno). RndMeth 'Zero' + OutDataType fixdt(1,19,8) = ESATTAMENTE la config
  % che G1 ha provato bit-identica a divide()-SP3 su 300k coppie reali. [SP4 f430aad0]
  add_block('HDLMathLib/Divide', [subM '/DIV']);
  set_param([subM '/DIV'], 'latencyMode','Max', 'RndMeth','Zero', 'OutDataTypeStr','fixdt(1,19,8)');
  for j = 1:4
    add_block('built-in/Inport', [subM '/' in_names{j}], 'Port', num2str(j));
    add_line(subM, [in_names{j} '/1'], ['IIDM_CTRL/' num2str(j)]);
  end
  % Unit Delay sul RITORNO: senza, chart -> Divide -> chart e' un LOOP ALGEBRICO. Simulink assume che gli
  % output di una MATLAB Function dipendano dagli input nello stesso passo; qui NON e' vero (num/den
  % vengono dallo STATO st/phase, non da quot/vout), ma il tool non puo' dedurlo. Il ritardo e' assorbito
  % dalla FSM, che attende comunque `vout`. [SP4 f430aad0]
  add_block('simulink/Discrete/Unit Delay', [subM '/z_q'], 'InitialCondition','0');
  add_block('simulink/Discrete/Unit Delay', [subM '/z_v'], 'InitialCondition','0');
  add_line(subM, 'DIV/1', 'z_q/1');  add_line(subM, 'z_q/1', 'IIDM_CTRL/5');   % quot -> z -> chart
  add_line(subM, 'DIV/2', 'z_v/1');  add_line(subM, 'z_v/1', 'IIDM_CTRL/6');   % vout -> z -> chart
  add_line(subM, 'IIDM_CTRL/2', 'DIV/1');     % num -> Divide
  add_line(subM, 'IIDM_CTRL/3', 'DIV/2');     % den -> Divide
  add_line(subM, 'IIDM_CTRL/4', 'DIV/3');     % vin -> Divide
  add_block('built-in/Outport', [subM '/accel'], 'Port', '1');
  add_line(subM, 'IIDM_CTRL/1', 'accel/1');
```

- [ ] **Step 3: Ricostruire e passare G3/G4 (blocco == model == SP3) + leggere la LATENZA**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); build_hdl_variants(); dmax = run_block_acciidm_m_test(12, 1, 900); fprintf('G3/G4 dmax = %g\n', dmax); assert(dmax == 0, 'G3/G4 FALLITO: dmax=%g', dmax)"
```

Expected: `costruito Donatello_ACC_IIDM_M`, la **latenza stampata** (ora maggiore: +latenza del Divide ×5
divisioni +2 per gli Unit Delay), e `dmax = 0`.
**Se fallisce:** leggere l'errore. Se è `loop algebrico` → il `latencyMode` non è `'Max'`. Se è
`boolean ... driving double` → lo Step 1 non è stato applicato. Se `dmax ~= 0` → l'handshake non attende
davvero `vout` (rivedere lo stadio 8).

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/build_hdl_variants.m
git commit -m "feat(iidm): stadio DIV via handshake verso blocco Divide PIPELINATO (Max/Zero/Q10.8)

Rianimato SP4 #1: A1 (tanh-LUT) ha rimosso il divieto dataflow che lo uccise. Chart 6in/4out
(num,den,vin -> quot,vout), Unit Delay z_q/z_v sul ritorno, tipi porte fissati. G3/G4 dmax=0."
```

---

## Task 4: Cancelli bit-exact completi (parity + B-1 + G2)

**Files:** Create `matlab/run_iidm_round.m`

- [ ] **Step 1: Creare l'harness di round**

```matlab
function run_iidm_round(tag, hold)
%RUN_IIDM_ROUND  [Studio IIDM] Fase MATLAB di un round: rebuild + cancelli bit-exact + gen VHDL per l'OOC.
%  Gate: G3/G4 (blocco==model==SP3) + parity 0/60000 (SNN invariata) + B-1 0/3000 (RTL FRESCO == blocco).
%  G2 (model==SP3 su 60k) NON e' qui: il model e le funzioni-fase non cambiano in questo studio -> si
%  esegue una volta (Task 4 Step 3), non ad ogni round.
%    run_iidm_round('r1', 900)
  if nargin < 1 || isempty(tag),  tag  = 'r1'; end
  if nargin < 2 || isempty(hold), hold = 900; end
  here = fileparts(mfilename('fullpath')); addpath(here);
  setenv('PATH', ['C:\PROGRA~1\Git\bin;' getenv('PATH')]);   % xsim: bash->WSL rotto (SP4 §Studio 2b)

  fprintf('\n==== IIDM %s: BUILD + G3/G4 ====\n', tag);
  build_hdl_variants();
  d34 = run_block_acciidm_m_test(12, 1, hold);
  assert(d34 == 0, 'G3/G4 FALLITO: dmax=%g', d34);

  fprintf('\n==== IIDM %s: parity SNN 0/60000 ====\n', tag);
  [~, nbs] = run_b2_parity_dataset('Donatello');
  assert(nbs == 0, 'parity FALLITO: %d/60000', nbs);

  fprintf('\n==== IIDM %s: B-1 (RTL FRESCO == blocco) ====\n', tag);
  rd = fullfile(here, 'hdlsrc_donatello_acc_iidm_m_v');
  if exist(rd, 'dir'), rmdir(rd, 's'); end     % forza rigenerazione: non riusare il .v stantio
  run_rtl_validate_b([1 7 23], 'reduced');

  fprintf('\n==== IIDM %s: GEN VHDL per OOC ====\n', tag);
  probe_pipe_tanh({tag, 0, 'off', 'off'});
  fprintf('\n=== IIDM %s: fase MATLAB OK -> matlab/hdl_pipe/%s (ora sintesi OOC) ===\n', tag, tag);
end
```

- [ ] **Step 2: Eseguire l'harness**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); run_iidm_round('r1', 900)"
```

Expected: `G3/G4 dmax = 0`, `parity: 0/60 traiettorie e 0/60000 control-step`, `B-1 ... 0 / 3000`,
`VHDL OK (4 file)`.

- [ ] **Step 3: G2 una tantum (il model non cambia, ma va confermato che il baseline regge)**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); d = run_acciidm_m_dataset(); fprintf('G2 dmax = %g\n', d); assert(d == 0, 'G2 FALLITO: dmax=%g', d)"
```

Expected: `dmax = 0` su 60.000 control-step (~12 min).

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/run_iidm_round.m
git commit -m "test(iidm): harness di round (G3/G4 + parity + B-1) + G2 una tantum verde"
```

---

## Task 5: Sintesi OOC — il risultato di Round 1

**Files:** Modify `matlab/hdl_iidm/RESULTS.txt`

- [ ] **Step 1: Copiare il VHDL in un path SENZA SPAZI e sintetizzare**

Il `glob` Tcl non sopravvive agli spazi nel path (`1.Reti Neurali`): si copia in `D:/zbd_pipe`.

```bash
WT="D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
rm -rf /d/zbd_pipe/iidm_r1
cp -r "$WT/matlab/hdl_pipe/r1" /d/zbd_pipe/iidm_r1
cp "$WT/scripts/synth_acc_iidm.tcl" /d/zbd_pipe/synth_acc_iidm.tcl
cd /d/zbd_pipe
"/c/AMDDesignTools/2026.1/Vivado/bin/vivado" -mode batch -source /d/zbd_pipe/synth_acc_iidm.tcl \
  -tclargs /d/zbd_pipe/iidm_r1 /d/zbd_pipe/iidm_r1/synth iidm_r1 2>&1 | grep -E "^RESULT|^CRITPATH"
```

Expected: due righe `RESULT iidm_r1 LUT=… FF=… DSP=… BRAM=… WNS=… Fmax=…` e
`CRITPATH iidm_r1 from=… to=… logic_levels=… delay=…`.

- [ ] **Step 2: Registrare il round in `matlab/hdl_iidm/RESULTS.txt`**

Aggiungere una riga nella tabella (leva = `divisore PIPELINATO (blocco, Max)`) coi valori misurati, più
sotto i record grezzi `RESULT`/`CRITPATH`. **Registrare anche l'AREA**: la spec segnala che la variante
config-based di SP4 fece esplodere l'area (LUT ×2,36, FF ×13,9) — qui va misurata, non assunta.

- [ ] **Step 3: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/hdl_iidm/RESULTS.txt
git commit -m "perf(iidm): Round 1 - divisore pipelinato, Fmax <misurata> (era 15.673), area misurata"
```

---

## Task 6: Round iterativi (template probe-first)

**Files:** dipende dal collo — si sceglie **sui dati**, non a tavolino.

Ripetere finché converge. In 2d il collo è saltato **due volte** dove non era previsto: si **rilegge sempre**
il `critpath.rpt`, non si deduce.

- [ ] **Step 1: Leggere il collo del round precedente**

```bash
sed -n '1,40p' /d/zbd_pipe/iidm_r1/synth/critpath.rpt
```

Identificare l'endpoint e la struttura dominante (celle `CARRY4`/`DSP48`/`LUT`).

- [ ] **Step 2: Scegliere la leva che calza**

| collo osservato | leva |
|---|---|
| ancora il divisore (`ql_*`) | aumentare la latenza del blocco (`Custom`/`Custom(PerIteration)`) e ri-misurare |
| `st_sab` (s_star / `sqrt(a·b)`) | sqrt sequenziale digit-recurrence, oppure **CORDIC iperbolico** (shift-add, ~1 bit/iterazione), oppure staging FSM come in 2d |
| catena di add/sub larghi | split in stadi FSM (identico a 2d R3/R8) |
| moltiplicatore non registrato | registrare il prodotto (stadio MAC, identico a 2d R6) |

- [ ] **Step 3: Applicare, ri-gattare, ri-sintetizzare**

Stessi comandi di Task 4 Step 2 e Task 5 Step 1 con `tag = 'r2'`, `'r3'`, … Registrare ogni round.

- [ ] **Step 4: Criterio di STOP (convergenza)** — fermarsi quando **una** vale:
  - il collo è un'**operazione singola non spezzabile** bit-exact;
  - un round rende **< ~5%** di `Fmax`;
  - l'area sfora il budget di xc7z020 (53k LUT / 106k FF) o cresce in modo sproporzionato al guadagno.

- [ ] **Step 5: Commit di ogni round**

```bash
git add matlab/build_hdl_variants.m matlab/hdl_iidm/RESULTS.txt
git commit -m "perf(iidm): Round N - <leva>, Fmax <prima>-><dopo> (bit-exact: G3/G4 + parity + B-1)"
```

---

## Task 7: Chiusura — curva, verdetto, documentazione

**Files:** Modify `document/SP4_ACC_IIDM_FAST.md`, `document/SESSION_RESUME.md`, memoria

- [ ] **Step 1: Gate esaustivo finale** — sul round vincente: `run_iidm_round(tagFinale, hold)` +
      `run_acciidm_m_dataset()` (G2) + `run_rtl_validate_b([1 7 23], 'full')`. Tutti verdi.

- [ ] **Step 2: Scrivere §Studio IIDM in `document/SP4_ACC_IIDM_FAST.md`** — la curva `Fmax`(round), la
      leva di ogni round, il collo residuo, l'area, la latenza finale, e il **perché** ci si è fermati.

- [ ] **Step 3: Aggiornare `document/SESSION_RESUME.md`** (box di stato in cima) e la memoria di progetto.

- [ ] **Step 4: Commit finale**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add document/SP4_ACC_IIDM_FAST.md document/SESSION_RESUME.md matlab/hdl_iidm/RESULTS.txt
git commit -m "docs(iidm): studio CHIUSO - curva Fmax(round), verdetto, collo residuo"
```

---

## Note di rischio (dalla spec, da tenere sott'occhio)

1. **Latenza / `hold`** — misurata a Task 1 Step 1 e ri-letta ad ogni G3/G4. Il divisore pipelinato ne
   aggiunge (×5 divisioni) + 2 cicli di Unit Delay. Se `run_block_acciidm_m_test` fallisce, il primo
   sospettato è un `hold` troppo stretto, **non** la matematica.
2. **Area** — SP4 config-based esplose (FF ×13,9). Si **misura** ad ogni round (Task 5 Step 2).
3. **Dataflow §9** — `tanh` risolto (LUT) e `persistent` SNN provati innocui dal probe; altri vincoli
   (struct empty-typed, `persistent` in non-entry-point) possono emergere ristrutturando la FSM.
4. **Il collo può NON spostarsi dove atteso** — rileggere sempre `critpath.rpt`.
