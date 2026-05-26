# CF_FSNN — Piano Esecutivo di Training
> Configurazione, piattaforme disponibili e procedura per l'esecuzione degli esperimenti.
> Da consultare insieme a `optimization_ideas.md` (analisi e idee) prima di ogni run.
> Aggiornato: 2026-05-25

---

## PIATTAFORME DI TRAINING DISPONIBILI

| Piattaforma | Hardware | Note |
|---|---|---|
| **CPU** | Locale (non specificato) | Training lento — solo per smoke test rapidi (≤ 5 epoche, n_train piccolo) |
| **GPU** | RTX 3060, 12 GB GDDR7 | Training principale — CUDA disponibile |
| **Cloud** | Microsoft Azure (GitHub Educational) | Per run lunghi o sweep paralleli |

---

## CONFIGURAZIONE PER PIATTAFORMA

### CPU — Smoke test (< 30 min)
```python
# config.py — override suggeriti
N_SCENARIOS_TRAIN = 200    # ridotto da 5000
N_SCENARIOS_VAL   =  50
BATCH_SIZE        =  16    # ridotto da 64
EPOCHS            =   5
```
**Quando usare:** verifica rapida che il codice non abbia errori prima di un run lungo; Stage A/B/C a 5 epoche.

### GPU locale — Training principale
```python
# Nessun override — usare config.py nominale
# DEVICE è già auto-detect: torch.device("cuda" if torch.cuda.is_available() else "cpu")
N_SCENARIOS_TRAIN = 5000
BATCH_SIZE        =   64   # RTX3060 12GB regge batch 64 o anche 128
EPOCHS            =   50
```
**Stima tempi** (approssimativa — da verificare al primo run):
- Generazione dataset (5000 traj × 1200 step): ~3–5 min su CPU (unica volta)
- 1 epoca training (5000 traj, batch=64): ~2–4 min su GPU
- 50 epoche complete: ~2–3 ore

**Checklist pre-run GPU:**
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Atteso: True  NVIDIA GeForce RTX 3060
```

### Azure (Microsoft) — Run lunghi / sweep paralleli
- Credenziali: account GitHub Educational → Azure for Students
- Consigliato: VM Standard_NC6 (1× Tesla K80, 12 GB) o Standard_NC6s_v3 (1× V100, 16 GB)
- Caricare il progetto via `git push` → clone su VM Azure
- **Attenzione:** terminare la VM dopo ogni sessione per non consumare i crediti

**Setup rapido Azure:**
```bash
# Sulla VM Azure
git clone <repo>
cd CF_FSNN
pip install -r requirements.txt
python train.py --epochs 50
```

---

## PROCEDURA ESECUZIONE STAGE A/B/C

### Fase 0 — Pre-condizioni obbligatorie
Prima di qualsiasi run di ottimizzazione:
1. Il sistema di logging deve essere attivo (`utils/plot_diagnostics.py` implementato)
2. Il generatore deve includere scenari cut-in (necessario per ACC-IDM)
3. ACC-IDM con base IIDM deve essere attivo nella `pinn_loss()`

### Stage A — Fix scheduler (eseguire su GPU locale)
```bash
# A1: OneCycleLR
python train.py --epochs 5 --scheduler onecycle --max_lr 5e-3 --tag A1_onecycle

# A2: CosineAnnealing
python train.py --epochs 5 --scheduler cosine --T0 5 --tag A2_cosine

# A3: Baseline ReduceLROnPlateau
python train.py --epochs 5 --scheduler plateau --patience 10 --tag A3_plateau
```
**Output atteso per ogni run:**
- `checkpoints/A1_onecycle/training_log.csv`
- `checkpoints/A1_onecycle/plots/G1_loss_curve.png` ... `G7_violin.png`

**Criterio di successo Stage A:**
- val_loss scende monotonicamente dopo ep.1
- Pendenza negativa a ep.5
- Il migliore dei 3 → usato in Stage B

### Stage B — Sweep LR (con scheduler vincitore di A)
```bash
python train.py --epochs 5 --scheduler <winner_A> --lr 3e-4 --tag B1_lr3e4
python train.py --epochs 5 --scheduler <winner_A> --lr 1e-3 --tag B2_lr1e3
python train.py --epochs 5 --scheduler <winner_A> --lr 3e-3 --tag B3_lr3e3
```
**Criterio di successo Stage B:** LR con val_loss più bassa a ep.5 → usato in Stage C

### Stage C — Sweep lambda PINN (con best scheduler + LR)
```bash
python train.py --epochs 5 --lambda_ou 0.05 --lambda_bc 1.0 --tag C1_baseline
python train.py --epochs 5 --lambda_ou 0.20 --lambda_bc 0.5 --tag C2_ou_up
python train.py --epochs 5 --lambda_data 2.0 --lambda_phys 0.05 --lambda_ou 0.20 --lambda_bc 0.3 --tag C3_data_first
python train.py --epochs 5 --lambda_phys 0.20 --lambda_ou 0.10 --lambda_bc 0.5 --tag C4_phys_up
```

### Full training — dopo Stage A+B+C
```bash
# Con la configurazione vincente da Stage A+B+C
python train.py --epochs 50 --tag FULL_v1
```

---

## ARGPARSE — Parametri attesi in train.py

Il file `train.py` deve supportare almeno i seguenti flag (da implementare se non presenti):

| Flag | Default | Descrizione |
|------|---------|-------------|
| `--epochs` | 50 | Numero epoche |
| `--lr` | 1e-3 | Learning rate iniziale |
| `--batch_size` | 64 | Batch size |
| `--seq_len` | 100 | Lunghezza finestra TBPTT |
| `--scheduler` | `plateau` | Uno tra: `plateau`, `onecycle`, `cosine` |
| `--max_lr` | 5e-3 | Per OneCycleLR |
| `--lambda_data` | 1.0 | Peso L_data |
| `--lambda_phys` | 0.1 | Peso L_phys |
| `--lambda_ou` | 0.05 | Peso L_OU |
| `--lambda_bc` | 1.0 | Peso L_bc |
| `--load_data` | None | Path a .pkl pre-generati |
| `--n_train` | 5000 | Numero scenari training |
| `--tag` | `run` | Etichetta cartella output |
| `--optimizer` | `adam` | Uno tra: `adam`, `lion`, `muon_lion` |

---

## STRUTTURA OUTPUT ATTESA

Dopo ogni run, la struttura dei file prodotti deve essere:

```
checkpoints/
└── <tag>/
    ├── best_model.pt            ← checkpoint del best val_loss
    ├── last_model.pt            ← checkpoint finale
    ├── training_log.csv         ← metriche per epoca
    ├── config_snapshot.json     ← config usata (per riproducibilità)
    └── plots/
        ├── G1_loss_curve.png
        ├── G2_components.png
        ├── G3_lr_schedule.png
        ├── G4_grad_norm.png
        ├── G5_T_scatter.png
        ├── G6_spike_rate.png
        └── G7_violin_params.png
```

---

## CRITERI DI SUCCESSO DEL TRAINING

| Metrica | Baseline attuale | Target Stage A/B/C | Target full training |
|---------|-----------------|-------------------|----------------------|
| SRMSE (test) | 0.871 | < 0.5 | < 0.3 |
| T bias | +0.15 s | < +0.08 s | < +0.03 s |
| T σ_pred / σ_true | 0.25 (comp. 4×) | > 0.50 | > 0.80 |
| v0 bias | +16% | < +8% | < +5% |
| Best epoch | 1/20 | > 3/5 | > 10/50 |
| Spike rate hidden | sconosciuto | 10–20% | 10–20% |

---

## NOTE DI RIPRODUCIBILITÀ

- Ogni run deve salvare `config_snapshot.json` con tutti i parametri usati
- Il seed è fisso (`SEED=42`) in `config.py` → risultati riproducibili a parità di hardware
- Su GPU con CUDA, aggiungere `torch.backends.cudnn.deterministic = True` per riproducibilità totale (penalità ~15% velocità)
- Su Azure, verificare che la versione CUDA della VM corrisponda a quella locale prima di confrontare risultati

---

> **Documenti correlati:**
> - `optimization_ideas.md` — analisi completa idee e razionale
> - `cf_model_recommendation.md` — modello fisico ACC-IDM con base IIDM
> - `use_cases.md` — requisiti funzionali (UC2 guida la necessità di scenari cut-in)
