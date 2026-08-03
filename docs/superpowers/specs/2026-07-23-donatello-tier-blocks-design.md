# Blocchi tier Donatello (SLOW / BALANCED / FAST) in libreria — design

**Data:** 2026-07-23
**Track:** HDL / Simulink_Importer
**Stato:** design approvato a voce (2026-07-23), in attesa di review della spec scritta

---

## 1. Contesto e motivazione

Lo Studio Trade-off (Blocco A) ha caratterizzato tre configurazioni del blocco Donatello — **SLOW**,
**BALANCED**, **FAST** — sul Fmax reale io-timed (report `report/Trade_Off_Study_Parte_A.pdf`,
record `matlab/study_tradeoff/donatello/RESULTS.md §16`). Una verifica sul campo (2026-07-23) ha però
mostrato che **quei tre tier non esistono come oggetti utilizzabili**:

- **non sono blocchi** di `snn_champions_lib.slx` (la libreria contiene `Donatello`, `Donatello_Champion`,
  `Donatello_LUT{16..512}`, `Donatello_ACC_IIDM`, `Donatello_ACC_IIDM_M` — nessun tier);
- sono **configurazioni parametriche** (decode `fused|p3|p5` × snapshot SNN `R2|R5|R9` × `archStyle=splitpipe`)
  materializzate come VHDL in scratch **fuori dal repo** (`D:/zbd_p1/{SLOW,BAL,FAST}/rtlgen_mdl/`);
- il VHDL misurato **non è versionato** (l'unico archivio nel repo, `donatello/vhdl_snn_points.tar.gz`, sono
  probe forward-only `snn_fwd_r*`, senza decode).

Finché resta così, scegliere il tier «prescelto» per il Blocco B significa scegliere un oggetto che non si
può piazzare in Simulink né deployare. Questo design colma il buco: porta i tre tier a **blocchi di libreria
veri**, plug&play, HDL-ready e coerenti col VHDL già misurato.

I blocchi base `Champion`/`LUT{N}` sono considerati **obsoleti** (i deployabili sono i tre tier) e in questo
lavoro **non vengono toccati**: la loro gestione è rinviata. I report minori legati (studio di precisione
LUT-N, `document/DECODE_LUT_SWEEP.md`) **non vengono rigenerati** ora.

## 2. Obiettivo e criteri di successo

Obiettivo: i tre tier diventano blocchi di `snn_champions_lib.slx` **funzionanti come gli altri blocchi**.
Successo = tutti i seguenti veri (mappano i tre requisiti posti dall'utente):

1. **Presenti in libreria** — `Donatello_SLOW`, `Donatello_BALANCED`, `Donatello_FAST` compaiono in
   `snn_champions_lib.slx` (browser + `find_system`).
2. **Plug&play / self-contained** — G1 verde: col **solo** `.slx` (nessun `.m` sul path) HDL Coder genera il
   loro VHDL.
3. **Simulabili e corretti** — G2 verde: piazzati in un modello e simulati danno i 5 parametri con `dmax = 0`
   vs il riferimento software.
4. **HDL-ready e coerenti col misurato** — G3 (firma) + G4 (coerenza col VHDL di `D:/zbd_p1`) verdi, e VHDL
   archiviato nel repo → i numeri Fmax/area/potenza del report valgono per il blocco di libreria.

## 3. Scope

**In scope**
- Tre blocchi `Donatello_SLOW/BALANCED/FAST`, architettura `splitpipe`, decode-sigmoide LUT-64.
- Una funzione `build_tier_blocks.m` che li aggiunge **senza toccare** gli altri blocchi.
- Quattro cancelli d'accettazione (G1–G4) che assertano ed sono provati sensibili.
- Archiviazione del VHDL dei tre tier nel repo (tar + sha256).
- Aggiornamento dei doc di processo (`SESSION_RESUME.md`, `HDL_PHASE.md`).

**Fuori scope (ora)**
- Toccare `Champion`/`LUT{N}` (obsoleti → future work).
- Rigenerare i report minori (`DECODE_LUT_SWEEP.md`) o il report Blocco A.
- Sintesi Vivado dei tier (i numeri sono già nel report; G4 li eredita per coerenza del VHDL).
- Scelta del prescelto per il Blocco B, SAIF-power, verifica xsim del prescelto (passi successivi).

**Fase 2, best-effort (§8)**: tentativo del blocco unico configurabile — solo dopo Fase 1 verde.

## 4. I tre blocchi (definizione tecnica)

| blocco | SNN snapshot | decode-pipeline | architettura | sigmoide | latenza [clk] |
|---|---|---|---|---|---|
| `Donatello_SLOW`     | `snn_variants/snn_b2_fsm_R2.m` | `fused` | `splitpipe` | LUT-64 | 342 |
| `Donatello_BALANCED` | `snn_variants/snn_b2_fsm_R5.m` | `p3`    | `splitpipe` | LUT-64 | 364 |
| `Donatello_FAST`     | `snn_variants/snn_b2_fsm_R9.m` | `p5`    | `splitpipe` | LUT-64 | 406 |

- **Interfaccia** (identica ai Donatello esistenti): ingressi fisici `s, v, dv, v_l` → uscite `v0, T, s0, a, b`
  (fixed, ≥20 bit frazionari). Edge-triggered (1 campione = 1 inferenza), **niente start/done**.
- **Stesso risultato, diverso profilo.** I tre snapshot sono «mirror BIT-EXACT di `snn_core`»
  (`snn_variants/README.txt`): differiscono solo per **profondità di pipeline** (firme `pCa/pCm/pCx`), non per
  valore. Anche i decode `fused/p3/p5` sono la stessa funzione a diverse profondità di fase. → i tre tier
  producono **gli stessi 5 parametri**, differendo per **latenza** (342/364/406 clk) e **profilo HDL/risorse**
  (i tier del report). Conseguenza operativa: G2 usa **un solo golden** per tutti e tre.
- **Snapshot congelati, non il file corrente.** `snn_b2_fsm_R9.m` **differisce** dal `snn_b2_fsm.m` corrente
  (avanzamenti/CRLF): per riprodurre fedelmente i numeri del report i tier inlinano **gli snapshot immutabili**
  di `snn_variants/`, non il file condiviso. È il principio già adottato dallo studio (`gen_donatello_point`).

## 5. Meccanismo di costruzione — `build_tier_blocks.m`

Nuova funzione che apre `snn_champions_lib.slx`, aggiunge/aggiorna **solo** i tre blocchi tier e salva, senza
rimontare gli altri blocchi. Riusa **i mattoni già provati** di `build_hdl_variants.m` (nessuna logica di
generazione nuova):

- `mount_split(sub, in, out, snnCode, decCode)` — monta le due MATLAB Function SNN + DEC (due entità di
  sintesi).
- `snnCode = snn_chart_code(srcRom, srcTypes, srcFsm, nrm, /*pipe=*/true)` — forward + normalize con il
  **registro operandi** (splitpipe); `srcFsm` = lo snapshot del tier.
- `decCode = dec_chart_code(srcLut, decVariant, 64, 'shared')` — latch + macchina a fasi del decode, con
  `decVariant ∈ {fused,p3,p5}` e sigmoide LUT-64.
- Sorgenti inlinati (single-source, letti a build-time → self-contained): `b2_rom_active` (via
  `gen_b2_rom('Donatello')`), `snn_types`, lo snapshot SNN, e la composizione decode
  (`snn_decode_lut` + `decode_a/a1/a2/b/b1/b2/c/c1/c2`); `nrm` = norma del champion Donatello da
  `champions_export.mat`.

**Refactor minimo previsto:** le funzioni di montaggio (`mount_split`, `snn_chart_code`, `dec_chart_code`,
`decode_phase_code`, `normalize_code`, `inlined_header`) sono oggi **locali** a `build_hdl_variants.m`. Vanno
rese condivise (estratte in file/funzioni riusabili) così che sia `build_hdl_variants` sia `build_tier_blocks`
le usino da **un'unica fonte** — evitando copie sincronizzate a mano. Il refactor non cambia il comportamento
di `build_hdl_variants` (i blocchi base restano bit-identici: verificabile).

**Non toccare i base:** `build_tier_blocks` fa `delete_block`+`add_block` solo dei tre `Donatello_<TIER>`;
gli altri blocchi non vengono aperti né riscritti. Dopo il salvataggio si verifica (dump del `.slx`) che
`Champion`/`LUT{N}` conservino la loro firma e che siano comparsi esattamente i tre tier.

## 6. Verifiche — cancelli d'accettazione (G1–G4)

Ogni cancello **asserisce** (non stampa e basta) e, dove ha senso, è **provato sensibile** (rotto apposta).
Tutti girano sul **dataset**, riportando quanti-su-quanti. Fase 1 è **MATLAB-only** (no Vivado): G1 `makehdl`,
G2 simulazione, G3 grep sul VHDL, G4 diff sul VHDL.

- **G1 — self-contained / plug&play.** `run_block_hdl_gate('Donatello_<TIER>')` per i tre: copia **solo** il
  `.slx` in cartella isolata, toglie `matlab/` dal path (assert: nessun `.m` del progetto raggiungibile),
  istanzia il blocco, `makehdl`. Verde = VHDL generato **+** `DualPortRAM_generic.vhd` presente (time-mux del
  deployato). Il gate esiste già e accetta un `blockName`: basta invocarlo sui tre tier — le dipendenze `.m`
  che verifica isolate dal path (`snn_b2_fsm`, `b2_rom_active`, `snn_types`, `snn_decode_lut`, …) sono le
  stesse che i tier inlinano.
- **G2 — simulabile + corretto.** Piazza ogni blocco in un modello, lo pilota con le traiettorie reali
  (`test_dataset.mat`) campione-a-campione, confronta i 5 parametri col **golden software** (norm-float +
  `snn_core` + `snn_decode_lut(·,64)`). Verde = **`dmax = 0`** su tutte le traiettorie del dataset (un golden
  per i tre). Sensibile: ingresso degradato < 20 bit frazionari → `dmax > 0` (il gate discrimina).
  Riusa/estende `run_block_traj_test`.
- **G3 — firma HDL.** Nel VHDL generato le firme del tier devono combaciare:
  - SNN: `R2 → pCa=0,pCm=0,pCx=0` · `R5 → pCa>0,pCm=0,pCx=0` · `R9 → pCa>0,pCm>0,pCx>0`;
  - decode: `fused → dodec>0,dph=0` · `p3 → dph>0,q1k>0,s3a=0` · `p5 → dph>0,s3a>0,q1k=0,«16#06#»=0`;
  - splitpipe: `local_normalize_ops`/`local_normalize_mul` presenti (registro operandi).
  Riusa la logica di `struct_gate` (`run_block_a_matrix.sh`). Sensibile: firma di un tier diverso → FALLITO.
- **G4 — coerenza col misurato.** Il VHDL rigenerato dal blocco (entità **SNN.vhd** + **DEC.vhd**) coincide
  **bit-per-bit** con quello misurato in `D:/zbd_p1/{SLOW,BAL,FAST}/rtlgen_mdl/`; il solo wrapper cambia nome
  (`Donatello_<TIER>` vs `Donatello_LUT64`) e va confrontato per struttura, non per nome. Verde = logica
  identica → **i numeri Fmax/area/potenza del report valgono per il blocco di libreria**. Se `D:/zbd_p1` non
  fosse più disponibile, G4 degrada a confronto delle firme (G3) più i numeri del report.
  **Archiviazione:** i tre VHDL (wrapper + SNN + DEC + DualPortRAM) sono salvati nel repo come tar + `sha256`
  (schema di `donatello/vhdl_snn_points.tar.gz`) → coerenza verificabile per sempre, senza scratch.

## 7. Chiusura

- Verifica del working tree; commit di `snn_champions_lib.slx` + `build_tier_blocks.m` + refactor dei mount
  condivisi + i gate + il VHDL archiviato. Conventional commit **senza** `Co-Authored-By`.
- Aggiornamento dei doc di processo (`SESSION_RESUME.md` blocco di ripresa, `HDL_PHASE.md`) col nuovo stato:
  i tre tier sono ora blocchi di libreria; i base restano obsoleti/da gestire.
- Report minori (`DECODE_LUT_SWEEP.md`) e report Blocco A **non** toccati (scelta esplicita dell'utente).

## 8. Fase 2 — blocco unico configurabile (tentativo best-effort)

Solo **dopo** che la Fase 1 è verde. `Donatello_Tier` = **Variant Subsystem** con le tre chart dentro
(le stesse dei tre blocchi) + **mask** enum `SLOW/BALANCED/FAST` che attiva la variante.

- **Successo** = G1 + G2 + G3 verdi sul tier attivo per **tutti e tre** i valori del mask (HDL Coder genera il
  VHDL della sola variante attiva, self-contained e bit-exact).
- **Fallback esplicito** = se HDL Coder non genera dal Variant, o rompe il self-containment o la bit-exactness,
  si **abbandona** il blocco configurabile e restano i tre blocchi separati (già validi dalla Fase 1).
- È un pattern **nuovo** per questo progetto (nessun uso di Variant/Mask oggi): il rischio è reale e per questo
  è confinato a un tentativo con fallback, non un requisito.

## 9. Rischi e note

- **`build_hdl_variants` rimonta TUTTI i blocchi** a ogni chiamata: `build_tier_blocks` **non** deve delegare
  ad esso il montaggio globale, ma aggiungere solo i tre tier. Il refactor condiviso (§5) va fatto in modo che
  `build_hdl_variants` resti invariato nel comportamento.
- **Snapshot vs forward corrente:** i tier usano gli snapshot congelati; eventuali bugfix del forward corrente
  non ancora negli snapshot sono un tema dei «vecchi» (future work), non di questo lavoro.
- **`D:/zbd_p1` è scratch** (fuori dal repo): G4 dipende dalla sua esistenza al momento del run;
  l'archiviazione nel repo rende la coerenza permanente a prescindere.
- **Il `.slx` è tracked e binario:** dopo il build si verifica per dump che siano cambiati solo i tre tier
  (base con firma invariata), non tutta la libreria.
- **Ambiente:** MATLAB `"C:\Program Files\MATLAB\R2026a\bin\matlab.exe" -batch`; `makehdl`/scratch su path
  **senza spazi** (`tempdir` o `D:/…`); Fase 1 **non richiede Vivado**.

## 10. Riferimenti

| Riferimento | Tema |
|---|---|
| `matlab/build_hdl_variants.m` | mattoni di montaggio (mount_split, snn_chart_code pipe, dec_chart_code) |
| `matlab/study_tradeoff/common/gen_donatello_point.m` | come lo studio materializzava un tier |
| `matlab/study_tradeoff/common/run_block_a_matrix.sh` (`struct_gate`) | firma decode + SNN (base di G3) |
| `matlab/run_block_hdl_gate.m` | cancello self-contained (base di G1) |
| `matlab/snn_variants/{README.txt,snn_b2_fsm_R2,R5,R9.m}` | snapshot congelati dei tre tier |
| `matlab/study_tradeoff/donatello/RESULTS.md §16` · `report/Trade_Off_Study_Parte_A.md §5-§6` | numeri dei tier |
| `D:/zbd_p1/{SLOW,BAL,FAST}/rtlgen_mdl/` | VHDL misurato (riferimento di G4) |
