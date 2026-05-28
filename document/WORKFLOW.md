# WORKFLOW.md — Procedura end-to-end per un nuovo esperimento

> Setup → training → analisi → push results. Tutto via `Training_File.ipynb` (cellula 1 unica da modificare).

---

## 📋 TL;DR (per chi ha già fatto il setup)

```
Sul tuo PC locale:
  git pull origin main                              (porta ultime modifiche)

Su Azure (compute instance attiva):
  1. Bash: git pull origin main                     (sync notebook + codice)
  2. Apri Training_File.ipynb
  3. Cella 1: modifica TAG + parametri CONFIG
  4. Cell → Run All
  5. Attesa ~2-3h (early stopping ~E3)
  6. Cella 8 pusha automaticamente results/<TAG>/
  7. Avvisa l'agente Claude per analisi
```

---

## 🚀 PRIMO SETUP (una sola volta per compute instance Azure)

### 1. Verifica dipendenze
Apri il notebook, esegui **Cella 0 (Bootstrap)**. Mostra:
- Verifica torch/numpy/pandas/matplotlib (installa se mancanti)
- Stato git (commit attuale, file modificati)
- Lista `checkpoints/` esistenti (cosa è già stato eseguito)
- Lista `results/` (cosa è già stato pushato)
- Cache `data/cache_*.pt` disponibili

Se mancano pacchetti, segui i suggerimenti `pip install`.

### 2. Verifica `.gitignore` whitelist
La Cella 0 verifica automaticamente che `.gitignore` contenga `!results/` (whitelist).
Se manca → fai `git pull origin main` per portare il commit `bdc1a00` o successivo.

### 3. Verifica accesso git (push)
```bash
git remote -v
git config user.name
git config user.email
```
Se non configurato, ci saranno problemi con la Cella 8 (push). Configura:
```bash
git config user.name "Il tuo nome"
git config user.email "tua@email.com"
```

---

## 🔄 WORKFLOW STANDARD (per ogni esperimento)

### Step A — Modifica Cella 1

Apri `Training_File.ipynb`, modifica **SOLO la Cella 1**.

**Esempio**: STEP 1 highway-only diagnostico

```python
TAG = "P9_S1_highway_v2"

CONFIG = {
    'epochs':         5,
    'scheduler':      'onecycle',
    'max_lr':         2e-3,
    'seq_len':        50,
    'batch_size':     64,
    'lambda_data':    1.0,
    'lambda_phys':    0.1,
    'lambda_ou':      0.05,
    'lambda_bc':      1.0,
    'optimizer':      'adam',
    # ── P10: scenario da CLI (no editing config.py) ──
    'scenario_mix':   'highway',        # 'default' | 'highway' | 'urban' | 'truck' | 'mixed' | 'highway:0.7,urban:0.3'
    'cut_in_ratio':   0.0,              # 0.0 = no cut-in
    # ── P11: early stopping ──
    'early_stop_patience': 2,
    'early_stop_delta':    1e-4,
    'max_inf_streak':      20,
}

CACHE_PATH = f"data/cache_1500_{CONFIG['scenario_mix']}_cut{CONFIG['cut_in_ratio']}.pt"

RUN_GIT_PULL    = True
RUN_PREFLIGHT   = True
RUN_FULL        = True
PUSH_RESULTS    = True
```

**Esempi alternativi**:

| Caso | Modifica |
|------|----------|
| Test full-mix (default) | `'scenario_mix': 'default'`, `'cut_in_ratio': 0.20` |
| Highway 70% + urban 30% | `'scenario_mix': 'highway:0.7,urban:0.3'` |
| Solo urban | `'scenario_mix': 'urban'` |
| No early stopping | `'early_stop_patience': 0` |
| Cosine scheduler | `'scheduler': 'cosine', 'T0': 5` |
| Plateau scheduler | `'scheduler': 'plateau', 'lr': 1e-3` |

### Step B — Cell → Run All

L'esecuzione segue 9 celle:

| Cella | Cosa fa | Tempo |
|-------|---------|-------|
| 0 | Bootstrap (sanity check) | 5s |
| 1 | Echo config | 1s |
| 2 | `git pull` + sanity imports | 5s |
| 3 | Verifica cache (genera se manca) | 0-3min |
| 4 | Pre-flight (2 smoke) | 3-5min |
| 5 | FULL training | **2-3h** (con early stop) |
| 6 | Display 15 grafici inline | 5s |
| 7 | Analisi numerica CSV | 5s |
| 8 | Estrazione + commit + push `results/<TAG>/` | 30s |
| 9 (opz) | Comparazione con altri esperimenti | 5s |

### Step C — Verifica esito

Alla fine del notebook vedrai (Cella 7):
```
📈 Per-batch summary (N=15234)
   • Best val_loss:          0.XXXXX
   • Inf grad batches:       N/N
   • Spike rate medio:       X.XX% (target 10-25%)
   • gn pre-clip max finito: X.XXe+XX
```

E nella Cella 8:
```
✅ Push completato. In locale: git pull && ls results/<TAG>/
```

### Step D — Avvisa l'agente

Dal tuo PC locale:
```bash
git pull origin main
ls results/<TAG>/
```

Poi messaggio: **"Fatto, ho pushato `<TAG>`. Fai pull e analizza."**

---

## 🔬 Cosa succede sotto il cofano

### Generazione dataset (se cache assente)
1. `train.py` chiama `generate_dataset(n_train, scenario_mix=<override>, cut_in_ratio=<override>)`
2. Per ogni traiettoria: `_sample_scenario(scenario_mix, cut_in_ratio)` campiona scenario+cut_in
3. Simula 120s di car-following con OU noise, packet loss, eventi cut-in
4. Salva `data/cache_<...>.pt` per riuso

### Preflight (doppio smoke)
1. `scripts/preflight.py` lancia 2 volte `python train.py --smoke ...`
2. Per ognuno verifica 7 criteri pass
3. Se entrambi ✅ → autorizza FULL
4. Se ❌ → blocca FULL (sicurezza)

### Training FULL
1. Carica/genera cache
2. Inizializza `CF_FSNN_Net` (864 param)
3. Loop epoche:
   - `train_epoch`: forward+backward su batch, clip grad max=1.0, ottimizzatore Adam
   - Batch logger (`BatchCSVLogger`) salva 20 col per batch
   - Diagnostica su anomalie (gn > soglia, NaN, inf)
   - Early stopping check (P11)
4. Salva `best_model.pt` quando val_loss migliora
5. Salva `last_model.pt` ad ogni epoca

### Post-training
1. Carica `best_model.pt` (strict=False per compat P2 D2)
2. Forward sul val set → estrae T_pred, T_true, parametri predetti (G5/G7)
3. Seleziona 3 traiettorie val rappresentative (highway/urban/cut_in) → G13
4. Genera 15 PNG in `plots/`
5. Cella 8 copia CSV+JSON+PNG in `results/<TAG>/` e committa

---

## 🐛 Troubleshooting comune

### "Cache scenari inattesi" warning
Significa: la cache esistente è stata generata con scenario_mix diverso dal tuo CONFIG attuale.

**Fix**: cancella e rigenera
```python
!rm data/cache_1500_<...>.pt
```
Oppure cambia il `CACHE_PATH` in Cella 1 (il default include scenario+cut_in nel nome, quindi raramente succede).

### Preflight FAIL
Apri `checkpoints/<TAG>_preflight_1/` e `_preflight_2/`:
- `training_log.csv` esiste? Se no → errore strutturale (es. import)
- `plots/` ha PNG? Se no → bug nei plot
- Cerca `[EARLY-STOP]` o `RuntimeError` nei log

NON forzare il FULL se preflight FAIL. Risolvi il problema upstream.

### Training abortisce
Vedi `results/<TAG>/CRASH_INFO.txt`:
```
Crash detected
Epoch: X
val_loss: inf
```

Apri G8 (gn per batch) per vedere dove esplode, G9 (heatmap layer) per vedere quale layer esplode prima. Apri G11 (spike rate) per vedere se è degenerazione dead-network o saturazione.

### `pd.NA` recursion error nella Cella 7
Bug noto pandas su Azure. Le nostre celle usano `np.nan` invece di `pd.NA` per evitarlo. Se vedi un errore di recursion, controlla che la Cella 7 usi `replace([np.inf, -np.inf], np.nan)` e NON `pd.NA`.

### `git commit` fails con "nothing to commit"
La Cella 8 ha già committato. Niente da fare. Se vuoi forzare un secondo push:
```bash
git push origin main
```

### Compute instance Azure pieno
Cancella checkpoints vecchi:
```python
!find checkpoints -name "best_model.pt" -delete   # mantiene CSV/PNG
!rm -rf checkpoints/<vecchio_tag>                  # cancella esperimento intero
```

I `results/` restano tracciati in git (sicuri).

---

## ⚡ Variations / Modalità avanzate

### Solo preflight (senza FULL)
```python
RUN_FULL = False
```
Utile per testare modifiche al codice senza spendere 3h di compute.

### Solo display di un run precedente
```python
TAG = "P6_T3_full"   # tag esistente
RUN_GIT_PULL = False
RUN_PREFLIGHT = False
RUN_FULL = False
PUSH_RESULTS = False
```
Esegui solo Cella 6 (grafici) e Cella 7 (analisi).

### Smoke locale (Windows, no Azure)
Da PowerShell:
```bash
python train.py --smoke --scenario_mix highway --cut_in_ratio 0.0 \
                --max_lr 2e-3 --seq_len 50 --tag local_check
```
Esegue 1 epoca su 100+30 trajectories → ~75s su CPU laptop.

### Resume da checkpoint
```python
CONFIG['resume'] = 'checkpoints/<TAG>/best_model.pt'
```
**Nota**: ancora non testato post-P11. Verificare che early_stop_counter sia 0 al resume.

---

## 📦 Cosa viene committato in `results/<TAG>/`

| File | Dimensione tipica | Tracciato git |
|------|-------------------|----------------|
| `config_snapshot.json` | <1 KB | ✅ |
| `training_log.csv` (per-epoca) | ~1-5 KB | ✅ |
| `training_batch_log.csv` (per-batch) | ~100-500 KB | ✅ |
| `plots/G1-G13_*.png` | ~2-3 MB totali (15 PNG) | ✅ |
| `CRASH_INFO.txt` (solo se crash) | <1 KB | ✅ |
| `best_model.pt`, `last_model.pt`, `crash_model.pt` | qualche MB ciascuno | ❌ NO (restano in `checkpoints/`) |

**Totale per run: ~2-5 MB versionati in git**. Migliaia di run = qualche GB, gestibile.

---

## 🔁 Convenzioni per i TAG

| Pattern | Per cosa | Esempio |
|---------|----------|---------|
| `<PROBLEM>_<STEP>_<DESC>` | Esperimenti diagnostici | `P9_S1_highway_v2` |
| `<PHASE>_<RESCHEDULER>` | Test scheduler | `A1_onecycle`, `A2_cosine` |
| `local_*` | Smoke locale (no analisi) | `local_check`, `local_B5_smoke` |
| `<NAME>_preflight_1` / `_2` | Auto-generati (non usare manualmente) | — |
| `<NAME>_validation` | Smoke esteso post-fix | `P1_B4_validation` |

**Versionamento**: se ri-lanci con stessi parametri ma codice diverso, suffisso `_v2`, `_v3`, ...

---

## 📞 Hand-off agente Claude

Quando passi un esperimento all'agente per analisi, includi:
1. **TAG** dell'esperimento (es. `P9_S1_highway_v2`)
2. **Commit del codice** usato (mostrato in Cella 2 output: `git log --oneline -3`)
3. **Esito sintetico**: completato/abortito + eventuale `Best val_loss`
4. **Domanda specifica** (se hai osservazioni)

Esempio:
> "Pushato `P9_S1_highway_v2` (commit `3dedf51`). Training completato 5 epoche con early stop, best val_loss=0.27. Confermi P9? Procediamo a STEP 2?"

L'agente farà `git pull`, leggerà `results/P9_S1_highway_v2/`, e risponderà.
