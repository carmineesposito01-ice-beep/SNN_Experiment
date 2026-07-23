# Blocchi tier Donatello (SLOW/BALANCED/FAST) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere a `snn_champions_lib.slx` tre blocchi `Donatello_SLOW/BALANCED/FAST` — plug&play, HDL-ready, simulabili come gli altri blocchi — riproducendo fedelmente le configurazioni misurate nello Studio Trade-off.

**Architecture:** I tre tier sono lo stesso blocco Donatello montato in `splitpipe` (due MATLAB Function SNN+DEC, registro operandi) con tre accoppiamenti (SNN snapshot R2/R5/R9 × decode fused/p3/p5), sigmoide LUT-64. Una nuova `build_tier_blocks.m` li aggiunge riusando i mattoni di montaggio di `build_hdl_variants.m`, estratti in file condivisi (single-source). Quattro cancelli (G1–G4) ne provano self-containment, correttezza, firma e coerenza col VHDL già misurato. Tutta la Fase 1 è MATLAB-only (nessuna sintesi Vivado).

**Tech Stack:** MATLAB R2026a (`matlab.exe -batch`), Simulink, HDL Coder (`makehdl`), Git Bash (grep/diff/tar/sha256sum). Spec: `docs/superpowers/specs/2026-07-23-donatello-tier-blocks-design.md`.

**Convenzioni d'esecuzione:**
- MATLAB: `MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"`; lanciare da `matlab/` con
  `"$MATLAB" -batch "addpath(pwd); <comando>"`.
- Scratch di lavoro su path **senza spazi**: `D:/zbd_tiers`.
- Commit **conventional, senza `Co-Authored-By`**. Working tree: solo file di questo lavoro.
- Un `.vhd` HDL Coder ha header con timestamp: ogni confronto VHDL è **logico** — si strippano le righe di
  commento con `grep -v '^\s*--'` e le righe vuote prima del `diff`.

---

## Task 0: Baseline per il non-regression del refactor + smoke ambiente

**Files:**
- Create (scratch, non versionato): `D:/zbd_tiers/baseline/champion/`, `D:/zbd_tiers/baseline/acciidm_m/`

- [ ] **Step 1: Smoke test ambiente MATLAB + libreria**

Run:
```bash
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); lib='snn_champions_lib'; load_system(lib); disp(sort(find_system(lib,'SearchDepth',1,'BlockType','SubSystem'))); close_system(lib,0)"
```
Expected: elenca i blocchi correnti — `Donatello`, `Donatello_ACC_IIDM`, `Donatello_ACC_IIDM_M`, `Donatello_Champion`, `Donatello_LUT16..512`, `Leonardo`, `Michelangelo`, `Raffaello`. **Nessun** `Donatello_SLOW/BALANCED/FAST`.

- [ ] **Step 2: Cattura il VHDL baseline di due blocchi rappresentativi**

`Donatello_Champion` esercita il path **split** (SNN+DEC); `Donatello_ACC_IIDM_M` esercita il path **acciidm**. Insieme coprono i chiamanti delle funzioni che il Task 1 estrarrà.

Run:
```bash
"$MATLAB" -batch "addpath(pwd); rtl_gen_dut('Donatello_Champion','D:/zbd_tiers/baseline/champion'); rtl_gen_dut('Donatello_ACC_IIDM_M','D:/zbd_tiers/baseline/acciidm_m','Verilog')"
```
Expected: per Champion `=== VHDL generato: Donatello_Champion -> … ===` con `DualPortRAM_generic.vhd` presente; per ACC_IIDM_M `=== Verilog generato: … ===`. Nessun errore.

*(Nessun commit: Task 0 produce solo baseline scratch. Il confronto avviene al Task 1 Step 3, che rigenera e
diffa direttamente `baseline/` vs `after/`.)*

---

## Task 1: Refactor — estrai i mattoni di montaggio in file condivisi

**Files:**
- Create: `matlab/mount_split.m`, `matlab/snn_chart_code.m`, `matlab/dec_chart_code.m`, `matlab/decode_phase_code.m`, `matlab/normalize_code.m`, `matlab/inlined_header.m`
- Modify: `matlab/build_hdl_variants.m` (rimuove le stesse funzioni locali; ora le chiama esterne)

Motivo: `build_tier_blocks` (Task 2) deve montare un blocco splitpipe con **la stessa identica logica** di `build_hdl_variants`. Le funzioni vivono in un solo posto (DRY, no copie sincronizzate a mano — regola di progetto).

- [ ] **Step 1: Individua quali funzioni sono davvero locali, poi spostale**

Prima verifica lo stato di partenza (alcune potrebbero già essere file esterni):
```bash
"$MATLAB" -batch "addpath(pwd); for f={'mount_split','snn_chart_code','dec_chart_code','decode_phase_code','normalize_code','inlined_header'}, w=which(f{1}); fprintf('%-20s %s\n', f{1}, w); end"
```
Per ciascuna funzione dell'elenco che risulta **locale a `build_hdl_variants.m`** (la riga `which` mostra
`build_hdl_variants.m` o `is a local function`): taglia il corpo `function … end` e incollalo in
`matlab/<nome>.m` con lo **stesso nome**, byte per byte (nessuna modifica alla logica); rimuovi la definizione
locale da `build_hdl_variants.m`. Le funzioni già esterne si lasciano dove sono. MATLAB risolve le chiamate
verso i nuovi file sul path; le dipendenze interne (es. `snn_chart_code`→`normalize_code`/`inlined_header`,
`dec_chart_code`→`decode_phase_code`/`inlined_header`) continuano a risolversi senza modifiche.

*Nota:* se una funzione da estrarre chiama micro-helper locali usati **solo** da lei (es. la parte finale di
`normalize_code`), spostali insieme come funzioni locali del nuovo file. Il cancello dello Step 3 è il giudice:
se il VHDL resta identico, l'estrazione è corretta.

- [ ] **Step 2: Rigenera il VHDL dei due blocchi baseline dopo il refactor**

Run:
```bash
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); rtl_gen_dut('Donatello_Champion','D:/zbd_tiers/after/champion'); rtl_gen_dut('Donatello_ACC_IIDM_M','D:/zbd_tiers/after/acciidm_m','Verilog')"
```
Expected: generazione OK per entrambi, come al Task 0 Step 2.

- [ ] **Step 3: Cancello non-regression — VHDL logicamente IDENTICO prima/dopo**

Run:
```bash
cd "D:/zbd_tiers"
fail=0
for d in champion acciidm_m; do
  for f in $(find "after/$d" -name '*.vhd' -o -name '*.v' | sort); do
    b="baseline/$d/$(basename "$f")"
    [ -f "$b" ] || { echo "MANCA baseline $(basename "$f")"; fail=1; continue; }
    if diff -q <(grep -v '^\s*--' "$b" | grep -v '^\s*$') <(grep -v '^\s*--' "$f" | grep -v '^\s*$') >/dev/null; then
      echo "OK   $d/$(basename "$f")"
    else
      echo "DIVERSO $d/$(basename "$f")"; fail=1
    fi
  done
done
[ "$fail" = 0 ] && echo "=== NON-REGRESSION PASSATO: refactor bit-identico sul VHDL ===" || { echo "=== FALLITO: il refactor ha cambiato il VHDL ==="; exit 1; }
```
Expected: tutte `OK` e `=== NON-REGRESSION PASSATO ===`. Se `DIVERSO`, il refactor ha alterato la logica → correggere prima di procedere.

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/mount_split.m matlab/snn_chart_code.m matlab/dec_chart_code.m matlab/decode_phase_code.m matlab/normalize_code.m matlab/inlined_header.m matlab/build_hdl_variants.m
git commit -m "refactor(hdl): estrai i mattoni di montaggio Donatello in file condivisi (single-source)"
```

---

## Task 2: `build_tier_blocks.m` — aggiungi i tre blocchi tier

**Files:**
- Create: `matlab/build_tier_blocks.m`
- Modify: `matlab/snn_champions_lib.slx` (aggiunge i 3 blocchi; base intatti)

- [ ] **Step 1: Scrivi `build_tier_blocks.m`**

```matlab
function build_tier_blocks()
%BUILD_TIER_BLOCKS  Aggiunge a snn_champions_lib.slx i 3 blocchi tier Donatello dello Studio Trade-off:
%  Donatello_SLOW (R2·fused), Donatello_BALANCED (R5·p3), Donatello_FAST (R9·p5), tutti in architettura
%  SPLITPIPE (registro operandi del normalize), decode-sigmoide LUT-64. Riusa i mattoni condivisi
%  (mount_split, snn_chart_code(pipe=true), dec_chart_code) — stessa logica di build_hdl_variants.
%  NON tocca gli altri blocchi. Self-contained: i sorgenti sono inlinati a build-time.
%  Gate d'accettazione: run_block_hdl_gate (G1), run_block_traj_test (G2), + firma/coerenza VHDL (G3/G4).
  here = fileparts(mfilename('fullpath'));
  cd(here);
  gen_b2_rom('Donatello');                       % ROM attiva = Donatello -> b2_rom_active.m

  % --- sorgenti VERI inlinati (single-source, letti a build-time) ---
  srcRom   = fileread(fullfile(here, 'b2_rom_active.m'));
  srcTypes = fileread(fullfile(here, 'snn_types.m'));
  % composizione decode: la chart chiama le meta' in fasi distinte -> inlinarle tutte (come build_hdl_variants)
  srcLut   = [fileread(fullfile(here, 'snn_decode_lut.m')) newline newline ...
              fileread(fullfile(here, 'decode_a.m'))  newline newline ...
              fileread(fullfile(here, 'decode_a1.m')) newline newline ...
              fileread(fullfile(here, 'decode_a2.m')) newline newline ...
              fileread(fullfile(here, 'decode_b.m'))  newline newline ...
              fileread(fullfile(here, 'decode_b1.m')) newline newline ...
              fileread(fullfile(here, 'decode_b2.m')) newline newline ...
              fileread(fullfile(here, 'decode_c.m'))  newline newline ...
              fileread(fullfile(here, 'decode_c1.m')) newline newline ...
              fileread(fullfile(here, 'decode_c2.m'))];

  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  nrm = double(c.norm(:));                        % [S V DV VL]

  %       nome                 snapshot SNN                     decode
  tiers = {'Donatello_SLOW',     'snn_variants/snn_b2_fsm_R2.m', 'fused'
           'Donatello_BALANCED', 'snn_variants/snn_b2_fsm_R5.m', 'p3'
           'Donatello_FAST',     'snn_variants/snn_b2_fsm_R9.m', 'p5'};
  NCHAMP = 64;                                     % sigmoide LUT-64 (come il deployato)

  lib = 'snn_champions_lib'; libfile = fullfile(here, [lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(libfile); set_param(lib, 'Lock', 'off');

  in_names  = {'s', 'v', 'dv', 'v_l'};
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for i = 1:size(tiers,1)
    name = tiers{i,1};
    snnPath = fullfile(here, tiers{i,2});
    assert(isfile(snnPath), 'snapshot SNN inesistente: %s', snnPath);
    srcFsm = fileread(snnPath);
    dec    = tiers{i,3};
    sub = [lib '/' name];
    if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
    add_block('built-in/Subsystem', sub, 'Position', [40, 300 + (i-1)*80, 230, 340 + (i-1)*80], ...
              'Description', tier_description(name, dec));
    % SPLITPIPE: snn_chart_code(...,true) = registro operandi ; dec_chart_code = macchina a fasi del decode
    mount_split(sub, in_names, out_names, ...
      snn_chart_code(srcRom, srcTypes, srcFsm, nrm, true), ...
      dec_chart_code(srcLut, dec, NCHAMP, 'shared'));
    fprintf('  costruito %s [splitpipe, decode=%s]\n', name, dec);
  end

  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, libfile);
  close_system(lib, 0);
  fprintf('OK: 3 blocchi tier SELF-CONTAINED HDL-ready (splitpipe) aggiunti a %s.slx\n', lib);
end

function d = tier_description(name, dec)
  cfg = struct('Donatello_SLOW','R2 (SNN 2 stadi) + decode fused  -> tier AREA MINIMA (~30 MHz io-timed)', ...
               'Donatello_BALANCED','R5 (SNN 5 stadi) + decode p3  -> tier COMPROMESSO (~58 MHz io-timed)', ...
               'Donatello_FAST','R9 (SNN 9 stadi) + decode p5      -> tier MARGINE MASSIMO (~74 MHz io-timed)');
  L = {
    sprintf('%s - SNN car-following (champion Donatello), architettura SPLITPIPE (SNN+decode come due', name)
    'entita'' di sintesi, con registro sugli operandi del normalize). Tier dello Studio Trade-off (Blocco A).'
    ''
    sprintf('CONFIGURAZIONE: %s', cfg.(name))
    'Decode della sigmoide via LUT a 64 punti. I tre tier danno gli STESSI 5 parametri (bit-exact fra loro),'
    'differiscono per latenza (342/364/406 clock) e profilo di risorse/Fmax.'
    ''
    'INGRESSI (fisici, fixed >=20 bit frazionari): s [m], v [m/s], dv [m/s] (sat +-20), v_l [m/s].'
    'USCITE (parametri IDM): v0, T, s0, a, b.  1 campione = 1 inferenza (edge-triggered), niente start/done.'
    ''
    'SELF-CONTAINED: nessun .m esterno; HDL Coder genera il VHDL dal solo blocco (time-mux, DualPortRAM).'
    'VERIFICHE: run_block_hdl_gate (self-contained) · run_block_traj_test (dmax=0).'
    'Rigenerazione: build_tier_blocks.m (NON modificare la chart a mano).'
  };
  d = strjoin(L, newline);
end
```

- [ ] **Step 2: Esegui il build**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); build_tier_blocks"
```
Expected: `costruito Donatello_SLOW [splitpipe, decode=fused]`, `…BALANCED…p3`, `…FAST…p5`, poi `OK: 3 blocchi tier …`.

- [ ] **Step 3: Cancello — i 3 tier presenti, i base invariati**

Run:
```bash
"$MATLAB" -batch "addpath(pwd); lib='snn_champions_lib'; load_system(lib); b=find_system(lib,'SearchDepth',1,'BlockType','SubSystem'); n=@(x)any(strcmp(b,[lib '/' x])); assert(n('Donatello_SLOW')&&n('Donatello_BALANCED')&&n('Donatello_FAST'),'tier mancante'); assert(n('Donatello_Champion')&&n('Donatello_LUT64'),'base sparito'); fprintf('OK: 12 blocchi, i 3 tier presenti, base intatti (%d totali)\n', numel(b)); close_system(lib,0)"
```
Expected: `OK: … i 3 tier presenti, base intatti`.

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/build_tier_blocks.m matlab/snn_champions_lib.slx
git commit -m "feat(hdl): 3 blocchi tier Donatello (SLOW/BALANCED/FAST) splitpipe in libreria"
```

---

## Task 3: G2 — simulabili e corretti (`dmax = 0`) + controllo negativo

**Files:** nessuno nuovo — riusa `run_block_traj_test.m` (accetta `blockName`; per i tier Ndec=64 di default).

- [ ] **Step 1: Cancello positivo — dmax=0 sui 3 tier, dataset**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); for t={'Donatello_SLOW','Donatello_BALANCED','Donatello_FAST'}, for tr=1:5, run_block_traj_test(20, t{1}, 500, tr); end, end; disp('=== G2 POSITIVO OK: 3 tier x 5 traj, dmax=0 ===')"
```
Expected: per ogni tier/traiettoria `dmax vs riferimento = 0` e `TRAJ TEST PASSATO`, poi `=== G2 POSITIVO OK ===`. (L'assert interno `dmax==0` ferma tutto se un tier diverge.)

- [ ] **Step 2: Cancello NEGATIVO — con ingresso a 10 bit frazionari deve FALLIRE**

Prova che il gate discrimina (ingresso degradato → dmax>0 → l'assert scatta).
⚠️ **`nfrac=10`, non 13**: verificato in esecuzione (2026-07-23) che i tier splitpipe restano bit-exact
(`dmax=0`) a nfrac=13 su tutte e 5 le traj (anche K=40) — più robusti di quanto il commento di
`run_block_traj_test` assumeva. A **nfrac=10** la normalizzazione devia abbastanza da flippare uno spike →
i parametri divergono → l'assert scatta. È la soglia che rende il gate provato-sensibile.

Run:
```bash
"$MATLAB" -batch "addpath(pwd); ok=false; try, run_block_traj_test(20,'Donatello_FAST',500,1,10); catch e, ok=true; fprintf('atteso FAIL (nfrac=10): %s\n', e.message); end; assert(ok,'CONTROLLO NEGATIVO non scattato: il gate NON discrimina'); disp('=== G2 NEGATIVO OK: il gate discrimina ===')"
```
Expected: `atteso FAIL (nfrac=10): … dmax=…` poi `=== G2 NEGATIVO OK ===`. (Se passa anche a nfrac=10, il gate non discrimina → STOP.)

- [ ] **Step 3: Commit (registro d'esito)**

Non ci sono file di codice nuovi; si registra l'esito nel doc di processo al Task 7. Nessun commit qui.

---

## Task 4: G1 — self-contained / plug&play

**Files:** nessuno nuovo — riusa `run_block_hdl_gate.m` (accetta `blockName`; le dipendenze `.m` isolate coincidono con quelle dei tier).

- [ ] **Step 1: Cancello self-contained sui 3 tier**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); for t={'Donatello_SLOW','Donatello_BALANCED','Donatello_FAST'}, run_block_hdl_gate(t{1}); end; disp('=== G1 OK: 3 tier self-contained + HDL-ready ===')"
```
Expected: per ciascun tier `isolamento OK…`, `VHDL generati: N`, `time-mux (DualPortRAM presente): true`, `=== GATE PASSATO: Donatello_<TIER> … ===`, infine `=== G1 OK ===`.

*(Nessun commit: verifica pura.)*

---

## Task 5: G3 — firma HDL del tier nel VHDL generato

**Files:**
- Create: `matlab/study_tradeoff/common/tier_signature_gate.sh`

- [ ] **Step 1: Genera il VHDL dei 3 tier (per firma e coerenza)**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); for t={'Donatello_SLOW','Donatello_BALANCED','Donatello_FAST'}, rtl_gen_dut(t{1}, ['D:/zbd_tiers/vhdl/' t{1}]); end"
```
Expected: 3 generazioni OK, ciascuna con `DualPortRAM_generic.vhd` e top `Donatello_<TIER>.vhd`.

- [ ] **Step 2: Scrivi il cancello di firma**

```bash
#!/usr/bin/env bash
# tier_signature_gate.sh — verifica che il VHDL di ogni tier porti la firma attesa (SNN round + decode + splitpipe).
# Firme (da snn_variants/README.txt e struct_gate di run_block_a_matrix.sh):
#   SNN:   R2 -> pCa=0,pCm=0,pCx=0 | R5 -> pCa>0,pCm=0,pCx=0 | R9 -> pCa>0,pCm>0,pCx>0
#   decode: fused -> dodec>0,dph=0 | p3 -> dph>0,q1k>0,s3a=0 | p5 -> dph>0,s3a>0,q1k=0
#   splitpipe: local_normalize_ops / local_normalize_mul presenti (registro operandi)
# Sourceable: se caricato con `source`, definisce gate() senza eseguire main (per il test di sensibilita').
set -uo pipefail
gate() { # gate <dir> <round R2|R5|R9> <decode fused|p3|p5>
  local G="$1" rnd="$2" dec="$3" all fail=0
  all=$(find "$G" -name '*.vhd' -exec cat {} + 2>/dev/null)
  cnt() { printf '%s' "$all" | grep -c "$1" || true; }
  local ca cm cx dodec dph q1k s3a ops mul
  ca=$(cnt pCa); cm=$(cnt pCm); cx=$(cnt pCx)
  dodec=$(cnt dodec); dph=$(cnt dph); q1k=$(cnt q1k); s3a=$(cnt s3a)
  ops=$(cnt local_normalize_ops); mul=$(cnt local_normalize_mul)
  case "$rnd" in
    R2) [ "$ca" -eq 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FAIL $G SNN!=R2 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
    R5) [ "$ca" -gt 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FAIL $G SNN!=R5 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
    R9) [ "$ca" -gt 0 ] && [ "$cm" -gt 0 ] && [ "$cx" -gt 0 ] || { echo "FAIL $G SNN!=R9 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
  esac
  case "$dec" in
    fused) [ "$dodec" -gt 0 ] && [ "$dph" -eq 0 ] || { echo "FAIL $G decode!=fused (dodec=$dodec dph=$dph)"; fail=1; } ;;
    p3)    [ "$dph" -gt 0 ] && [ "$q1k" -gt 0 ] && [ "$s3a" -eq 0 ] || { echo "FAIL $G decode!=p3 (dph=$dph q1k=$q1k s3a=$s3a)"; fail=1; } ;;
    p5)    [ "$dph" -gt 0 ] && [ "$s3a" -gt 0 ] && [ "$q1k" -eq 0 ] || { echo "FAIL $G decode!=p5 (dph=$dph s3a=$s3a q1k=$q1k)"; fail=1; } ;;
  esac
  [ "$ops" -gt 0 ] && [ "$mul" -gt 0 ] || { echo "FAIL $G splitpipe assente (ops=$ops mul=$mul)"; fail=1; }
  [ "$fail" = 0 ] && echo "OK  $(basename "$G"): SNN=$rnd decode=$dec splitpipe (pCa=$ca pCm=$cm pCx=$cx | dodec=$dodec dph=$dph q1k=$q1k s3a=$s3a | ops=$ops mul=$mul)"
  return "$fail"
}
main() {
  local ROOT="${1:-D:/zbd_tiers/vhdl}" rc=0
  gate "$ROOT/Donatello_SLOW"     R2 fused || rc=1
  gate "$ROOT/Donatello_BALANCED" R5 p3    || rc=1
  gate "$ROOT/Donatello_FAST"     R9 p5    || rc=1
  [ "$rc" = 0 ] && echo "=== G3 OK: firma HDL corretta sui 3 tier ===" || { echo "=== G3 FALLITO ==="; return 1; }
}
[ "${BASH_SOURCE[0]}" = "${0}" ] && main "$@"
```

- [ ] **Step 3: Esegui il cancello**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
bash matlab/study_tradeoff/common/tier_signature_gate.sh "D:/zbd_tiers/vhdl"
```
Expected: tre righe `OK  Donatello_<TIER>: SNN=… decode=… splitpipe …` e `=== G3 OK ===`.

- [ ] **Step 4: Prova che il cancello è sensibile (firma incrociata deve fallire)**

Run (in una subshell, per non lasciare `set -u` nella shell corrente):
```bash
( source matlab/study_tradeoff/common/tier_signature_gate.sh
  # dir del FAST ma firma dichiarata SLOW: deve fallire (R9!=R2, p5!=fused)
  gate "D:/zbd_tiers/vhdl/Donatello_FAST" R2 fused && echo "NON SENSIBILE (BUG)" || echo "OK sensibile: rifiuta la firma sbagliata" )
```
Expected: righe `FAIL … SNN!=R2 …` / `FAIL … decode!=fused …` poi `OK sensibile: rifiuta la firma sbagliata`.
(Il `main` non gira perché lo script è `source`-ato — parte solo `gate` con gli argomenti sbagliati.)

- [ ] **Step 5: Commit**

```bash
git add matlab/study_tradeoff/common/tier_signature_gate.sh
git commit -m "test(hdl): G3 cancello firma HDL dei tier (round SNN + decode + splitpipe)"
```

---

## Task 6: G4 — coerenza col VHDL misurato + archiviazione nel repo

**Files:**
- Create: `matlab/study_tradeoff/common/tier_coherence_gate.sh`
- Create: `matlab/study_tradeoff/donatello/vhdl_tiers.tar.gz` + `matlab/study_tradeoff/donatello/vhdl_tiers.sha256`

- [ ] **Step 1: Scrivi il cancello di coerenza col misurato**

Confronta la **logica** di `SNN.vhd` e `DEC.vhd` del tier rigenerato con quelli misurati in `D:/zbd_p1` (il wrapper top ha nome diverso — `Donatello_<TIER>` vs `Donatello_LUT64` — e non si confronta). Se `D:/zbd_p1` non esiste, degrada con avviso a "solo firma (G3)".

```bash
#!/usr/bin/env bash
# tier_coherence_gate.sh — la logica SNN.vhd/DEC.vhd del tier rigenerato == quella misurata in D:/zbd_p1.
set -uo pipefail
NEW="${1:-D:/zbd_tiers/vhdl}"; MEAS="${2:-D:/zbd_p1}"
declare -A M=( [Donatello_SLOW]=SLOW [Donatello_BALANCED]=BAL [Donatello_FAST]=FAST )
logic() { grep -v '^\s*--' "$1" | grep -v '^\s*$'; }
rc=0
for t in Donatello_SLOW Donatello_BALANCED Donatello_FAST; do
  meas="$MEAS/${M[$t]}/rtlgen_mdl"
  if [ ! -d "$meas" ]; then echo "SKIP $t: misurato assente ($meas) -> affidarsi a G3"; continue; fi
  newdir=$(dirname "$(find "$NEW/$t" -name 'SNN.vhd' | head -1)")
  for leaf in SNN.vhd DEC.vhd DualPortRAM_generic.vhd; do
    a="$newdir/$leaf"; b="$meas/$leaf"
    [ -f "$a" ] && [ -f "$b" ] || { echo "FAIL $t/$leaf: file mancante"; rc=1; continue; }
    if diff -q <(logic "$a") <(logic "$b") >/dev/null; then echo "OK   $t/$leaf coerente";
    else echo "DIVERSO $t/$leaf"; rc=1; fi
  done
done
[ "$rc" = 0 ] && echo "=== G4 OK: VHDL del blocco == VHDL misurato (i numeri del report valgono) ===" || { echo "=== G4 FALLITO ==="; exit 1; }
```

- [ ] **Step 2: Esegui il cancello di coerenza**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
bash matlab/study_tradeoff/common/tier_coherence_gate.sh "D:/zbd_tiers/vhdl" "D:/zbd_p1"
```
Expected: righe `OK   Donatello_<TIER>/SNN.vhd coerente` (+ DEC/DualPortRAM) e `=== G4 OK ===`. Se qualche `DIVERSO`, indagare la differenza logica prima di procedere (non archiviare un VHDL incoerente).

- [ ] **Step 3: Archivia il VHDL dei 3 tier nel repo (tar + sha256)**

Run:
```bash
cd "D:/zbd_tiers/vhdl"
find Donatello_SLOW Donatello_BALANCED Donatello_FAST -name '*.vhd' | sort > /tmp/tier_manifest.txt
tar -czf vhdl_tiers.tar.gz -T /tmp/tier_manifest.txt
sha256sum $(cat /tmp/tier_manifest.txt) > vhdl_tiers.sha256
DST="D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/study_tradeoff/donatello"
cp vhdl_tiers.tar.gz vhdl_tiers.sha256 "$DST/"
echo "archiviati: $(tar -tzf "$DST/vhdl_tiers.tar.gz" | wc -l) file"
```
Expected: `archiviati: N file` (N ≥ 12: SNN+DEC+wrapper+DualPortRAM(+pkg) × 3).

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/study_tradeoff/common/tier_coherence_gate.sh matlab/study_tradeoff/donatello/vhdl_tiers.tar.gz matlab/study_tradeoff/donatello/vhdl_tiers.sha256
git commit -m "test(hdl): G4 coerenza VHDL tier vs misurato + archivio VHDL dei 3 tier"
```

---

## Task 7: Chiusura — doc di processo e verifica finale

**Files:**
- Modify: `document/SESSION_RESUME.md` (blocco di ripresa), `document/HDL_PHASE.md`

- [ ] **Step 1: Aggiorna `SESSION_RESUME.md`**

Nel blocco `▶ RIPRESA A FREDDO`, sezione dello Studio Trade-off, aggiungi una riga di stato:
> **✅ Tier a blocchi di libreria (2026-07-23):** `Donatello_SLOW/BALANCED/FAST` sono ora blocchi di
> `snn_champions_lib.slx` (splitpipe, LUT-64), self-contained e HDL-ready. Gate verdi: G1 self-contained
> (`run_block_hdl_gate` ×3), G2 `dmax=0` (`run_block_traj_test`, +controllo negativo), G3 firma
> (`tier_signature_gate.sh`), G4 coerenza col misurato (`tier_coherence_gate.sh`) + VHDL archiviato
> (`vhdl_tiers.tar.gz`). Base `Champion`/`LUT{N}` obsoleti, **non toccati** (gestione futura). Report minori
> non rigenerati. Builder: `build_tier_blocks.m`. **PROSSIMO: scelta prescelto** (SAIF + xsim del prescelto).

- [ ] **Step 2: Aggiorna `HDL_PHASE.md`**

Aggiungi una nota nella sezione dei blocchi di libreria: i tre tier sono costruiti da `build_tier_blocks.m`
(riusa i mattoni condivisi estratti da `build_hdl_variants` al 2026-07-23); i loro gate sono G1–G4 sopra;
il VHDL è archiviato in `study_tradeoff/donatello/vhdl_tiers.tar.gz` (coerente col misurato in `D:/zbd_p1`).

- [ ] **Step 3: Verifica finale del working tree e dello stato libreria**

Run:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git status --porcelain
cd matlab
"$MATLAB" -batch "addpath(pwd); lib='snn_champions_lib'; load_system(lib); b=find_system(lib,'SearchDepth',1,'BlockType','SubSystem'); fprintf('%d blocchi; tier presenti=%d\n', numel(b), sum(~cellfun('isempty',regexp(b,'Donatello_(SLOW|BALANCED|FAST)$')))); close_system(lib,0)"
```
Expected: `git status` mostra solo i doc modificati (poi committati); MATLAB stampa `… tier presenti=3`.

- [ ] **Step 4: Commit finale**

```bash
git add document/SESSION_RESUME.md document/HDL_PHASE.md
git commit -m "docs(hdl): tier Donatello a blocchi di libreria (build + gate G1-G4) nello stato di ripresa"
```

---

## Self-Review (svolto in scrittura)

- **Spec coverage:** §2 criteri 1–4 → Task 2 (presenti), Task 4/G1 (self-contained), Task 3/G2 (simulabili+corretti), Task 5/G3 + Task 6/G4 (HDL-ready+coerenti+archivio). §5 meccanismo → Task 1 (refactor) + Task 2. §7 chiusura → Task 7. §3 «non toccare i base» → Task 2 Step 3 lo asserisce. Tutte coperte.
- **Placeholder scan:** nessun TBD/TODO; codice completo per il nuovo (`build_tier_blocks`, i due gate); il refactor è un move descritto + cancello di equivalenza.
- **Type/nome consistency:** `Donatello_SLOW/BALANCED/FAST`, `snn_variants/snn_b2_fsm_R{2,5,9}.m`, decode `fused/p3/p5`, `splitpipe`, `NCHAMP=64` coerenti in tutti i task; firme G3 coerenti con `snn_variants/README.txt` e `struct_gate`.

## Note di rischio (dalla spec §9)
- Il refactor (Task 1) è il punto caldo: il cancello non-regression (Champion split + ACC_IIDM_M) lo blinda.
- `D:/zbd_p1` è scratch: se assente, G4 degrada a G3 + archivio; l'archivio `vhdl_tiers.tar.gz` rende la coerenza permanente.
- `build_hdl_variants` deve restare invariato nel comportamento: garantito dal non-regression di Task 1.
