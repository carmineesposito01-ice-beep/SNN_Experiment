# LOSS_STUDY & EVALUATION — record completo (2026-06-19)

> **⚠️ MILESTONE CHIUSA**: `Loss_Study` è stato **merge in `main`** (2026-06-20). Il lavoro continua
> nel branch **`Dynamic_Study`** sul tetto dei parametri dinamici a/b. Per lo stato attuale parti da
> `document/SESSION_RESUME.md` → poi `DYNAMIC_STUDY_PLAN.md` e `DYNAMIC_STUDY_B_RESULTS.md`. Questo
> documento resta il record storico di Loss_Study.

> **Scopo**: documento auto-sufficiente per riprendere il lavoro da una chat nuova.
> Copre tutto il branch `Loss_Study`: lo studio di identificabilità (S1→S3), la digressione
> capacità (S2), i fix al training, e l'intero framework di **evaluation closed-loop**
> (micro/meso/macro + vetrina neuromorfica). Per la storia pre-Loss_Study vedi
> `PRODIGY_STUDY_CLOSURE.md`. Per i dettagli: `S2_CAPACITY_DIGRESSION.md`,
> `S3_CONSOLIDATION_AND_FUTURE_B.md`.

---

## 0. TL;DR (dove siamo)

- **Branch**: `Loss_Study` (da `main` tag `R33_closure`). Tutto il lavoro sotto è qui.
- **Domanda di partenza**: la rete SNN deve stimare i **5 parametri ACC-IDM** `[v0, T, s0, a, b]`
  da segnali osservati; in S1 abbiamo scoperto che **non sono congiuntamente identificabili**
  dall'accelerazione (manifold molle v0↔a). Per la **safety** servono tutti e 5 corretti.
- **Leva trovata**: **osservabilità** (dati che eccitano i parametri), non la capacità.
  Freeflow → sblocca v0; launch (accel forti ripetute) → sblocca parzialmente `a`.
- **Capacità**: digressione **SOSPESA** (non esaustiva), i modelli grandi esplodono in BPTT.
- **Validazione**: costruito un framework completo **micro + meso + macro + vetrina** che gira
  in un solo notebook (`Loss_Study_Validation_Full.ipynb`, ~6-9 min) → `results/evaluate/<analisi>/`.
- **Esito micro (v1, cut-in realistico — FATTO)**: la SNN guida con **0 collisioni su TUTTI gli
  scenari** (100 sim/sorgente), come/meglio dell'oracolo (più dolce, più string-stable). Il 4%
  iniziale era SOLO l'artefatto del cut-in fisicamente inevitabile. **Validazione superata.**
- **Prossimo**: S4 (bias a/b lato training) — l'unico problema residuo (vedi §7).

---

## 1. Modello di base (invariato)

- `CF_FSNN_Net` (core/network.py), **864 parametri**, h=32, rank=8, max_delay=6, bit_shift=3.
- ALIF hidden (4→32, low-rank recurrent U@V) + LI output (32→5). Po2 quantization. n_ticks=10.
- Output: 5 parametri IDM decodificati `[v0, T, s0, a, b]` (sigmoid + bound + per-channel τ).
- Loss PINN (`train.py:pinn_loss`): `loss_data` = **RMSE mascherato su accelerazione** `a_pred`
  (da `CF_FSNN_Net.acc_iidm_accel`, ACC-IDM con base IIDM + CAH, coolness 0.99) vs GT.
  `loss_data` NON è decomponibile per-parametro: i 5 entrano TUTTI nell'equazione fisica.
- Dataset **sintetico** (data/generator.py) → la GT dei parametri è SEMPRE nota (utile per NRMSE).

---

## 2. STUDIO IDENTIFICABILITÀ (S1) — quale parametro pesa e perché

Notebook: `Loss_Study_S1.ipynb`. Triangolazione a 3 lenti su PEAK(864p) + STABLE(232p):
- **Lente A — gradiente**: `gn_decoded_<p>` (già loggato, plot G16/G17). Ranking **T > a > b > s0 > v0**,
  identico sulle 2 architetture. v0 ~2 ordini sotto (loss quasi cieca a v0).
- **Lente B — residuo**: `val_<p>_nrmse` (RMSE pred/GT ÷ range). **AGGIUNTO a train.py** (val_epoch).
  Risultato sorprendente: A e B **anti-correlate**. T = gradiente alto MA ben imparato (NRMSE 0.13);
  v0 = gradiente basso E peggiore (NRMSE 0.50, **pred saturato a ~41 vs vero 33**); `a` = gradiente
  alto MA mal imparato (NRMSE 0.36, collassato).
- **Lente C — ablation**: supervisione ausiliaria per-canale (λ_aux=0.1, flag `--lambda_*_aux`).

**Scoperta chiave (provata causalmente)**: v0 e `a` sono una **coppia molle** (sloppy manifold).
- Forzo v0↓ (R2) → `a` sale; forzo `a`↑ (R4) → v0 scende; `corr(v0,a)=−0.82` lungo il training.
- Meccanica: la rete spara v0 altissimo (free-term IDM ≈ costante) e collassa `a` per compensare,
  fittando l'accelerazione con parametri "fasulli". L'accelerazione da sola **non determina i 5**.
- Plot **G19** (NRMSE per-canale) aggiunto a `plot_all` (su ogni run).

---

## 3. OSSERVABILITÀ (la soluzione) — S1b (freeflow) + S3 (launch)

Principio: l'**osservabilità** (dati che eccitano i parametri) è la leva fondamentale;
l'**aux** è solo strumento/diagnostica (non crea informazione; va validato sul val).

### S1b — scenario `freeflow` (`Loss_Study_S1b.ipynb` / cache freeflow)
- Aggiunto scenario **freeflow** (profilo leader `free`: accel libera fino a v0) in data/generator.py.
- Risultato: **dato da solo NON risolve**. v0 migliora (NRMSE 0.50→0.39) ma `a` resta collassato,
  T/s0/b peggiorano. Media NRMSE 0.28→0.35 (più uniforme). Il manifold si **ridistribuisce**.
- Check gradiente: freeflow ha **triplicato** il gradiente di v0 ma lasciato `a` **invariato (1.02×)**.
  Motivo fisico: v0 si vede nella **crociera** (71% del freeflow); `a` solo nel **transitorio di accel** (breve).

### S3 — scenario `launch` (`Loss_Study_S3.ipynb`)
- Aggiunto scenario **launch** (profilo `launch`: cicli di accelerazione forte RIPETUTA) → l'ego passa
  il **63% del tempo a |a|>1** (vs freeflow 12%). Mix usato: `highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35`.
- Risultato: **successo parziale**. Gradiente `a` 1.23×; `a_pred` 0.43→**0.65** (verso vero 1.1);
  `a_nrmse` 0.34→**0.26**, **niente ricollasso**. Run più **bilanciata** (media NRMSE 0.265, v0 0.50→0.20).
  `a` ancora ~40% basso (finestra di osservazione intrinsecamente stretta in IIDM).
- **Fix restart** (osservazione utente): i bump di val_data coincidevano coi restart (lr→0.5 ogni 12 ep,
  **Opzione 0** `restart_decay=1.0`). Passato a **Opzione 1+4** (`restart_decay=0.3` + warmup 2 = setting
  champion CLEAN) → restart progressivamente gentili (0.5, 0.15, 0.045…). Run consolidata:
  **`LS3_PEAK_R0_launch_d03`** (il checkpoint usato per la validazione).
- **Bias a/b sistematico** (da analisi): `a_pred 0.65` (sotto, vero 1.1), `b_pred 1.79` (sopra, vero 1.5).
  Sovrastimare `b` → la rete "crede" di frenare più comodo → margini sottili in frenata. → **S4 futuro**
  (lato training: pesare il residuo PINN sulla decelerazione / penalizzare il bias su b).

---

## 4. DIGRESSIONE CAPACITÀ (S2) — SOSPESA (vedi `S2_CAPACITY_DIGRESSION.md`)

- Teoria: NRMSE che bilancia → forse capacità il limite. Sweep x1/2/4/8/10 su freeflow.
- **INVALIDO**: i modelli grandi **esplodono** (BPTT, gn 1e19/inf), val_data peggiora monotona.
- Ipotesi lr/Prodigy-d **FALSIFICATA** (d stabile, lr_eff in calo). Causa: **instabilità intrinseca del
  ricorrente grande** (raggio spettrale).
- **Fix guard** (in train.py):
  - **v1**: epoca esplosa se **frazione** di batch con gn>soglia > `--epoch_explosion_frac` (def 0.5),
    non più un singolo spike isolato (`max_gn`).
  - **v2**: i batch **inf/nan contano come esplosi** (prima x8/x10 giravano 50ep su inf non contati).
- **Ricerca optimizer**: LAMB (= AdamW + trust ratio ‖w‖/‖update‖; sostituirebbe Prodigy) vs **AGC**
  (Adaptive Gradient Clipping, Brock 2021: clip per-unità del gradiente ∝ ‖w‖, **optimizer-agnostico
  → mantiene Prodigy**). Implementato **AGC**: `--grad_clip agc --agc_lambda 0.01` (default off,
  esclude `layer_out` + param 1-D).
- **Test AGC su x10**: λ0.01 = 8 epoche pulite poi esplode (guard v2 lo cattura); λ0.005 PEGGIO.
  AGC (clip per-step) **ritarda ma non cura** l'instabilità di spazio-pesi.
- **Conclusione**: capacità SOSPESA, **non esaustiva**. Strade future: **LAMB**, **vincolo raggio
  spettrale** sul ricorrente U@V, **multi-seed**. Infrastruttura guadagnata e riusabile: guard v2, AGC, G19.

---

## 5. INVENTARIO MODIFICHE AL CODICE (training)

| File | Modifica |
|---|---|
| `train.py` | `val_*_nrmse` per-canale in `val_epoch` (Lente B); guard v2 (frazione + inf, `--epoch_explosion_frac`); **AGC** (`adaptive_grad_clip` + `--grad_clip`/`--agc_lambda`). Flag aux già esistenti (`--lambda_*_aux`). |
| `data/generator.py` | scenari **freeflow** (profilo `free`) e **launch** (profilo `launch`), additivi; `valid_scenarios` esteso; default `SCENARIO_MIX` invariato. |
| `utils/plot_diagnostics.py` | **G19** (NRMSE per-canale) + **G20** (follow x(t) ego/leader) in `plot_all` → ogni run. |
| `core/network.py` | invariato (referenziato `acc_iidm_accel`, ordine 5-tuple `[v0,T,s0,a,b]`, F5 decode_scale). |

> Tutte le modifiche sono **additive e retro-compatibili** (default = comportamento precedente).

---

## 6. FRAMEWORK DI EVALUATION (la validazione del progetto)

Obiettivo: la SNN, usata come stimatore dei parametri che guidano l'ego via ACC-IDM, guida in modo
**sicuro** e produce comportamento di traffico **corretto**? 4 livelli, un solo notebook.

### Notebook unico: `Loss_Study_Validation_Full.ipynb` (~6-9 min, no training)
Carica il checkpoint **una volta** → esegue micro → meso → macro → vetrina →
`results/evaluate/<ANALYSIS>/{Eval_ClosedLoop, Meso, Macro, Showcase}`. Push unico finale.
Variabile `ANALYSIS` nella prima cella (default `v1_realistic_cutin`). Robusto al checkpoint assente.
Build-script: `scripts/_build_validation_full_notebook.py` (importa le celle dai build-script eval/showcase/mesomacro
e rimappa `RESULTS_DIR`→`EVAL_DIR/MESO_DIR/MACRO_DIR/SHOW_DIR`). Esistono anche i notebook singoli
(`Loss_Study_Eval_ClosedLoop.ipynb`, `Loss_Study_Showcase.ipynb`, `Loss_Study_MesoMacro.ipynb`).

### MICRO — sicurezza closed-loop (`utils/closed_loop_eval.py`)
Ego guidato da ACC-IDM con parametri SNN; leader esegue scenari avversari: **following, stop&go,
hard_brake, cut_in, sinusoidal**. Confronto **SNN vs oracolo** (parametri veri). N=100 sim/sorgente
(20 driver × 5 scenari).
- **Cut-in corretto** (importante): prima il gap crollava a 4m (DRAC ~8 = inevitabile anche per
  l'oracolo). Ora **TTC~1s / DRAC~4 m/s² = difficile ma EVITABILE** (oracolo 0/30) → discrimina i controller.
- **Metriche**: collision_rate (+ **CI Wilson 95%**), min_gap, min_TTC, min_headway, max_DRAC, TET, TIT;
  comfort (rms_accel, rms_jerk, max_decel); tracking (rms_gap_error); string_gain.
- **Grafici (5)**: G1 traiettorie (gap/v/accel), G2 TTC(t), G3 margini (scatter coda + barre worst-case),
  G4 string-stability + indice smorzamento D (sinusoidale **e stop&go**), **G5 scorecard** (tutte le
  metriche numeriche a barre, con CI su collision rate).

### MESO — plotone / string stability (`utils/platoon_eval.py`)
N veicoli in fila; **CAM cablato**: veicolo *i* osserva *i−1* (davanti) → `(gap, v, dv=v_i−v_{i−1}, v_leader=v_{i−1})`.
Perturbazione sinusoidale in testa. Criterio ACC (Treiber ch16.7, stringa **aperta**).
- **Metriche**: gain per veicolo `|H|_i=A_i/A_leader`, **head-to-tail** (≤1 = stabile), max amplificazione,
  monotonia strict, **convettività a monte**, min gap/TTC nella catena, collisioni, comfort (rms accel/jerk, max decel).
- **Grafici (2)**: `meso_string_stability.png` (gain per veicolo 1-linea/variante + heatmap spazio-tempo velocità),
  `meso_metrics_scorecard.png` (metriche scalari a barre).
- Fisica validata: il plotone IDM **smorza** (gain decrescente, head-to-tail 0.12).

### MACRO — diagramma fondamentale (`utils/platoon_eval.py`)
Veicoli su **anello** (i segue i−1, 0 segue N−1 +L). Densità ρ=N/L; Q, V via Edie. Sweep densità.
- **Metriche**: **diagramma fondamentale Q(ρ)** (capacità annotata ★), V(ρ), capacità Q_max, densità
  critica, v free-flow, densità di jam, soglia di instabilità (stop&go). [NB: rilevatore instabilità grezzo, da affinare].
- **Grafici (3)**: `macro_fundamental_diagram.png` (Q-ρ + V-ρ, SNN vs oracolo, capacità marcata),
  `macro_metrics_scorecard.png` (scalari a barre), `macro_stopandgo.png` (heatmap onde di congestione).
- Fisica validata: Q(ρ) sale→capacità(~1045 veh/h)→scende (forma corretta).

### VETRINA neuromorfica (`utils/snn_showcase.py`)
- **accuracy** scorecard (NRMSE/accuracy per param, pred vs vero) — **media reale ~77%**.
- **raster spike** (neuroni × tempo) sincronizzato allo scenario + spike-rate(t).
- **energia SNN vs ANN**: SynOps×E_AC vs MAC×E_MAC (Horowitz 45nm: E_MAC 4.6pJ, E_AC 0.9pJ), per-inferenza.
  **~4×** più efficiente — NB: il vantaggio viene dal **costo AC<MAC**, NON dalla sparsità (spike rate ~22%,
  ~72% neuroni attivi → non sparso). Po2/FPGA → ancora meglio. Sparsità è una **leva futura**.
- **animazione** auto (GIF) durante uno scenario.
- **dashboard** riassuntivo (include il verdetto di sicurezza letto dall'eval).

**Totale: 15 grafici** — ogni metrica è in un grafico leggibile (i CSV sono solo backup).

---

## 7. RISULTATI EVALUATION (1ª run, cut-in "harsh" — pre-fix)

> Diretta in `results/evaluate/v0_harsh_cutin/`. La run corretta è `v1_realistic_cutin` (da lanciare).

- **Sicurezza**: SNN ≈ **oracolo** (collision rate 4% entrambi). Collisioni **solo nel cut-in** e
  **anche per l'oracolo** (parametri perfetti) → era lo scenario fisicamente inevitabile (corretto in v1).
  In following/hard_brake/stop&go/sinusoidale: **0 collisioni** per tutti.
- **Comfort/stabilità**: SNN più **dolce** (rms_accel 0.76 vs 0.84) e **più string-stable** dell'oracolo
  (string_gain 0.38 vs 0.49). Gap tracking un po' peggiore (atteso da parametri imperfetti).
- **Energia**: ~3.9× vs ANN (vedi nota sparsità sopra).
- **Accuracy**: 77% media.
- **Meso/Macro**: plotone string-stable; diagramma fondamentale corretto (capacità ~1045 veh/h).

---

## 7bis. RISULTATI EVALUATION v1 (cut-in realistico — FATTO, `results/evaluate/v1_realistic_cutin/`)

**MICRO — VALIDAZIONE SUPERATA**:
- **collision_rate = 0.0 per TUTTE le sorgenti e TUTTI gli scenari** (incluso cut_in), N=100/sorgente
  (CI Wilson 95% sup = 0.037). Col cut-in fisicamente evitabile, la SNN non causa incidenti.
- worst_min_TTC ~0.97s, max_DRAC ~4.8 m/s² (frenata ferma ma fattibile, <9). SNN ≈ oracolo.
- Comfort: SNN più **dolce** (rms_accel 0.74 vs oracolo 0.81), più **string-stable** (gain 0.38 vs 0.49);
  gap tracking un po' peggiore (11.4 vs 8.6, atteso da bias parametri).
- **MESO**: tutte string-stable (head-to-tail 0.12-0.17 < 1), convettive a monte, 0 collisioni nel plotone.
- **MACRO**: FD corretto; la SNN ha capacità **più alta** (~1960-2080 vs oracolo 1045 veh/h) perché
  **sovrastima v0** (bias) → free-flow speed più alta. Conferma indiretta del bias parametri.
- **Energia**: ~3.9× vs ANN (spike rate 22%, da AC<MAC non da sparsità — invariato).
- **Accuracy**: ~77%.

**Conclusione**: la SNN è **validata come controller car-following sicuro** (micro 0 collisioni, meso
string-stable, macro traffico valido). Unico problema residuo: il **bias parametri** (v0 alto, a basso,
b alto) che (a) assottiglia i margini in frenata, (b) alza la capacità macro. → **S4** (lato training).

---

## 8. MAPPA FILE (branch Loss_Study)

**Codice**: `train.py`, `data/generator.py`, `utils/plot_diagnostics.py`, `utils/closed_loop_eval.py`,
`utils/snn_showcase.py`, `utils/platoon_eval.py`, `core/network.py`.
**Notebook**: `Loss_Study_S1.ipynb`, `Loss_Study_S1b.ipynb`, `Loss_Study_S2_Capacity.ipynb`,
`Loss_Study_S2b_AGC.ipynb`, `Loss_Study_S3.ipynb`, `Loss_Study_Eval_ClosedLoop.ipynb`,
`Loss_Study_Showcase.ipynb`, `Loss_Study_MesoMacro.ipynb`, **`Loss_Study_Validation_Full.ipynb`** (il principale).
**Build-script**: `scripts/_build_*.py` (uno per notebook; rigenerano i .ipynb).
**Risultati**: `results/Loss_Study/{S1,S2_Capacity,S3}/`, `results/evaluate/{v0_harsh_cutin,v1_realistic_cutin}/`.
**Doc**: questo file, `S2_CAPACITY_DIGRESSION.md`, `S3_CONSOLIDATION_AND_FUTURE_B.md`, `PRODIGY_STUDY_CLOSURE.md`.

---

## 9. PROSSIMI PASSI (priorità)

1. **Lanciare `Loss_Study_Validation_Full.ipynb`** (`ANALYSIS='v1_realistic_cutin'`) → verdetto micro
   corretto col cut-in realistico + meso + macro + vetrina, tutto in `results/evaluate/v1_realistic_cutin/`.
2. **S4 (training)**: bias a/b — pesare il residuo PINN sulla decelerazione / penalizzare il bias su `b`
   (le criticità closed-loop sono in frenata). Studio lato training, dopo l'evaluation.
3. **Capacità (sospesa)**: LAMB (`--optimizer lamb`, da vendorizzare come Lion), vincolo raggio spettrale,
   multi-seed — solo se si rivisita la pista.
4. **Evaluation futura**: alzare N driver (CI più stretti), affinare il rilevatore di instabilità macro.
5. **EventProp** (pre-Loss_Study, in pipeline): rifarlo "come si deve" (verificare misuso come per Prodigy).
6. **Deploy FPGA PYNQ-Z1** dopo la validazione (R33_C2 CLEAN o il modello consolidato).

---

## 10. COME RIPRENDERE DA CHAT NUOVA

1. `git checkout Loss_Study && git pull`.
2. Leggi questo file + `SESSION_RESUME.md` (sezione 2026-06-19).
3. Lo stato attuale: framework di evaluation completo e pushato; in attesa/analisi della run
   `v1_realistic_cutin`. Il checkpoint consolidato è `LS3_PEAK_R0_launch_d03` (solo su Azure).
4. Concetto guida: **osservabilità > capacità/aux** per l'identificabilità; la SNN guida come l'oracolo
   (validazione micro), il problema residuo è il **bias a/b in frenata** (→ S4).
