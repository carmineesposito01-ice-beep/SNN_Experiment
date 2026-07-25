# Blocco B — Controllore IIDM standalone + studio NFRAC — Design

**Data:** 2026-07-25 · **Branch:** `Simulink_Importer` · **Stato:** spec di design (da revisionare)

## 1. Obiettivo

Produrre un **blocco di libreria riutilizzabile e GENERICO** — il controllore **`ACC-IIDM` standalone**,
HDL-ready, configurabile in precisione (menu NFRAC). **Non è legato a Donatello**: riceve i 5 parametri IDM
*in ingresso* (da qualunque fonte) e calcola l'accelerazione. Si compone naturalmente con `Donatello_Tier`
(l'estimator, Blocco A), ma resta usabile per conto suo in progetti diversi:

```
[qualunque estimator, es. Donatello_Tier → v0,T,s0,a,b]  →  ACC-IIDM (s,v,dv,v_l + v0,T,s0,a,b → accel)
```

Prima del blocco, uno **studio NFRAC dell'IIDM** che ne caratterizza il compromesso sicurezza/fedeltà/hardware.
È lo **studio SPECCHIATO** di quello dell'estimator: **stesse metriche**, ma con la **SNN congelata** (piena
precisione) e questa volta l'**IIDM che varia**.

**Perché "solo NFRAC" e non TIER:** sull'IIDM il TIER **non è un vero trade-off** — la variante veloce `M`
(SP4) domina la `SP3` (riferimento) su *entrambi* gli assi (LUT −21% **e** Fmax ×4,6). Non c'è SLOW↔FAST da
esporre. L'unico knob con senso reale è la precisione fixed-point (`acc_types` nfrac). L'architettura resta
fissa a **M** (la migliore).

## 2. Fattibilità (verificata)

- **L'FSM IIDM standalone esiste già**: `acc_iidm_fsm(s, v, dv, v_l, p, rst) → accel` (`matlab/acc_iidm_fsm.m`)
  prende i 5 parametri `p=[v0;T;s0;a;b]` **in ingresso** (niente SNN dentro), architettura M (le fasi
  `iidm_prep/iidm_nd/iidm_use/iidm_final` + `fsm_div`), già `dmax=0` vs `acc_iidm_open` sul dataset intero
  (60×1000 control-step). Il Blocco B è **wrappare + menu NFRAC**, non un lavoro da zero.
- **Type-parametrico**: `acc_types(dt, nfrac)` (`matlab/acc_types.m`) definisce i tipi fixed; nfrac = bit
  frazionari (interi fissi, come `snn_types`). Default nfrac=8.
- **Riferimento double**: `acc_iidm_open(...,T)` type-parametrico (T assente → double). È l'unica fonte della
  matematica IIDM (usata da SP2 e dal plant `cf_plant_lib/ACC_IIDM`).
- **Budget già noto** (`run_acc_fixed_sweep`, log `sweep_nfrac8_60traj.log`): floor **nfrac=8** — a nfrac=6
  `E_iidm` (footprint in accel della quantizzazione IIDM) p99=0,325 max=1,78 → l'IIDM diventa la fonte d'errore
  dominante (sfonda `E_snn`, la quantizzazione già accettata della rete). nfrac=8 passa con margine ~1,75×.

## 3. Architettura — due parti

### Parte 1 — Studio NFRAC dell'IIDM (isolato in `matlab/Quantizzation_Study_IIDM/`, prefisso `qzi_`)

Mirror dello studio dell'estimator, applicato all'IIDM. **Riuso**: `qz_cl_sim`, `qz_safety_metrics`,
`test_dataset_exhaustive.mat`, il tooling di sintesi `study_tradeoff/common/*.tcl`, il generatore report.

**Studio SPECCHIATO dell'estimator: STESSE metriche, SNN congelata, IIDM che varia.** L'anello chiuso fedele
gira con l'**SNN a piena precisione** (congelata) e l'**IIDM a nfrac** ∈ {13,8,5,2}. Lo stepFun usa
`acc_iidm_open` con `acc_types('fixed',nfrac)` per l'accel (SNN fissa → si isola l'effetto della quantizzazione
IIDM). Le **metriche sono le stesse dello studio dell'estimator**, con quelle sull'*uscita diretta* calcolate
sull'accel (dove là erano sui 5 parametri):

| Metrica (come l'estimator) | Nell'IIDM specchiato |
|---|---|
| Sicurezza — 0 collisioni extra vs oracolo | identica (esito car-following) |
| Fedeltà — NRMSE | NRMSE dell'**accel** (uscita IIDM), normalizzato sull'escursione |
| Severità — impact_dv sulle inevitabili | identica |
| Accuratezza open-loop — max\|d\| worst-case | max\|d\| sull'**accel** |
| Hardware — LUT/FF/DSP/potenza/Fmax vs nfrac | sintesi di `acc_iidm_fsm` (invece dell'SNN forward) |

Lente aggiuntiva specifica dell'IIDM: il **budget `E_iidm` vs `E_snn`** (già misurato, floor 8) per collocare
dove l'IIDM diventa la fonte d'errore dominante.

- **Hardware**: sintesi io-timed (deploy 125 ns) di `acc_iidm_fsm` a ogni nfrac ∈ {13,8,5,2} → LUT/FF/DSP/BRAM
  + potenza (**dinamica** prominente) + **slack (WNS)**. Insieme ridotto (4 punti) per non sforare le ore Vivado.
- **Report SPECCHIATO**: documento dedicato a sé `report/ACC_IIDM_QUANTIZATION_REPORT.{md,pdf}` (generatore
  deterministico grounded, via skill `create-report`), stessa struttura e disciplina del report dell'estimator:
  numeri dai TSV, figure, equazioni, ToC, lettura onesta.

Output dati (committati): `qzi_cl_sweep.tsv`, `qzi_res_sweep.tsv`, `qzi_sev_sweep.tsv`, `qzi_acc_sweep.tsv`.

### Parte 2 — Blocco `ACC-IIDM` (in `snn_champions_lib.slx`)

**Nome `ACC-IIDM`, senza prefisso Donatello**: il blocco è generico (riceve i parametri IDM da qualunque
fonte, non solo dall'SNN). Distinto da `Donatello_ACC_IIDM` (SP2, che ha l'SNN *dentro*): questo è il solo
controllore IIDM. File/funzioni di supporto mantengono il prefisso `acc_iidm_`/`qzi_`.

- **Sorgente**: `acc_iidm_fsm` con `acc_types` nfrac **cotto concreto** per variante (stessa tecnica del menu
  NFRAC di `build_tier_configurable`: sostituzione del nfrac hardcoded con il valore, un Variant Subsystem con
  le varianti nfrac, mask popup). **Abilitatore** (come Task 0 mixed-precision): parametrizzare `nfrac` in
  `acc_iidm_fsm` / nelle funzioni-fase (oggi `acc_types('fixed')` è cotto a default dentro).
- **I/O**: 9 ingressi (`s, v, dv, v_l, v0, T, s0, a, b`) → 1 uscita (`accel`). Le 5 uscite parametri di
  `Donatello_Tier` si collegano diretto ai 5 ingressi parametri.
- **Config**: menu **NFRAC** {13,8,5,2}. I livelli sotto il floor (5, 2) **marcati** nella descrizione come
  "oltre il budget E_iidm / solo-sicurezza" **se e solo se** lo studio (Parte 1) conferma che il car-following
  regge comunque; altrimenti il menu si ferma a 8.
- **Auto-layout + pulizia**: `arrangeSystem` prima del salvataggio; rimozione robusta dei sottosistemi default
  del template (lezione appresa dal Blocco A: il template lascia un `Subsystem1` inerte).

## 4. Cancelli (disciplina dell'estimator)

- **G0 — abilitatore bit-exact**: a nfrac=13 (o al nfrac di default storico), l'IIDM parametrizzato ==
  `acc_iidm_fsm` esistente, `dmax=0` sul dataset. Il nfrac deve *mordere* ai bit bassi (controllo negativo).
- **G1 — parità vs riferimento**: l'IIDM fixed a nfrac == `acc_iidm_open` con `acc_types('fixed',nfrac)`,
  `dmax=0` sul dataset intero (già il cancello G2 storico di `acc_iidm_fsm`).
- **G2 — studio comportamentale nei due sensi**: la sicurezza regge (0 coll extra) e la fedeltà degrada in modo
  misurabile; il rilevatore accetta full-precision e rifiuta una config palesemente rotta.
- **G3 — blocco no-regressione**: la variante di default del blocco riproduce il riferimento in streaming
  (`run_block_*_test`, `dmax=0`); il menu non regredisce.
- **G4 — HDL da blocco**: `makehdl` sul blocco genera VHDL coerente (con l'handshake della divisione
  `HDLMathLib/Divide`, la forma FSM di M).
- **G5 — report**: determinismo `.md` + QC visiva + audit avversariale (come per l'estimator).

## 5. Riuso (niente reinvenzione)

| Componente | Fonte |
|---|---|
| Anello chiuso fedele | `qz_cl_sim.m` (stepFun iniettato) |
| Metriche SSM | `qz_safety_metrics.m` |
| Dataset esaustivo | `test_dataset_exhaustive.mat` (99 traj) |
| Matematica IIDM (rif. double) | `acc_iidm_open.m` (type-parametrico, invariato) |
| FSM IIDM (HDL) | `acc_iidm_fsm.m` (da parametrizzare in nfrac) |
| Tooling sintesi | `study_tradeoff/common/{synth,impl}_point.tcl` |
| Tecnica menu NFRAC | `build_tier_configurable.m` (Variant Subsystem + mask popup + tipi cotti) |
| Generatore report | `scripts/build_quantization_report.py` (da clonare/adattare) |

## 6. Rischi / note

- **`acc_iidm_fsm` è "fixed-only" con nfrac cotto dentro** per un vincolo HDL Coder (struct di prototipi
  empty-typed rifiutato nella conversione MATLAB-to-dataflow). Parametrizzare nfrac va fatto **senza**
  reintrodurre quel vincolo — probabilmente cuocendo il valore concreto per variante (come l'estimator), non
  passando un `nfrac` runtime. Da verificare in fase abilitatore.
- **La divisione** nell'IIDM (`fsm_div`/`HDLMathLib/Divide`) è delicata per l'HDL (lezione SP4 §9): la chart
  deve restare **sola** nel subsystem, altrimenti scatta la conversione dataflow che vieta `tanh` fixed. Il
  blocco va montato di conseguenza.
- **Livelli 5 e 2 oltre il budget**: da includere nel menu solo se lo studio conferma la sicurezza; altrimenti
  il menu è {13,10,8} o {13,8}. Decisione ancorata ai dati, non a priori.
- **Studio isolato in `Quantizzation_Study_IIDM/`**, core IIDM (`acc_iidm_open`/`acc_iidm_fsm`) intatto salvo
  la parametrizzazione nfrac provata bit-exact.
- Il **plant/anello chiuso in Simulink** (Blocco B *in retroazione*) resta **fuori scope** qui: questo blocco è
  il controllore standalone; la validazione è in MATLAB (`qz_cl_sim`). `closed_loop_demo.slx` NON si tocca.

## 7. Fuori scope (esplicito)

- TIER SLOW/BAL/FAST per l'IIDM (nessun trade-off reale; M domina).
- Mixed-precision per-campo dell'IIDM (lo studio dell'estimator ha mostrato nessun guadagno HW netto; non si
  replica salvo richiesta).
- Wrapper double-input / modo comportamentale (deciso di non farlo sul Blocco A; stessa logica qui).
- Integrazione estimator+IIDM in un blocco unico (l'obiettivo è la separazione/componibilità).
