# WORKFLOW.md — Procedura end-to-end per un nuovo esperimento

> Setup → training → analisi → push results.
> **Convention post 2026-06-02**: ogni studio nuovo ha (a) branch git dedicato `<Topic>_Deep_Study` o `<Topic>_Setup`, (b) notebook dedicato `<Topic>_Diagnostics.ipynb`, (c) sub-folder dedicata `results/<Study_Name>/`.

## 🔀 Convention nuovi studi (R1, R2, R3, ...)

```
1. Branch creato da main aggiornato:
     git checkout main && git pull origin main
     git checkout -b <Topic>_Deep_Study
     git push -u origin <Topic>_Deep_Study

2. Notebook: <Topic>_Diagnostics.ipynb (root repo)

3. Results: results/<Topic>_Study/<tag>/
   - Cellula RUN del notebook fa: subprocess train.py + shutil.move
     da checkpoints/<tag>/ → results/<Topic>_Study/<tag>/
   - SKIP_IF_EXISTS=True per resume idempotente

4. Doc: document/<TOPIC>_DEEP_STUDY.md
   - Parte 1: math + source walkthrough (pre-esperimenti)
   - Parte 2: community wisdom / state-of-the-art (ricerca multi-fonte)
   - Parte 3: lessons dai nostri esperimenti (post-Azure)

5. Chiusura: merge in main → cancella branch di lavoro (NON i branch storici)
```

Esempi: `Prodigy_Deep_Study` (R2 attivo), `EventProp_Deep_Study` (R3 futuro), `Arch_Tested_Setup` (R1 chiuso/cancellato).

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

### 4. Setup nbstripout (CRUCIALE post-2026-05-29 — evita conflitti Jupyter)
**Una volta sola** per ogni nuova compute instance Azure E ogni nuova workstation locale:

```bash
pip install --quiet nbstripout
nbstripout --install --attributes .gitattributes
```

**Cosa fa**: configura un filter git che strippa **automaticamente** gli output dei notebook
prima di ogni operazione git. Il notebook resta intatto su disco (Jupyter vede output),
ma git ne vede una versione pulita → mai più `"Your local changes would be overwritten"`.

Operazione idempotente: `--install` non duplica se già attivo.

In alternativa: lo `Training_File_Sweep.ipynb` Cella 0 esegue questo automaticamente al primo run.

**Lezione storica**: abbiamo perso 4 sessioni a fare workaround manuali (`git checkout -- *.ipynb` prima di ogni pull) prima di setupparlo. Da ora è obbligatorio al primo setup.

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
Oppure cambia il `CACHE_PATH` in Cella 1 (il default include scenario+cut_in+n_train nel nome, quindi raramente succede).

### "Your local changes to the following files would be overwritten by merge"
**Fix permanente (DA SETUPPARE UNA VOLTA, vedi PRIMO SETUP punto 4)**: installa nbstripout. Dopo nbstripout attivo, questo errore non succede mai più.

**Fix immediato se nbstripout non è ancora attivo**: scarta gli outputs locali (saranno rigenerati al prossimo Run All):
```bash
git checkout -- Training_File.ipynb Training_File_Sweep.ipynb
git pull --no-rebase --no-edit origin main
```

Pattern raccomandato post-2026-05-29: **setup nbstripout al primo setup della compute instance**. Dopo, `git pull` su notebook girati non si blocca più.

### "fatal: Need to specify how to reconcile divergent branches"
Git ≥2.27 richiede strategia esplicita per `git pull` quando ci sono commit divergenti. Usa sempre:
```bash
git pull --no-rebase --no-edit origin main
```
- `--no-rebase`: forza merge (default-agnostic, evita errore "divergent branches")
- `--no-edit`: evita prompt nano sul merge commit auto-generato

**Alternativa permanente** (una tantum):
```bash
git config pull.rebase false      # configura merge di default
git config core.editor "true"     # niente editor sui merge
```

### `git push` rejected dopo commit di results
Succede se nel frattempo qualcuno (anche tu da un'altra macchina) ha pushato. **Pattern raccomandato**:
```bash
git commit -m "..."
git pull --no-rebase --no-edit origin main   # pull-before-push obbligatorio
git push origin main
```

I notebook Sweep/Standard Cella 8 + Cella 6 già seguono questo pattern. Se push manuale, ricordatene.

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

### Sweep parametrico (STEP 2B+, usa `Training_File_Sweep.ipynb`)
Per testare N configurazioni in batch (es. capacity sweep, scenario diversity):

1. Apri `Training_File_Sweep.ipynb` (NON `Training_File.ipynb`)
2. **Cella 1**: edita `SWEEP_PLAN = [...]` con lista esperimenti
   ```python
   SWEEP_PLAN = [
       {'tag': 'P9_S2C_h64_r16_run1', 'cf_hidden_size': 64, 'cf_rank': 16, 'scenario_mix': 'highway'},
       {'tag': 'P9_S2C_h64_r16_run2', 'cf_hidden_size': 64, 'cf_rank': 16, 'scenario_mix': 'urban'},
       ...
   ]
   ```
3. Flag di controllo:
   - `RUN_PREFLIGHT = True` — doppio smoke obbligatorio per ogni run
   - `PUSH_PER_RUN = True` — pusha results subito dopo ogni FULL completato
   - `SKIP_IF_EXISTS = True` — salta runs già presenti in `results/<tag>/`
   - `STOP_ON_FAIL = False` — continua sweep anche se un run crash
4. **Cell → Run All**. Il loop esegue: preflight → train.py → push per ogni run
5. Cell 4 produce summary table, Cell 5 grafici comparativi (S1-S6), Cell 6 push aggregati

**Caratteristiche**:
- **Cache condivisa**: runs con stessa `(n_train, scenario_mix, cut_in)` riusano la stessa cache (es. 5 runs capacity highway = 1 generazione dataset)
- **Continue-on-failure**: se un run fallisce, il sweep va al successivo
- **Resume parziale**: se interrotto, SKIP_IF_EXISTS riprende dai mancanti

**Bug noti fixati**:
- Commit `6790019`: preflight propaga `--cf_hidden_size/--cf_rank/--scenario_mix/--cut_in_ratio`
- Commit `534c2af`: `_push_results` non importa torch (kernel Jupyter Azure non lo ha)

### Fast iteration mode (STEP 2A — consigliato per esperimenti veloci)
Quando vuoi iterare rapidamente (testare config, scheduler diversi, sweep parametrici):
```python
CONFIG = {
    'epochs':              10,         # più epoche brevi
    'n_train':             500,        # dataset 10× più piccolo
    'n_val':               100,
    'early_stop_patience': 2,
    'early_stop_delta':    0.005,      # AGGRESSIVO — ferma quando miglioramento < 0.5%
    ...
}
```

**Tempo**: ~15-25 min vs 2-3h del modo standard.

**Quando NON usare**: per il run finale "di prodotto" usa il dataset completo (n_train=5000) per il modello migliore. Fast iteration è per scoperta/exploration.

**Rationale**: la rete converge nel ~10% di E1 (osservazione utente confermata da `P9_S1_highway_v2` — 90% del miglioramento E1 raggiunto a B298/3047). Vedi `TIMELINE.md` lezione #8.

### Solo preflight (senza FULL)
```python
RUN_FULL = False
```
Utile per testare modifiche al codice senza spendere compute.

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

L'agente farà `git pull`, leggerà `results/P9/P9_S1_highway_v2/`, e risponderà.
