# SNN Champions — Plan 2: Libreria Simulink + parità di blocco + gate HDL

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development o superpowers:executing-plans. Steps con checkbox `- [ ]`.

**Goal:** Generare la libreria Simulink `snn_champions_lib.slx` con i 4 blocchi champion plug&play, provarne la **parità a livello di blocco** vs golden, e verificare la **HDL-readiness** del core (`coder.screener`+`checkhdl`).

**Architecture:** Un generatore MATLAB (`build_library.m`) emette, per champion, una funzione dati `<name>_weights.m` (costanti bakate) e un blocco = Subsystem contenente un MATLAB Function block che chiama `snn_entry('double', x, <name>_weights())` — riusa il core `snn_entry`/`snn_core` già provato in Plan 1 (DRY). La parità di blocco gira i blocchi in un modello di test vs il golden. Il gate HDL screena `snn_core` (datapath shift-add sintetizzabile); il decode (sigmoid) è **escluso** perché stadio isolato (LUT/CORDIC/PS nel build HDL).

**Tech Stack:** MATLAB R2026a (Simulink + HDL Coder + Fixed-Point Designer, licenza accademica completa). Dipende da Plan 1 (`snn_*.m`, `champions_export.mat`). Worktree `.worktrees/Simulink_Importer`.

**Precondizione:** Plan 1 completo e verde (`matlab/snn_entry.m`, `snn_core.m`, `snn_normalize.m`, `snn_decode.m`, `snn_types.m`, `champions_export.mat`). Test MATLAB: `matlab -batch "cd('matlab'); <script>"`.

---

## Task 1: Spike — verifica i meccanismi MATLAB/Simulink (chart.Script + blocco-libreria in un modello)

Risolve i due unknown segnalati nello spec (§5.2): formato di `chart.Script` in R2026a e come far girare un blocco di libreria in un modello di test. **File temporaneo, non committato.**

**Files:**
- Create (temp): `matlab/spike_mechanics.m`

- [ ] **Step 1: Write the spike**

```matlab
function spike_mechanics()
  lib = 'spike_lib'; mdl = 'spike_tb';
  for b = {lib, mdl}, if bdIsLoaded(b{1}), close_system(b{1},0); end, end
  if isfile([lib '.slx']), delete([lib '.slx']); end

  % (1) libreria + Subsystem + MATLAB Function block, codice via chart.Script
  new_system(lib, 'Library');
  add_block('built-in/Subsystem', [lib '/Blk']);
  add_block('simulink/User-Defined Functions/MATLAB Function', [lib '/Blk/MF']);
  add_block('built-in/Inport',  [lib '/Blk/In1']);
  add_block('built-in/Outport', [lib '/Blk/Out1']);
  add_line([lib '/Blk'], 'In1/1', 'MF/1'); add_line([lib '/Blk'], 'MF/1', 'Out1/1');
  code = sprintf('function y = MF(u)\n%%#codegen\ny = u*2 + 3;\nend\n');
  chart = sfroot().find('-isa','Stateflow.EMChart','Path',[lib '/Blk/MF']);
  chart.Script = code;
  set_param(lib, 'EnableLBRepository','on'); save_system(lib);

  % (2) round-trip di chart.Script
  close_system(lib,0); load_system(lib);
  chart2 = sfroot().find('-isa','Stateflow.EMChart','Path',[lib '/Blk/MF']);
  fprintf('ROUNDTRIP_STARTS_WITH_FUNCTION=%d\n', startsWith(strtrim(chart2.Script),'function'));

  % (3) esecuzione del blocco-libreria in un modello (atteso 5*2+3=13)
  new_system(mdl);
  add_block([lib '/Blk'], [mdl '/DUT']);
  add_block('simulink/Sources/Constant', [mdl '/C'], 'Value','5');
  add_block('simulink/Sinks/To Workspace', [mdl '/Y'], 'VariableName','yout','SaveFormat','Array');
  add_line(mdl,'C/1','DUT/1'); add_line(mdl,'DUT/1','Y/1');
  set_param(mdl,'StopTime','0'); out = sim(mdl);
  y = out.yout; fprintf('DUT_OUTPUT=%g (atteso 13)\n', y(end));
  close_system(mdl,0); close_system(lib,0); if isfile([lib '.slx']), delete([lib '.slx']); end
  disp('SPIKE_OK');
end
```

- [ ] **Step 2: Run**

Run: `matlab -batch "cd('matlab'); spike_mechanics"`
Expected: `ROUNDTRIP_STARTS_WITH_FUNCTION=1`, `DUT_OUTPUT=13`, `SPIKE_OK`, exit 0.

- [ ] **Step 3: Registra gli esiti e adegua Task 2 se serve**

Annota: (a) `chart.Script` va assegnato con o senza la riga `function` (il round-trip lo dice); (b) i nomi porta di `add_line` corretti; (c) come si legge l'output del blocco. Se un'API differisce, aggiornare Task 2/3 di conseguenza **prima** di procedere.

- [ ] **Step 4: Rimuovi lo spike (non si committa)**

```bash
rm -f matlab/spike_mechanics.m matlab/spike_lib.slx
```

---

## Task 2: `build_library.m` — generatore (4 weight-data + `snn_champions_lib.slx`)

**Files:**
- Create: `matlab/build_library.m`

Genera, da `champions_export.mat`: per champion una funzione dati `<name>_weights.m` (struct `W` con costanti bakate) e un blocco = Subsystem con un MATLAB Function che chiama `snn_entry`. Self-contained per i pesi (bakati); riusa `snn_*.m` (spedite con la libreria).

- [ ] **Step 1: Write the generator**

```matlab
function build_library()
%BUILD_LIBRARY  Genera snn_champions_lib.slx (4 blocchi) + <name>_weights.m dai champion.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  lib = 'snn_champions_lib';
  if bdIsLoaded(lib), close_system(lib,0); end
  if isfile(fullfile(here,[lib '.slx'])), delete(fullfile(here,[lib '.slx'])); end
  new_system(lib,'Library'); 

  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name));
    write_weights_fn(fullfile(here,[name '_weights.m']), name, c);   % <name>_weights.m
    sub = [lib '/' name];
    add_block('built-in/Subsystem', sub);
    add_block('built-in/Inport',  [sub '/x_phys']);
    add_block('built-in/Outport', [sub '/params']);
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    add_line(sub,'x_phys/1','SNN/1'); add_line(sub,'SNN/1','params/1');
    code = sprintf(['function params = SNN(x_phys)\n%%#codegen\n' ...
                    'params = snn_entry(''double'', x_phys(:), %s_weights());\n' ...
                    'end\n'], name);
    chart = sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/SNN']);
    chart.Script = code;
  end
  set_param(lib,'EnableLBRepository','on'); save_system(lib, fullfile(here,[lib '.slx']));
  close_system(lib,0);
  fprintf('Built %s.slx with %d blocks\n', lib, numel(champs));
end

function write_weights_fn(path, name, c)
  fid = fopen(path,'w'); assert(fid>0, 'cannot open %s', path);
  fprintf(fid,'function W = %s_weights()\n%%#codegen\n', name);
  flds = {'hidden','rank','n_ticks','max_delay','fc_weight','rec_U','rec_V','readout', ...
          'delays','base_threshold','thresh_jump','leak_div','param_lo','param_hi', ...
          'decode_offset','logit_tau','norm'};
  for k = 1:numel(flds)
    f = flds{k};
    fprintf(fid,'  W.%s = %s;\n', f, mat2str(double(c.(f)), 17));
  end
  fprintf(fid,'end\n'); fclose(fid);
end
```

- [ ] **Step 2: Run the generator**

Run: `matlab -batch "cd('matlab'); build_library"`
Expected: `Built snn_champions_lib.slx with 4 blocks`, e i file `Donatello_weights.m` … `Leonardo_weights.m` creati.

- [ ] **Step 3: Commit**

```bash
git add matlab/build_library.m matlab/snn_champions_lib.slx matlab/Donatello_weights.m matlab/Michelangelo_weights.m matlab/Raffaello_weights.m matlab/Leonardo_weights.m
git commit -m "feat(fase2): build_library genera snn_champions_lib.slx (4 blocchi + pesi bakati)"
```

---

## Task 3: `run_block_parity.m` — parità a livello di blocco Simulink

**Files:**
- Create: `matlab/run_block_parity.m`

Per ogni blocco: costruisce un modello di test, guida il blocco con `x_phys` del golden (come sequenza, stato persistente), raccoglie l'output e confronta con `y_params`. Tol 1e-4 (stessa del core; il blocco chiama lo stesso `snn_entry`).

- [ ] **Step 1: Write the harness**

```matlab
function run_block_parity()
%RUN_BLOCK_PARITY  Parita' dei blocchi di snn_champions_lib vs golden (sequenza).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  lib = 'snn_champions_lib'; load_system(fullfile(here,[lib '.slx']));
  tol = 1e-4; failed = false;

  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name)); N = size(c.x_phys,1);
    mdl = ['tb_' name]; if bdIsLoaded(mdl), close_system(mdl,0); end
    new_system(mdl);
    add_block([lib '/' name], [mdl '/DUT']);
    add_block('simulink/Sources/In1', [mdl '/In']);       % root inport
    add_block('simulink/Sinks/Out1',  [mdl '/Out']);
    add_line(mdl,'In/1','DUT/1'); add_line(mdl,'DUT/1','Out/1');
    % input come sequenza (N passi, dt=1), stato del blocco persiste
    ds = Simulink.SimulationData.Dataset;
    ts = timeseries(c.x_phys, (0:N-1).');                 % (N x 4)
    in = Simulink.SimulationInput(mdl);
    in = in.setExternalInput(ts);
    in = in.setModelParameter('StopTime', num2str(N-1), 'LoadExternalInput','on', ...
                              'SaveOutput','on','OutputSaveName','yo','SaveFormat','Array');
    out = sim(in);
    y = squeeze(out.yo);                                   % (N x 5)
    ey = max(abs(y(:) - c.y_params(:)));
    fprintf('%-13s  block|err|=%.2e [%s]\n', name, ey, tern(ey<tol));
    failed = failed || ey>=tol; close_system(mdl,0);
  end
  close_system(lib,0);
  if failed, error('run_block_parity:FAIL','Parita'' di blocco fallita'); end
  disp('ALL BLOCK PARITY PASS');
end
function s = tern(b), if b, s='PASS'; else, s='FAIL'; end, end
```

> **Nota:** la meccanica esatta di input-sequenza a un blocco (root Inport + `setExternalInput` vs From Workspace) va allineata all'esito dello **spike (Task 1)**. Se `setExternalInput` con timeseries non guida il blocco come atteso, usare un blocco **From Workspace** dentro il modello di test che itera `x_phys`. Il criterio invariante: alimentare i N passi in sequenza, stato del blocco persistente, confronto vs `y_params`.

- [ ] **Step 2: Run to verify**

Run: `matlab -batch "cd('matlab'); run_block_parity"`
Expected: `ALL BLOCK PARITY PASS`. Se FAIL, il blocco chiama lo stesso `snn_entry` del core (già a parità 1e-6) → la causa è quasi certamente il **cablaggio del modello di test / semantica input-sequenza**, non la matematica: iterare qui (vedi nota), non su `snn_core`.

- [ ] **Step 3: Commit**

```bash
git add matlab/run_block_parity.m
git commit -m "test(fase2): parita' a livello di blocco Simulink vs golden (4 champion)"
```

---

## Task 4: `check_hdl.m` — gate HDL-readiness (screener + checkhdl sul core)

**Files:**
- Create: `matlab/check_hdl.m`

Verifica che il **core datapath** (`snn_core`, shift-add) sia HDL-generabile, PRIMA di generare RTL (build successivo). Il decode (sigmoid) è **escluso** (stadio isolato → LUT/CORDIC/PS in fase HDL). `coder.screener` sull'entry-point del core; `checkhdl` sul subsystem di un blocco.

- [ ] **Step 1: Write the gate**

```matlab
function check_hdl()
%CHECK_HDL  Gate HDL-readiness: coder.screener sul core + checkhdl sul subsystem.
%  Il decode (sigmoid) e' escluso: stadio isolato (LUT/CORDIC/PS nel build HDL).
  here = fileparts(mfilename('fullpath'));
  ok = true;

  % (1) screener sul datapath del core (snn_core). Serve un wrapper a firma fissa.
  %     Genera un entry di prova con tipi/size concreti di un champion baseline.
  d = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  info = coder.screener('snn_core');   % analizza costrutti non supportati
  fprintf('coder.screener(snn_core): %d issue\n', numel(info.Messages));
  ok = ok && isempty(info.Messages);

  % (2) checkhdl sul subsystem di un blocco (Raffaello, baseline).
  lib = 'snn_champions_lib'; load_system(fullfile(here,[lib '.slx']));
  try
    checkhdl([lib '/Raffaello']);      % genera hdlsrc/*_report.html; error su Errors
    fprintf('checkhdl(Raffaello): OK\n');
  catch e
    fprintf('checkhdl(Raffaello): %s\n', e.message); ok = false;
  end
  close_system(lib,0);

  if ~ok, error('check_hdl:FAIL','HDL-readiness gate fallito (vedi messaggi/hdlsrc report)'); end
  disp('HDL READINESS OK');
end
```

- [ ] **Step 2: Run**

Run: `matlab -batch "cd('matlab'); check_hdl"`
Expected (obiettivo): `HDL READINESS OK`. **Realistico:** `coder.screener` e/o `checkhdl` segnaleranno issue da correggere in `snn_core` (es. `sum(..,2)` su size dinamiche, indicizzazione non statica, o il decode se non escluso). Iterare su `snn_core` per rispettare il subset HDL **mantenendo la parità** (rieseguire `run_parity_tests` dopo ogni modifica) finché il gate è verde. Se un costrutto è intrinsecamente non-HDL ma necessario in simulazione, isolarlo dietro un flag `coder.target` (behavioral vs HDL) — documentarlo.

- [ ] **Step 3: Commit**

```bash
git add matlab/check_hdl.m matlab/snn_core.m
git commit -m "feat(fase2): gate HDL-readiness (coder.screener + checkhdl sul core)"
```

---

## Self-review (fatta)

- **Spec coverage (§5.2 libreria, §6 parità blocco, §7 gate checkhdl):** build_library→.slx+4 blocchi (Task 2 ✓); parità di blocco (Task 3 ✓); gate coder.screener+checkhdl sul core, decode escluso (Task 4 ✓); meccanismi Simulink verificati prima (Task 1 spike ✓). Fuori Plan 2 (→ build HDL): fi/fxpopt, makehdl RTL, cordicsigmoid/LUT, cosim HDL Verifier, PYNQ-Z1 custom-board, ri-profilazione Qm.n eventprop.
- **Placeholder scan:** nessun TBD; codice reale in ogni step. Le note "allinea allo spike" / "itera sul core" sono guardrail di debug espliciti, non placeholder.
- **Type consistency:** i blocchi chiamano `snn_entry('double', x, <name>_weights())`; `<name>_weights()` ritorna la struct `W` coi campi usati da `snn_entry`/`snn_core` (identici a `to_weights` di Plan 1); `run_block_parity` confronta vs `y_params` come `run_parity_tests`.

## Execution handoff

Esecuzione **inline** (come Plan 1), task-by-task con checkpoint. Task 1 (spike) de-risca i meccanismi prima di generare i 4 blocchi.
