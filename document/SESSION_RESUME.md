# SESSION_RESUME.md — Quick context for any new Claude session

> **Scopo**: in 5 minuti capire **dove siamo**, **cosa è stato fatto**, **cosa fare adesso**.
> Aggiornare ad ogni milestone (1 sezione "Stato attuale" sempre aggiornata, log storico in coda).

---

## 🎯 Stato attuale (2026-05-28 18:00)

**Repo HEAD**: `3dedf51` — `feat: P10 (scenario/cut_in CLI-controllabili) + P11 (early stopping) + notebook in git`

**Progetto**: CF_FSNN — Spiking Neural Network per identificazione parametri car-following ACC-IDM (con base IIDM, Treiber Ch12 Sez.12.4). Target hardware: PYNQ-Z1 FPGA.

**Architettura rete**: 864 parametri totali
- HiddenLayer_ALIF (4→32, rank=8, max_delay=6)
- OutputLayer_LI (32→5) → params IDM `[v0, T, s0, a, b]`

**Diagnosi corrente**: **P9 — capacity insufficiency** (vedi `P_S.md`).
- 5 run consecutivi convergono al plateau `val_loss ≈ 0.35` indipendentemente dai fix applicati
- 4 esplosioni del gradiente, tutte SINTOMO del plateau (training oltre il limite rappresentazionale)
- Conferma matematica: `val_loss 0.371 → 0.363 → 0.354` con asintoto chiaro

**Hardware constraint**: tutti i fix devono mantenere compatibilità FPGA (pesi power-of-2, leak bit-shift, surrogate hardware-friendly senza propagation al threshold).

---

## 📍 Prossimo step pianificato

**STEP 1 (in attesa di esecuzione utente)**: ri-eseguire `P9_S1_highway_v2` su Azure.

Obiettivo: confermare/falsificare P9 con dataset semplificato (solo highway, no cut-in).

| Esito val_loss | Significato | Prossimo |
|----------------|-------------|----------|
| < 0.25 | ✅ P9 confermato | STEP 2: capacity increase (CF_HIDDEN_SIZE 32→64, CF_RANK 8→16) |
| 0.25-0.32 | ⚠️ P9 parziale | STEP 2 comunque |
| 0.32-0.40 | ❌ P9 falsificato | Indagine separata (encoding, loss formulation) |

**Come lanciare** (utente su Azure):
1. `git pull origin main`
2. Apre `Training_File.ipynb`
3. Cella 1 ha già `TAG="P9_S1_highway_v2"`, `scenario_mix='highway'`, `cut_in_ratio=0.0`, `early_stop_patience=2`
4. `Cell → Run All`
5. Attesa ~2-3h (early stopping atteso a E3-E4)
6. Avvisa l'agente

**Cosa fa l'agente al ritorno**: `git pull`, analizza `results/P9_S1_highway_v2/`, decide STEP 2 sulla base del val_loss raggiunto.

---

## 🗂️ Mappa dei documenti

| File | Quando consultarlo |
|------|---------------------|
| **SESSION_RESUME.md** (questo file) | Sempre per primo, in ogni nuova sessione |
| **GLOSSARY.md** | Decode acronimi P/A/B/F/T/PF/G usati nei commit/log |
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
- `train.py` — main + `pinn_loss` + `train_epoch` + `BatchCSVLogger` + early stopping
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

# Smoke locale di sanità (no Azure)
python train.py --smoke --tag local_check --scenario_mix highway --cut_in_ratio 0.0
```

### Azure (Jupyter)
```bash
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

3. **NON sprecare compute su training oltre il plateau** (P6_T3 ha sprecato ~2h girando E4 destinato al crash). Usa `early_stop_patience=2`. Vedi P11.

4. **Il plateau val_loss ≈ 0.35 è strutturale** (capacity insufficiency). Non insistere con fix anti-crash: aumenta capacità o accetta il plateau. Vedi P8, P9.

5. **L'esplosione del gradiente è SINTOMO, non causa**: rete satura → spike rate degenera → catena ricorrenza U·V amplifica → boom. Vedi P7, P8.

6. **Tutti i fix devono mantenere compatibilità FPGA**: pesi power-of-2, leak bit-shift, surrogate hw-friendly. Vedi `project_core_guidelines.md`.

7. **Cache invalidate vanno rigenerate**: se cambi fisica (es. F1 s_safe=2.0) o scenario, cancella `data/cache_*.pt` o usa nome diverso.

8. **Telemetria T è sacra**: i CSV per-batch (`training_batch_log.csv`) sono l'unico modo per diagnosticare run abortiti. Non disabilitarli.

---

## 📊 Risultati storici principali

| TAG | Config chiave | E completate | val_loss best | Esito |
|-----|---------------|--------------|---------------|-------|
| (pre-F1) | seq=100, lr=5e-3, no fix | 0 | — | ❌ crash B1000 |
| `A1_onecycle_v3` | + B4 (poi rollback) | 0 | — | ❌ crash B126 (B4 incompatibile) |
| `P6_T2_full` | A3+A1+A2 | 1 | 0.371 | ❌ crash E2 B2395 |
| `P6_T3_full` | + B5 | 3 | **0.354** | ❌ crash E4 (47 inf grad) |
| `P9_S1_highway_only` | (=P6_T3, config.py drift) | 3 | 0.354 | ❌ identico a P6_T3 |
| `P9_S1_highway_v2` (in attesa) | + P10 + P11 | TBD | TBD | TBD |

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
