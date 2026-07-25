# Studio quantizzazione — validazione car-following (Donatello) — documento sorgente

> **Ruolo**: documento di lavoro che accumula metodo, dati e risultati della **validazione car-following** dello
> studio di quantizzazione (nfrac unico). È la **sorgente** del futuro report (come `DECODE_LUT_SWEEP.md`). Track
> `Simulink_Importer`. Ogni numero è grounded su `cl_sweep.tsv` (anello chiuso), `acc_sweep.tsv` (accuratezza
> open-loop) e sulla prova di severità (`qz_cl_severity`). Tutto isolato in `matlab/Quantizzation_Study/`; gli
> script funzionanti originali **non toccati** (regola §3.1 della spec).

## 1. Scopo
Per il candidato al deploy **Donatello** (il forward del blocco `Donatello_Tier`, prescelto BAL), caratterizzare
l'effetto della quantizzazione fixed-point del core (`nfrac` = bit frazionari, tenendo fissi gli interi per campo)
sul **comportamento car-following in anello chiuso**, spingendosi fino al limite estremo **nfrac=2**. La domanda
guida dell'utente: *«collisioni=0 serve a poco senza scenari di cut-in; e non solo l'RMSE, anche l'NRMSE sui
parametri»*. Lo studio risponde con scenari di cut-in **reali** e metriche di sicurezza vere.

## 2. Metodo

### 2.1 Dataset esaustivo (nuovo)
Il `test_dataset.mat` storico (60 traj) è inadeguato: profili di sola velocità leader, **nessun evento forzante**
(nessun cut-in fisico), gap mai spinto piccolo. `test_dataset_exhaustive.mat` (99 traj) è generato dal
**generatore canonico del Simulator** — `utils/closed_loop_eval.build_scenarios` (la funzione su cui girano i
report del progetto, INVARIANTE) — via `gen_exhaustive_qz_dataset.py` (nessuna copia, nessun drift):

- **9 scenari canonici** × **11 estrazioni di `params_gt`** (campionate per regime — highway/urban/truck/mixed —
  da `data.generator._sample_scenario`, la distribuzione-label del champion): `following, stop_and_go, hard_brake`
  (−7 m/s²)`, cut_in, sinusoidal, cut_out, static_target, panic_stop` (−9 m/s²)`, aggressive_cut_in`.
- **33 traiettorie con evento cut-in a teletrasporto di gap** `(t_cut, new_gap)`: `cut_in`, `cut_out`,
  `aggressive_cut_in` (11 ciascuno). Il cut-in **non è** un profilo di velocità: è una discontinuità di gap
  relativa all'ego (a `t_cut` un veicolo più vicino diventa il leader → il gap crolla). Rappresentazione canonica
  del progetto, non inventata.

Isolato: assemblato in `.mat` da `qz_build_exhaustive_dataset.m`. Il `test_dataset.mat` globale (20+ cancelli che
vi dipendono) **non è toccato**.

### 2.2 Anello chiuso FEDELE (nuovo — sostituisce il vecchio, difettoso)
`qz_cl_sim.m` è un **port fedele** di `utils/closed_loop_eval.simulate()`: gap tracciato direttamente
(`s += (v_l − v)·DT`, **nessun floor**), collisione rilevata a `s ≤ 0`, teletrasporto `cut_in` al passo giusto,
`dv = v − v_l` (corrente, come in training). Riusa `qz_snn_cl_step` (normalize → core a `nfrac` → decode LUT-64 →
`acc_iidm_open`) come step; lo step è iniettato via handle, così lo stesso anello gira con la **rete** o con
l'**oracolo** (params veri).

> ⚠️ **Perché era necessario.** Il vecchio anello (`qz_cl_run`) **clampava il gap** a `s_lo = 0.5·s0` e contava le
> collisioni su quel gap clampato → collisioni **strutturalmente non rilevabili** sui cut-in. Verificato che sul
> vecchio dataset (facile) il floor non mordeva, ma su un cut-in (gap teletrasportato a pochi metri) avrebbe
> mascherato ogni crash. Sostituito.

**Cancello-chiave di parità** (`qz_cl_parity_gate.m`): oracolo MATLAB (`qz_cl_sim` + `acc_iidm_open` double) vs
`simulate()` **float di Python**, sui 9 scenari passo-passo → **max|Δs| = 2.24×10⁻⁶ m**, flag collisione coerenti
(anche `aggressive_cut_in`: collide a step 308 in entrambi). Il port è provato fedele al motore canonico, non solo
plausibile.

### 2.3 Baseline oracolo (la mossa metodologica)
Prima dello sweep, l'**oracolo** (params veri, controllore a conoscenza perfetta) gira su tutte le 99 traiettorie
→ marca quali sono **fisicamente evitabili**. Poi, per la rete a ogni `nfrac`, le collisioni su traiettorie che
l'oracolo **evita** = **`coll_extra`** = **costo reale della quantizzazione**, separato da ciò che nessun
controllore può evitare. Metriche SSM (`qz_safety_metrics.m`, port di `safety_metrics`): collisione, min_gap,
min_TTC, max_DRAC, **brake_margin** (evitabilità con segno; <0 = inevitabile), impact_dv. Vista rete: NRMSE
per-parametro vs nfrac=13.

## 3. Risultati — accuratezza open-loop (worst-case, `acc_sweep.tsv`)
`qz_run_fixed_sweep`: core `fi` sul golden di Donatello, decode esatto → **max|d|** sui 5 parametri (fisico, la
vista **pessimista**; floor double ≈ 0.03).

| nfrac | 13 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| max\|d\| | 0.028 | 0.47 | 0.52 | 0.52 | 0.50 | 0.55 | 0.74 | 1.03 | 0.90 | 0.75 | 1.88 | 2.45 |

Worst-case **rumoroso** (max su 5 parametri × sequenza: n5-6 oscillano ~0.9-1.0) ma con trend chiaro: near-exact a
nfrac=13, plateau ~0.5 su n8-12, **degrado marcato sotto nfrac=4** (1.88 a n3, 2.45 a n2). Già a nfrac medi il
parametro peggiore è off di ~0.5-1.0 (fisico) → in open-loop la rete **sembra sensibile** — ed è questa vista che
l'anello chiuso (§4) capovolge.

## 4. Risultati — car-following in anello chiuso (`cl_sweep.tsv`, 99 traj)

Baseline oracolo: **3/99 traiettorie inevitabili** (tutte `aggressive_cut_in`, dove servono ~12.5 m/s² di
decelerazione contro un massimo fisico di 9 → collide anche l'oracolo).

| nfrac | coll_extra | coll_tot | min_gap (ev) | brake_margin (ev) | NRMSE param (media) |
|---|---|---|---|---|---|
| **2** | **0** | 3 | 0.304 | −0.111 | **0.327** |
| 3 | **0** | 3 | 0.289 | −0.120 | 0.201 |
| 4 | **0** | 3 | 0.307 | −0.085 | 0.109 |
| 5 | **0** | 3 | 0.282 | −0.109 | 0.097 |
| 6 | **0** | 3 | 0.219 | −0.167 | 0.093 |
| 7 | **0** | 3 | 0.241 | −0.144 | 0.090 |
| 8 | **0** | 3 | 0.285 | −0.105 | 0.089 |
| 9 | **0** | 3 | 0.237 | −0.152 | 0.087 |
| 10 | **0** | 3 | 0.234 | −0.153 | 0.086 |
| 11 | **0** | 3 | 0.254 | −0.134 | 0.084 |
| 12 | **0** | 3 | 0.274 | −0.114 | 0.083 |
| 13 (rif.) | **0** | 3 | 0.264 | −0.122 | 0.000 |

- **`coll_extra` = 0 a OGNI livello, fino a nfrac=2.** La rete quantizzata non causa **una singola collisione
  extra** su 99 scenari duri (min gap sceso a **0.25 m**, 33 cut-in). Eguaglia l'oracolo sull'evitamento a ogni
  profondità di bit; le 3 collisioni sono le stesse inevitabili dell'oracolo.
- **Margini piatti**: `min_gap` (~0.25 m, il passaggio più stretto sui 96 evitabili) e `brake_margin` (~−0.12 m,
  dip transitorio) sono **non-monotoni e quasi costanti** su nfrac → li fissa la **geometria dello scenario**, non
  la quantizzazione (perfino il riferimento nfrac=13 tocca −0.12).
- **NRMSE**: degrado **liscio con ginocchio ~nfrac=4** (0.109), che accelera sotto (0.201 a n3, 0.327 a n2).
- **`max_DRAC`** (in tsv, non in tabella): rumoroso (153–1950, non-monotono), dominato dal singolo istante più
  stretto — non è una curva pulita.
- Nessun artefatto NaN: NRMSE e min_gap finiti a nfrac=2 (parametri finiti); rilevatore collisione provato nei due
  sensi (scatta sui 3 inevitabili, min_gap 0.25 m mostra che sfiora senza toccare sugli evitabili).

## 5. Risultati — severità sulle inevitabili (`qz_cl_severity`)
Sulle 3 collisioni inevitabili, `impact_dv` = velocità relativa al contatto [m/s] (più alto = crash più duro):

| traiettoria | oracolo | n13 | n8 | n4 | n2 |
|---|---|---|---|---|---|
| aggressive #9 | 5.39 | 6.32 | 6.32 | 6.32 | 5.38 |
| aggressive #18 | 4.87 | 4.88 | 4.89 | 4.88 | 4.85 |
| aggressive #27 | 7.69 | 7.63 | 7.63 | 7.61 | 7.65 |
| **max** | **7.69** | 7.63 | 7.63 | 7.61 | **7.65** |

**La quantizzazione non aumenta la severità.** L'impatto massimo è **piatto a ~7.6 m/s da nfrac=13 a nfrac=2**
(delta vs oracolo −0.03…−0.08 m/s). Dove la collisione è comunque inevitabile, la rete a 2 bit sbatte né più né
meno di quella a 13 bit o dell'oracolo.

## 6. Interpretazione — il capovolgimento
L'accuratezza **open-loop worst-case** (§3, max|d|) dice *sensibile*: il parametro peggiore degrada già a nfrac
medi. Ma l'**anello chiuso** (§4-5) dice *robusta*: zero collisioni extra, severità e margini invariati, fino a 2
bit. Il motivo è che la rete è **probabilistica** e l'anello è **tollerante**: sotto quantizzazione i parametri si
**riorganizzano** (NRMSE 0.33 a 2 bit) ma la legge IIDM + la retroazione **assorbono** il drift e preservano il
car-following. Ipotesi degli **"equilibri interni"** — confermata **rigorosamente**: non su un caso singolo né su
un anello che maschera le collisioni, ma su 99 scenari duri con cut-in reali, anello provato fedele, e baseline
oracolo che separa il costo-quantizzazione da ciò che è fisicamente inevitabile.

## 7. Risultati — hardware (risorse/potenza/Fmax vs nfrac)
Config di riferimento **FAST-like** (forward corrente + splitpipe + decode p5), vincolo **deploy 125 ns io-timed**,
**stesso protocollo per tutti i livelli** (confronto valido). Sintesi OOC Vivado 2026.1, `xc7z020clg400-1`. Dati:
`res_sweep.tsv`; figura `figures/quantization_curves.png`. Estratto:

| nfrac | LUT | FF | DSP | Ptot_W | dLUT% (vs 13) | NRMSE param |
|---|---|---|---|---|---|---|
| 2 | 2832 | 1713 | 30 | 0.109 | **−38.8** | 0.327 |
| 4 | 4856 | 2381 | 31 | 0.111 | **+4.9** (picco) | 0.109 |
| 5 | 3664 | 2497 | 51 | 0.112 | −20.8 | 0.097 |
| 8 | 4043 | 2864 | 51 | 0.113 | −12.6 | 0.089 |
| 13 | 4628 | 3474 | 52 | 0.111 | 0.0 | 0.000 |

Il risparmio d'area **non è monotòno** — è dominato dal confine di inferenza **DSP↔LUT**:
- **FF**: pulito, monotòno (~+120/bit) → **−51%** da 13 a 2 bit. La metrica di risparmio affidabile.
- **DSP**: **gradino a nfrac=5→4** (51 → 31 → 30): sotto 5 bit ~20 moltiplicatori escono dai DSP.
- **LUT**: monotòno 13→5 (−21%), poi **picco a n4** (+4.9%, i mult usciti dai DSP diventano logica LUT), poi giù a
  n2-3. → **n4 è dominato da n5** (n5: meno LUT, params ugualmente fedeli, stessi DSP; n4 conviene solo se
  DSP-limitato).
- **Potenza**: **piatta** (−1.8% a n2), **static-dominata** (0.103 W statica su ~0.11 tot). La quantizzazione **non
  salva potenza** su Zynq-7020 → conferma la nota clock-gating: il vantaggio si materializza su chip
  dynamic-dominati (dove la rete idle >99.9% dà il taglio senza costo).
- **Fmax**: rumore ~52-60 MHz al vincolo lasco (WNS +105-108) → **margine**, non proprietà del design (tutti
  ~10⁴× il control-step). Vedi impl_point.tcl §validità.

**Task 6 (config canonica / Fmax massimo via bisezione): NON eseguito, con motivo.** Fmax è margine (tutti
~55 MHz vs requisito ~4 kHz); massimizzarlo per livello aggiungerebbe decine di sintesi per un numero senza valore
operativo (coerente con l'onestà §9 della spec: la config canonica è "caratterizzazione del limite").

## 8. Ginocchio e menu quantizzazione (integrato: fedeltà × hardware)
- **Sicurezza**: invariante fino a nfrac=2 (0 collisioni extra) → floor.
- **Fedeltà parametri** (NRMSE): ginocchio ~nfrac=4-5; sopra piatta (~0.09), sotto raddoppia (0.20@n3, 0.33@n2).
- **Hardware**: FF −51% a n2, DSP a gradino sotto n5, LUT non-monotona (tradeoff), potenza piatta.

**Il collo NON è l'hardware, è la fedeltà dei parametri.** Il risparmio d'area è modesto e la potenza è piatta;
la scelta di bit la detta l'NRMSE. Menu proposto:

| livello | uso | NRMSE | risparmio (vs n13) |
|---|---|---|---|
| **n8** | conservativo | 0.089 | −13% LUT, −18% FF, DSP pieno |
| **n5** | sweet spot | 0.097 | **−21% LUT, −28% FF**, DSP pieno |
| **n2** | aggressivo / safety-only | 0.327 (ma 0 collisioni) | −39% LUT, **−51% FF**, DSP 30 |

## 9. Limiti
- **Config FAST-like** (non BAL, il prescelto): risorse/potenza/**ginocchio** sono tier-robusti (la quantizzazione
  tocca la logica del core, identica tra i tier); solo l'**Fmax assoluto** è quello di FAST. Per l'Fmax canonico di
  BAL, ri-girare Task 6 sulla config BAL (economico, harness pronto).
- **`max_DRAC`** troppo spiky per una curva; usare min_gap/brake_margin/coll_extra come SSM pulite.
- **Ingressi non quantizzati** nell'anello (come `simulate`): si varia il **solo** `nfrac` del core; la
  quantizzazione V2X 20 bit degli ingressi è un asse separato, fuori scope.
- **Per-campo mixed-precision** (frazionari indipendenti per V/fatigue/acc/raw/w): future work (spec §8).

## 10. Riproducibilità
```
gen_exhaustive_qz_dataset.py   (cf_sim python) -> exhaustive_scenarios.json   [build_scenarios canonico]
qz_build_exhaustive_dataset.m                  -> test_dataset_exhaustive.mat
gen_oracle_parity_ref.py       (cf_sim python) -> oracle_parity_ref.json
qz_cl_parity_gate.m            -> cancello parità (max|Δs| ~2e-6 m)
qz_cl_selftest.m               -> collisione nei due sensi + teletrasporto
qz_cl_validate.m               -> cl_sweep.tsv   (sweep nfrac 2-13, SSM + NRMSE)
qz_cl_severity.m               -> impact_dv sulle inevitabili
qz_run_fixed_sweep.m           -> acc_sweep.tsv  (accuratezza open-loop max|d|)
qz_gen_block_vhdl.m            -> VHDL Donatello a nfrac variabile (core+normalize; decode En13; gate bit-exact @13)
qz_sweep_nfrac.sh              -> res_sweep.tsv  (risorse/potenza/Fmax vs nfrac, sintesi OOC io-timed)
qz_knee.m                      -> tavola incrociata + menu livelli
qz_figs.py                     (python base, matplotlib) -> figures/quantization_curves.png
```
Anello: `qz_cl_sim.m` (+ `qz_safety_metrics.m`). Motore canonico di riferimento:
`<worktree Simulator>/utils/closed_loop_eval.py`. Harness sintesi: `study_tradeoff/common/{synth,impl}_point.tcl`.

## 11. Menu nel blocco (implementato)
Il blocco `Donatello_Tier` (`snn_champions_lib.slx`) ha ora un **2° popup NFRAC** (13/8/5/2, i livelli canonici)
ortogonale al popup TIER → **3 tier × 4 nfrac = 12 varianti** Variant Subsystem, ognuna col nfrac **cotto
concreto** nella chart SNN (decode fisso En13). Builder: `build_tier_configurable.m`. Gate:
`qz_tier_nfrac_gate.m` (default BALANCED/n13 **bit-exact** al riferimento storico; 12 varianti compilano;
quantizzazione morde: max|Δparam| vs n13 = 0.68@n8 / 1.16@n5 / 2.07@n2; makehdl@n8 → VHDL valido).
⚠️ **Muro Simulink (registrato)**: un `nfrac` come **mask-parameter vivo** (word-length parametrico) funziona
in una MATLAB Function co-locata ma **NON aggancia attraverso il Variant Subsystem** (la Parameter data
annidata non risolve il parametro mask del blocco top, anche con `Tunable=false`; verificato in
`probe_nfrac_mask`). Le **varianti discrete** aggirano il problema (tipi concreti, robusti).

## 12. Mixed-precision per-campo (nfrac indipendenti)

Estensione: **6 nfrac indipendenti** per i tipi del core `[V fatigue acc accw raw w]` invece di un unico
nfrac, misurati con **gli stessi criteri dello studio uniforme**: **sicurezza** (0 collisioni extra vs
oracolo, §4) + **fedeltà** NRMSE (§5). ⚠️ Il cancello `max|Δgap|≤0.5 m` (`qz_mp_gate` `THR`) è solo una soglia
strumentale: dà **gli stessi floor** del criterio "bit-identico" (NRMSE=0), perché i campi sensibili rompono
già al primo bit (0.9 m **e** NRMSE≠0 a 12) e acc/w sono a 0 fino a 4. **NON è un vincolo di sicurezza** (quello
è 0 collisioni extra, qui soddisfatto **ovunque**).

- **Sicurezza**: `coll_extra=0` su TUTTE le 78 config (anche a 1 bit, 40 m di Δgap) → **ogni campo scende fino
  a 1 bit** senza collisioni extra, coerente con "sicuro fino a n2" dell'uniforme. La sicurezza non è il limite.
- **Fedeltà (ciò che distingue i campi)**: **floor senza perdita** = nfrac minimo con uscita bit-identica (NRMSE=0).

**Floor senza perdita per campo** (`mp_sens.tsv`, 78 config; sicurezza a 1 bit per tutti):

| Campo | Floor | | Campo | Floor |
|---|---|---|---|---|
| V | **13** | | accw | **13** |
| fatigue | **13** | | raw | **13** |
| acc | **4** | | w | **4** |

**Asimmetria + meccanismo VERIFICATO**: solo `acc`/`w` riducibili (a 4 bit, bit-identici 13→4). La sonda
pesi conferma: **tutte** le matrici (fc/rec_U/rec_V/readout) sono **po2 con minimo 2⁻⁴** → 4 bit frazionari
bastano esatti; a 3 il peso 2⁻⁴ sparisce. `acc` (accumulo pesi-po2×spike interi) vive sulla griglia 2⁻⁴.
`V/fatigue/accw/raw` portano grandezze continue (soglia/decode non-po2) → servono pieni sotto 0.5 m.

**Config area-ottimale** = `[13 13 4 13 13 4]` (`mp_finalists.tsv`, verifica CONGIUNTA): `max|Δgap|=0`,
**bit-identica** al full-precision. L'**uniforme non scende sotto 13** (a 12 rompono 4 campi) → la
precisione mista taglia acc/w dove l'uniforme non può.

**Hardware** (`mp_res.tsv`, 3 config @125 ns io-timed su Zynq-7020; **VHDL mp@[13×6] provato bit-exact** al
gen unico@13, diff solo contatore segnali):

| Config | LUT | FF | DSP | slack WNS (ns) | Pdyn (mW) |
|---|---|---|---|---|---|
| full `[13×6]` | 4628 | 3474 | 52 | 106 | 8 |
| finale `[13,13,4,13,13,4]` | 5203 | 3045 | 36 | 106 | 10 |
| uniform `[4×6]` (fuori cancello) | 4856 | 2381 | 31 | 106 | 8 |

**Onesto**: il taglio è comportamentalmente gratis ma in HW **non è un risparmio pulito** — DSP −31% e
FF −12%, ma **LUT +12%** (confine DSP↔LUT: moltiplicatori stretti → celle) e **potenza piatta** (dinamica
8→10 mW, sale per le celle; a pochi mW è entro risoluzione). Slack ~106 ns (Fmax non è il collo). Valore =
**diagnostico**; conferma indipendente del §6 (il collo dei bit è la fedeltà, non l'hardware).

**Modalità Avanzata nel blocco** (`build_tier_configurable(nf)`): checkbox ADV + 6 slider (1..13) nella
mask; ADV attiva 3 varianti `<tier>_ADV` **cotte concrete** a `nf` (tipi `qz_snn_types_mp` per-campo);
callback `tier_adv_cb` = **solo visibilità** (sicuro su link). La config ADV si imposta ri-eseguendo il
builder (il **B live è impossibile su blocco linkato** — la chart di un link vive nella libreria, non
modificabile per-istanza; sonda `probe_adv`. Approccio A robusto adottato).

**File**: `qz_snn_types_mp.m` `qz_snn_cl_step_mp.m` `qz_mp_gate.m` `qz_mp_sensitivity.m` `qz_mp_combine.m`
`qz_gen_block_vhdl_mp.m` `qz_mp_synth.sh` `qz_mp_advanced_gate.m` `tier_adv_cb.m`. Gate: `qz_mp_selftest0`
(forward bit-exact @full-precision), `qz_mp_gate_selftest` (detector nei due sensi: accetta @13, rifiuta @2),
`qz_mp_advanced_gate` (5 gate: Base no-regressione · struttura · ADV≡Base · ADV discrimina · HDL da ADV).
Dati: `mp_sens.tsv` `mp_finalists.tsv` `mp_res.tsv`. Report: sezione §8 di `QUANTIZATION_STUDY_REPORT`.
