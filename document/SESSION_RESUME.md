# SESSION_RESUME.md — Quick context for any new Claude session

> **Scopo**: in 5 minuti capire **dove siamo**, **cosa è stato fatto**, **cosa fare adesso**.
> Aggiornare ad ogni milestone (1 sezione "Stato attuale" sempre aggiornata, log storico in coda).

---

## 🎯 Stato attuale (2026-05-28 21:00)

**Repo HEAD**: `ed8debb` — `feat: STEP 2A — fast iteration mode (n_train=500, early_stop_delta=0.005)`

**Progetto**: CF_FSNN — Spiking Neural Network per identificazione parametri car-following ACC-IDM (con base IIDM, Treiber Ch12 Sez.12.4). Target hardware: PYNQ-Z1 FPGA.

**Architettura rete corrente**: 864 parametri totali
- HiddenLayer_ALIF (4→32, rank=8, max_delay=6)
- OutputLayer_LI (32→5) → params IDM `[v0, T, s0, a, b]`

**Diagnosi finale corrente**: **P9 (capacity insufficiency) CONFERMATO MATEMATICAMENTE** dopo `P9_S1_highway_v2`:

| Dataset | Plateau val_loss | Conclusione |
|---------|-------------------|-------------|
| Full-mix (highway+urban+truck+mixed+cut-in) | **0.354** | Task complesso → rete satura |
| Highway-only | **0.277** | Task semplice → -22%, ma satura comunque |

Se Po2 quantization fosse il bottleneck, i 2 plateau sarebbero IDENTICI. Sono DIVERSI → il limite è **task complexity vs capacity**.

**Eurekas utente confermate**:
1. **"Dancing intorno al plateau"**: pattern reale (E2/E3 hanno std=0.024, range 0.16 → oscillazione) ma il **livello** del plateau è dato da P9, non da Po2.
2. **"Training super-rapido + parametric sweep fattibili"**: ✅ confermato dai dati. **90% del miglioramento E1 raggiunto a B298/3047 = 9.8% di E1**. La rete converge in ~5 min, il resto è plateau-dancing. STEP 2A sfrutta esattamente questo.

**Hardware constraint**: tutti i fix devono mantenere compatibilità FPGA (pesi power-of-2, leak bit-shift, surrogate hardware-friendly senza propagation al threshold).

---

## 📍 Prossimo step pianificato

**STEP 2A — Fast iteration baseline** (codice già pushato, **in attesa di esecuzione utente**):

Lo scopo è validare il **regime fast-iteration** prima di iniziare gli sweep parametrici. Config:
- `n_train: 500` (×10 più piccolo di prima)
- `epochs: 10` (più epoche brevi)
- `early_stop_delta: 0.005` (aggressivo, ferma quando il miglioramento è < 0.5%)
- `scenario_mix: 'highway'`, `cut_in_ratio: 0.0`

**Tempo atteso Azure CPU**: ~15-25 min (vs 2-3h del modo standard).

**Come lanciare** (utente su Azure):
1. `git pull origin main` (porta `ed8debb`)
   - Se "Your local changes would be overwritten by merge" → fai prima:
     `git checkout -- Training_File.ipynb && git pull origin main`
2. Apre `Training_File.ipynb`
3. Cella 1 ha già `TAG="P9_S2A_fast_baseline"` + config STEP 2A
4. `Cell → Run All`
5. Attesa ~15-25 min (early stopping atteso a E4-E5)
6. Cella 8 pusha automaticamente `results/P9_S2A_fast_baseline/`
7. Avvisa l'agente

**Cosa fa l'agente al ritorno**:

1. `git pull`
2. Analizza `results/P9_S2A_fast_baseline/`
3. Confronta con `P9_S1_highway_v2` (n_train=5000)
4. **Decision tree**:

| Esito P9_S2A vs P9_S1 | Significato | STEP 2B parametri da sweep |
|------------------------|-------------|----------------------------|
| val_loss < 0.30 (≈ P9_S1) | ✅ Fast iteration funziona: stesso risultato con 10× meno dati | OK procedo con sweep capacity (CF_HIDDEN_SIZE 32→48→64→96) su dataset ridotto |
| val_loss 0.30-0.35 | ⚠️ Dataset troppo piccolo: serve almeno n_train=1000 | Adatto STEP 2B con n_train=1000 |
| val_loss > 0.35 o crash | ❌ Early stopping troppo aggressivo | Revisione delta o approccio diverso |

---

## 🛣️ Roadmap completa STEP 2

| Step | Stato | Obiettivo | Variabili sweep | Tempo stimato |
|------|-------|-----------|-----------------|----------------|
| **STEP 2A** | 🟡 IN ATTESA Azure | Validare fast-iteration mode con baseline | (nessuna, baseline) | ~15-25 min |
| **STEP 2B** | ⏸️ pianificato | Trovare capacity ottimale | `CF_HIDDEN_SIZE` (32, 48, 64, 96), opz. `CF_RANK` (8, 16) | ~2-3h totali (4-6 run) |
| **STEP 2C** | ⏸️ futuro | Cementare architettura definitiva post-sweep | Config vincitrice di 2B | Variabile |

**Domanda strategica per STEP 2B** (da discutere dopo STEP 2A):
- Sweep solo `CF_HIDDEN_SIZE` (4 run) o anche `CF_RANK` (8 combinazioni)?
- Testare anche cosine vs onecycle vs plateau?

---

## 🗂️ Mappa dei documenti

| File | Quando consultarlo |
|------|---------------------|
| **SESSION_RESUME.md** (questo file) | Sempre per primo, in ogni nuova sessione |
| **GLOSSARY.md** | Decode acronimi P/A/B/F/T/PF/G/STEP usati nei commit/log |
| **WORKFLOW.md** | Come fare un nuovo esperimento end-to-end |
| **TIMELINE.md** | Storia decisioni + cosa è stato provato/scartato |
| **P_S.md** | **Living doc**: 11 problemi diagnosticati + soluzioni applicate/scartate |
| `report/report_4.md` | Snapshot architettura + 12 fix SNN-expert (storico) |
| `report/report_1.md`, `report_2.md`, `report_3.md` | Snapshots più vecchi |
| `cf_model_recommendation.md` | Analisi modelli candidati (IDM/IIDM/ACC-IDM) |
| `optimization_ideas.md` | Idee tuning a lungo termine |
| `training_plan.md` | Piano addestramento (potrebbe essere obsoleto) |
| `use_cases.md` | Use cases V2X (UC2 cut-in, ecc.) |
| `project_core_guidelines.md` | Vincoli hardware, design principles |

---

## ⚙️ Infrastruttura disponibile

### Codice principale (NON modificare senza tracking esplicito in P_S.md)
- `core/network.py` — `CF_FSNN_Net` + layers + funzioni fisica ACC-IDM
- `core/neurons.py` — `ALIFCell`, `LICell` (hardware-friendly)
- `core/hardware.py` — `SurrogateSpike_Hardware` (γ=1.0 A3), `PowerOf2Quantize`
- `train.py` — main + `pinn_loss` + `train_epoch` + `BatchCSVLogger` + early stopping + CLI scenario/cut_in/n_train/n_val
- `data/generator.py` — generatore sintetico ACC-IDM, `parse_scenario_mix`
- `config.py` — costanti (NON modificare scenario/cut_in qui: usa CLI da Cella 1)
- `utils/plot_diagnostics.py` — G1-G13 grafici

### Workflow
- `scripts/preflight.py` — doppio smoke obbligatorio prima di FULL
- `Training_File.ipynb` — notebook universale 10 celle (tracciato in git, sync via pull)

### Cache & artefatti
- `data/cache_*.pt` — dataset persistenti (NON committati, .gitignore)
- `checkpoints/<TAG>/` — pesi modello + CSV + plots (NON committati)
- `results/<TAG>/` — CSV + plots **tracciati in git** (whitelist .gitignore)

---

## 🔧 Comandi quick reference

### Locale (Windows PowerShell)
```bash
# Sync stato
git pull origin main && git log --oneline -5

# Lista esperimenti pushati
ls results/

# Analisi rapida di un run
python -c "import pandas as pd; df = pd.read_csv('results/<TAG>/training_log.csv'); print(df)"

# Smoke locale fast iteration (~9 min CPU laptop)
python train.py --tag local_check --scenario_mix highway --cut_in_ratio 0.0 \
                --n_train 200 --n_val 50 --epochs 3 \
                --early_stop_patience 1 --early_stop_delta 0.005 \
                --max_lr 2e-3 --seq_len 50
```

### Azure (Jupyter)
```bash
# Sync codice + notebook
git pull origin main

# Se git lamenta "Your local changes would be overwritten by merge":
git checkout -- Training_File.ipynb && git pull origin main

# Solo Cella 1 va modificata per nuovo esperimento
# Run All esegue: pull → preflight → FULL → display → push results

# Cleanup storage (se compute instance pieno)
!find checkpoints -name "best_model.pt" -delete   # mantiene CSV/PNG
!rm -rf checkpoints/<old_tag>                      # cancella un esperimento intero
```

### Commit di results (fatto automaticamente da Cella 8)
```bash
git add results/<TAG>/
git commit -F /tmp/commit_msg.txt   # messaggio generato auto da Cella 8
git push origin main
```

---

## 🚨 Lezioni cardinali (per non ripetere errori)

1. **NON applicare fix SNN "da manuale" senza verificare l'implementazione specifica del surrogate** (errore B4: detach reset rotto perché `SurrogateSpike_Hardware` non propaga al threshold). Vedi P5.

2. **NON modificare config.py manualmente su Azure** (errore P9_S1_highway_only: identico a P6_T3_full perché config.py non modificato). Vedi P10. Usa CLI/Cella 1.

3. **NON sprecare compute su training oltre il plateau** (P6_T3 ha sprecato ~2h girando E4 destinato al crash). Usa `early_stop_delta` adeguato. Su nostro plateau, `0.005` è giusto (`1e-4` è troppo sensibile, non ferma mai). Vedi P11 + STEP 2A.

4. **Il plateau val_loss ≈ 0.35 (full-mix) o 0.28 (highway-only) è strutturale** (capacity insufficiency). Non insistere con fix anti-crash: aumenta capacità o accetta il plateau. Vedi P8, P9.

5. **L'esplosione del gradiente è SINTOMO, non causa**: rete satura → spike rate degenera → catena ricorrenza U·V amplifica → boom. Vedi P7, P8.

6. **Tutti i fix devono mantenere compatibilità FPGA**: pesi power-of-2, leak bit-shift, surrogate hw-friendly. Vedi `project_core_guidelines.md`.

7. **Cache invalidate vanno rigenerate**: se cambi fisica (es. F1 s_safe=2.0) o scenario, cancella `data/cache_*.pt` o usa nome diverso. Il `CACHE_PATH` in Cella 1 ora include `n_train` + `scenario_mix` + `cut_in_ratio` → collisioni evitate.

8. **Telemetria T è sacra**: i CSV per-batch (`training_batch_log.csv`) sono l'unico modo per diagnosticare run abortiti. Non disabilitarli.

9. **La rete converge nel 10% di E1** (osservazione utente confermata dai dati). Non aspettare 5 epoche: usa fast-iteration con `n_train` ridotto + early stopping aggressivo per **iterare 10-20× più velocemente**. Vedi STEP 2A.

10. **Po2 quantization NON è il plateau**: i pesi raw sono float continui (STE). Il bottleneck è capacity vs task complexity (prova: highway plateau 0.28 ≠ full-mix plateau 0.35 — sarebbe stato lo stesso se Po2 fosse il bottleneck).

---

## 📊 Risultati storici principali

| TAG | Config chiave | E completate | val_loss best | Esito |
|-----|---------------|--------------|---------------|-------|
| (pre-F1) | seq=100, lr=5e-3, no fix | 0 | — | ❌ crash B1000 |
| `A1_onecycle_v3` | + B4 (poi rollback) | 0 | — | ❌ crash B126 (B4 incompatibile) |
| `P6_T2_full` | A3+A1+A2 | 1 | 0.371 | ❌ crash E2 B2395 |
| `P6_T3_full` | + B5 | 3 | **0.354** | ❌ crash E4 (47 inf grad) |
| `P9_S1_highway_only` | (=P6_T3, config.py drift) | 3 | 0.354 | ❌ identico a P6_T3 |
| `P9_S1_highway_v2` | + P10 + P11 + scenario CLI | 2 | **0.277** | ❌ crash E3 — **P9 CONFERMATO!** (-22% vs full-mix) |
| **`P9_S2A_fast_baseline`** (in attesa) | + STEP 2A (n_train=500, delta=0.005) | TBD | TBD | TBD |

**Pattern**: full-mix plateau ~0.354, highway-only plateau ~0.277. Differenza significativa che esclude Po2 come causa.

---

## 🎯 Cosa fare adesso (per un nuovo agente / sessione)

### Se l'utente dice "ho lanciato STEP 2A, ecco i risultati":
1. `git pull origin main`
2. `ls results/P9_S2A_fast_baseline/`
3. Analizza `training_log.csv` per val_loss
4. Confronto con `P9_S1_highway_v2` (val=0.277)
5. Applica decision tree sopra → propone STEP 2B

### Se l'utente dice "non ho ancora lanciato":
- Ricorda che il notebook è già pronto (commit `ed8debb`)
- Verifica che lui faccia `git pull` su Azure
- Spiega cosa atteso: ~15-25 min, val_loss ≈ 0.28-0.30 atteso

### Se l'utente dice "nuova diagnosi/problema":
1. Leggi `P_S.md` per stato problemi correnti
2. Leggi `TIMELINE.md` per capire perché siamo qui
3. Consulta skill `SNN-expert` (ch22 §22.x) se è diagnosi tecnica
4. Propone fix tracciandolo come nuovo `P<N>` in `P_S.md`

### Se l'utente vuole STEP 2B:
- Discuti con lui quali variabili sweep (HIDDEN_SIZE / RANK / scheduler)
- Implementa CLI `--cf_hidden_size` e `--cf_rank` in `train.py`
- Aggiorna notebook Cella 1 con `'cf_hidden_size': 64`, ecc.
- Crea N esperimenti con TAG `P9_S2B_h<N>_r<R>` (es. `P9_S2B_h64_r16`)
- Mostra tabella confronto risultati

---

## 🔗 Esterno

- **GitHub**: https://github.com/carmineesposito01-ice-beep/SNN_Experiment
- **Skill diagnostica**: `SNN-expert` (locale, 23 capitoli, ch22 §22.2-22.4 critici)
- **Skill car-following**: `car-follow-expert` (Treiber & Kesting 2025, ch12 ACC-IDM)
- **Hardware target**: PYNQ-Z1 FPGA (Xilinx Zynq-7020)

---

## 📝 Log aggiornamenti questo file

| Data | Cambio | Autore |
|------|--------|--------|
| 2026-05-28 18:00 | Creato (post commit `3dedf51`) | claude (session 28/05) |
| 2026-05-28 21:00 | Aggiornato post `ed8debb` (STEP 2A) + P9 confermato + eurekas utente | claude (session 28/05) |
