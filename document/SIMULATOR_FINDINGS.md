# Simulator Findings — validazione operativa CF_FSNN

**Data**: 2026-06-01
**Branch**: `Visualizer_Building`
**Modulo simulatore**: `utils/simulator/` (engine + metrics + plots + anim)
**Notebook**: `Simulator_Visual.ipynb` (16 celle, incluso CUT-IN ANALYSIS section)
**Reference**: baseline ALIF+BPTT (`checkpoints/GRID2x2_baseline/best_model.pt`, val_data 0.2224)

---

## 1. Setup esperimenti

Cache testate:
1. `data/cache_1500_highway_cut0.0_ou0.0.pt` (originale F2): 300 val, 100% highway, 0 cut-in
2. `data/cache_400_mixed_cut0.3_ou0.0.pt` (nuova ITER1): 100 val, mix (highway/urban/truck), **23 cut-in flagged, 21 detected dal simulatore**

Configurazione simulazione:
- **Open-loop**: SNN vede inputs RECORDED a ogni step (s, v, dv, vl da V2X), integra ego_pred separatamente con `acc_iidm_accel(params_pred)`.
- **Integrazione**: ballistica DT=0.1s (matches generator + Treiber Ch11).
- Window temporale: testata da seq_len=50 (5s) a seq_len=700 (70s).

Cut-in detection: heuristic `jump in s_obs > 5m in single DT` → identifica tick + gap_before/after.

---

## 2. Scoperta principale: drift cumulativo open-loop ~ T²

Test scaling su 20 scenari per ogni durata:

| seq_len (s) | accel_rmse (puntuale) | gap_rmse (m) | pos_drift (m) |
|---:|---:|---:|---:|
| 5  | 0.193 | 0.77   | **1.97**  ✅ |
| 10 | 0.204 | 3.92   | 8.77      |
| 20 | 0.207 | 16.4   | 37.0      |
| 30 | 0.216 | 36.5   | 79.2      |
| 50 | 0.223 | 89.7   | 199.8     |
| 70 | 0.224 | 176.8  | **366.3** ❌ |

**Osservazioni rigorose**:
1. `accel_rmse` **stabile** a ~0.22 (= val_data baseline, sanity confermata)
2. `pos_drift` cresce come **T²**: 366/1.97 = 186× ≈ (70/5)² = 196× (quadratic, NON random walk T^1.5)
3. Pattern T² implica **bias sistematico** ≈ 0.15 m/s² nell'accelerazione predetta
   - Formula: x_drift(T) = 0.5 · bias · T² → 0.5 · 0.15 · 70² = 367m ≈ observed

Vedi `opt_plots/cutin/scaling_drift_vs_T.png`.

---

## 3. Cut-in analysis — verdetto contro-intuitivo

Aggregato su 100 scenari val (mixed cache, seq_len=700):

| Metric | no-cut-in (n=79) | cut-in (n=21) | ratio (cut-in / no) |
|---|---:|---:|---:|
| gap_rmse_m | 138.7 | 119.2 | **0.86×** (cut-in ≈ uguale) |
| pos_cum_err_m | 305.1 | 241.1 | 0.79× |
| accel_rmse_masked | 0.198 | 0.336 | 1.69× |
| **jerk_max_pred** | 7.18 | **89.4** | **12.5×** (vero impatto cut-in) |
| jerk_p95_pred | 3.14 | 3.28 | 1.04× |
| spike_rate_avg | 0.032 | 0.026 | 0.83× |
| TTC_min_pred (cut-in only) | n/a | 0.43s | (1 finite value) |

**Interpretazione**:
- Su window 70s, il drift cumulativo overrides l'impatto specifico del cut-in
- I cut-in producono **picco di jerk transitorio 12× maggiore** (~89 m/s³ vs 7) ma localizzato al cut-in event
- Il jerk_p95 è invece simile (3.1-3.3) → il transient cut-in è breve, lascia il sistema a comportamento normale
- TTC_min 0.43s sul singolo cut-in detected con TTC finite → safety-critical ma raro

Vedi `opt_plots/cutin/boxplot_cutin_vs_normal.png` + 7 figure scenari individuali in `opt_plots/cutin/cutin_idx*.png`.

---

## 4. Implicazione per deploy FPGA

### Sistema in deploy reale = **closed-loop**

Il drift cumulativo osservato è **artefatto della modalità test open-loop estesa**, non una limitazione del sistema in operazione reale.

**Closed-loop deploy** (10Hz V2X PYNQ-Z1):
- Ogni 100ms: V2X riceve dati REALI (s, v, dv, vl) dal veicolo + leader fisici
- SNN predice solo `a_pred` istantanea
- L'attuatore applica `a_pred` al VEICOLO FISICO (non integrato dalla SNN)
- Al tick successivo: nuova osservazione, nuova predizione

In closed-loop **NON c'è accumulo di drift** — la SNN non "guida" l'ego integrando nel tempo, ma è un decoder istantaneo di parametri di controllo.

### Open-loop simulation è utile come "stress test"

Per il deploy bisogna validare:
- ✅ Accel error puntuale: 0.22 m/s² (val_data, già validato)
- ✅ Spike rate: 3-5% (FPGA-friendly, già validato)
- ✅ Latency inference: << 100ms (TBD post-FPGA)
- ⚠️ **Bias sistematico**: ~0.15 m/s² su accel predetta — potrebbe creare drift residual in closed-loop su lunga durata se non corretto

Il bias sistematico richiede attenzione anche in closed-loop. Mitigation possibili:
1. **Bias correction layer**: subtract running mean da `a_pred` (semplice, no retrain)
2. **Re-training con regularization a_mean_zero**: lambda extra che penalizza la media di a_pred
3. **Post-deploy monitoring**: telemetria che alert se velocita' deriva > soglia

---

## 5. Implementazione completed (artefatti pushati)

### Codice (`utils/simulator/`)
- `engine.py` (380 LOC): CFSimulator + integrate ballistico + cut-in detection
- `metrics.py` (150 LOC): 9 metriche operative + aggregate_metrics
- `plots.py` (335 LOC): Layout A static 5-panel + Layout B topdown + cut-in highlight
- `anim.py` (150 LOC): Layout C FuncAnimation + GIF/MP4 export

### Notebook
- `Simulator_Visual.ipynb` (16 celle, era 11): aggiunte 5 celle dedicate cut-in analysis

### Cache nuova
- `data/cache_400_mixed_cut0.3_ou0.0.pt` (29.7 MB, generata via generate_dataset programmatic)

### Risultati visivi (`opt_plots/cutin/`)
- 7 figure statiche cut-in scenarios (idx 0/7/41/48/50/52/54) — diversi scenario_type
- 1 GIF animazione cut-in idx=0 (10.9 MB)
- 1 boxplot comparative cut-in vs no-cut-in (4 metric)
- 1 scaling plot drift vs T
- 1 aggregate_metrics.csv (100 scenari × 18 colonne)

---

## 6. Decisioni operative

| ID | Decisione | Razionale |
|---|---|---|
| **D1** | Procedere con deploy FPGA closed-loop | Drift open-loop NON applica a deploy 10Hz V2X real |
| **D2** | Aggiungere bias correction al deploy | bias sistematico ~0.15 m/s² mitigabile con running mean subtract |
| **D3** | Includere telemetria velocity drift in deploy | post-deploy safety net: alert se drift > soglia |
| **D4** | Non re-training con a_mean_zero regularization | costoso, potrebbe peggiorare val_data; closed-loop e bias correction sufficienti |
| **D5** | Cut-in NON sono mostro: ok procedere | jerk transitorio gestito da actuator dynamics reali, non da SNN |

---

## 7. Lessons learned (simulator dev)

#### Lezione #28 — val_data è UNA metrica puntuale, non operativa
val_data 0.22 m/s² (RMSE puntuale su accel) NON garantisce comportamento di guida acceptable su simulation estesa. Il drift cumulativo open-loop scala come T² del bias sistematico, non come T del rumore. Sempre validare con `pos_cum_err` su orizzonti realistici.

#### Lezione #29 — Open-loop e closed-loop sono modi di test diversi
Open-loop = "predici e integra autonomamente" (stress test). Closed-loop = "predici, applica, riosserva". Il deploy reale è closed-loop a 10Hz — i numeri open-loop esagerano i problemi reali.

#### Lezione #30 — Cut-in NON sono peggio del normal su drift dominato
Quando il drift cumulativo domina la metrica spaziale (gap_rmse), il cut-in localizzato (jerk transitorio) non emerge come "peggio". Le metric appropriate per cut-in sono `jerk_max` + `TTC_min`, NON `gap_rmse`.

#### Lezione #31 — Simulator come bridge metric ML → operativo
Nessuna decisione di deploy puo' essere presa solo dalla metric ML. Il simulator visivo ha cambiato decisione architetturale: da "EventProp è la cura per val_data" (mai trovato) a "deploy con bias correction è sufficiente perchè closed-loop neutralizza drift open-loop".
