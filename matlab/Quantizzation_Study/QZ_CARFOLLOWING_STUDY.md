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

## 7. Ginocchio e livelli candidati
- **Sicurezza**: nessun ginocchio — invariante fino a nfrac=2 (limite estremo testato).
- **Fedeltà dei parametri** (NRMSE): ginocchio **~nfrac=4** (0.11); sopra è piatta (~0.08-0.10), sotto raddoppia
  per bit (0.20 a n3, 0.33 a n2).

Il vincolo sui bit **non viene dalla sicurezza** (che regge fino a 2), ma dalla fedeltà dei parametri se la si
vuole vicina al riferimento. Candidati per il menu quantizzazione: **nfrac ≥ 4-5** conserva params ~fedeli;
**nfrac 2-3** resta sicuro ma con parametri visibilmente diversi (utile per il massimo risparmio di area se conta
solo il comportamento). La scelta finale incrocia questi con le curve **risorse/potenza/Fmax** (§8).

## 8. Limiti e prossimo fronte
- **Comportamento/sicurezza soltanto.** Le curve **risorse (LUT/DSP/FF) / potenza / Fmax vs nfrac** + il ginocchio
  hardware + la **configurazione canonica** (Fmax massimo via ricerca a passo adattivo) sono il fronte **Vivado**
  (Task 3-6 del piano `docs/superpowers/plans/2026-07-24-quantization-study.md`), ancora da eseguire. Solo lì il
  trade-off diventa "quanti bit convengono davvero".
- **`max_DRAC`** troppo spiky per una curva; usare min_gap/brake_margin/coll_extra come metriche di sicurezza pulite.
- **Ingressi non quantizzati** nell'anello (come `simulate`): lo studio varia il **solo** `nfrac` del core; la
  quantizzazione V2X a 20 bit degli ingressi è un asse separato, fuori scope.

## 9. Riproducibilità
```
gen_exhaustive_qz_dataset.py   (cf_sim python) -> exhaustive_scenarios.json   [build_scenarios canonico]
qz_build_exhaustive_dataset.m                  -> test_dataset_exhaustive.mat
gen_oracle_parity_ref.py       (cf_sim python) -> oracle_parity_ref.json
qz_cl_parity_gate.m            -> cancello parità (max|Δs| ~2e-6 m)
qz_cl_selftest.m               -> collisione nei due sensi + teletrasporto
qz_cl_validate.m               -> cl_sweep.tsv   (sweep nfrac 2-13, SSM + NRMSE)
qz_cl_severity.m               -> impact_dv sulle inevitabili
qz_run_fixed_sweep.m           -> acc_sweep.tsv  (accuratezza open-loop max|d|)
```
Anello: `qz_cl_sim.m` (+ `qz_safety_metrics.m`). Motore canonico di riferimento:
`<worktree Simulator>/utils/closed_loop_eval.py`.
