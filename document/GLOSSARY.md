# GLOSSARY.md — Decode degli acronimi usati nel progetto

> Tutti i codici usati in commit, log, plot, documenti. Aggiornare quando si introduce un nuovo prefisso.

---

## 🩺 P1-P11 — Problemi diagnosticati (vedi `P_S.md` per dettagli)

| Codice | Nome | Status |
|--------|------|--------|
| **P1** | Exploding gradient deterministico (originale, B1000/E01) | risolto parzialmente da A3+A1+A2+B5 |
| **P2** | Checkpoint pre-F5 manca `decode_scale` buffer | ✅ risolto da D2 (strict=False) |
| **P3** | Telemetria mancante (era impossibile diagnosticare post-crash) | ✅ risolto da T + grafici G8-G12 |
| **P4** | Rischio FULL senza preflight | ✅ risolto da PF (preflight obbligatorio) |
| **P5** | B4 incompatibile con `SurrogateSpike_Hardware` (rompe ALIF cell learning) | ✅ documentato + rollback |
| **P6** | Roadmap revisione post-P5 (Tier 1/2/3/4) | strategia: A1+A2+A3+B5 (Tier 3) |
| **P7** | Spike-rate saturation post-B5 (oscillazione 5%→25%→50%) | ⚠️ collegato a P9 |
| **P8** | Plateau val_loss ≈ 0.35 in tutti i run (osservazione utente, confermata matematicamente) | confermato |
| **P9** | Capacity insufficiency (rete UNDERSIZED, 864 param insufficient per task) | diagnosi corrente |
| **P10** | Config drift: SCENARIO_MIX/CUT_IN_RATIO non controllabili da CLI | ✅ risolto (commit 3dedf51) |
| **P11** | Early stopping mancante (spreco compute + crash post-plateau) | ✅ risolto (commit 3dedf51) |

---

## 🎛️ A1-A3 — Lever architetturali "soft" (Tier 1-2 del piano P6)

| Codice | Modifica | Status |
|--------|----------|--------|
| **A1** | `max_lr` da 5e-3 → 2e-3 (LR softer per OneCycleLR) | ✅ applicato in P6_T2+ |
| **A2** | `seq_len` da 100 → 50 (dimezza profondità BPTT) | ✅ applicato in P6_T2+ |
| **A3** | γ surrogate da 0.3 → 1.0 in `core/hardware.py` (kernel 3× più stretto) | ✅ applicato (commit `1eff0b0`) |

---

## 🏗️ B4-B6 — Lever strutturali "bigger" (Tier 2-3-4 del piano P6)

| Codice | Modifica | Status |
|--------|----------|--------|
| **B4** | `.detach()` sul reset path ALIF (spezza catena BPTT) | ❌ **SCARTATO** — vedi P5, rotto perché surrogate hw non propaga al threshold |
| **B5** | Spike-rate regularizer `λ_sr·(spike_rate − 0.15)²` in `pinn_loss()` | ✅ applicato (commit `a13afb6`) |
| **B6** | TBPTT (Truncated BPTT) — chunking della sequenza temporale | ⏸️ in stand-by come escalation finale |

---

## 🔬 F1-F12 — 12 Fix SNN-expert review (commit `4e01bcc`, 2026-05-26)

| Codice | Modifica | File |
|--------|----------|------|
| **F1** | s_safe `0.01 → 2.0` in `_acc_iidm_accel` (allineamento generator ↔ network) | `data/generator.py` |
| **F2** | val_epoch NaN guard | `train.py` |
| **F3** | `plot_diagnostics` crash su CSV vuoto (training abortito) | `plot_diagnostics.py` |
| **F4** | `forward_sequence_with_stats` da monkey-patch a metodo di classe | `network.py` + `train.py` |
| **F5** | `_decode_params`: pre-scaling `decode_scale` per gradiente bilanciato (v0/T 18.5× squilibrio) | `network.py` |
| **F6** | OU floor irreducibile documentato (~1.8e-4) | `network.py` docstring |
| **F7** | delta=4 hardcoded documentato (coerente con config) | `network.py` |
| **F8** | `deque` invece di `list` per delay buffer (O(1) vs O(n)) | `network.py` |
| **F9** | `thresh_jump.clamp(min=0)` invece di `abs()` (più efficiente, gradiente simmetrico) | `neurons.py` |
| **F10** | `fatigue.clamp(min=0)` invece di `relu` (ridondante, gradiente equivalente) | `neurons.py` |
| **F11** | Docstring `max_delay`: 0.6s → 0.06s (era errato di un fattore 10) | `network.py` |
| **F12** | γ=0.3 surrogate documentato come scelta Bellec 2018 LSNN (poi rivisto in A3) | `hardware.py` |

---

## 📊 T — Telemetria estesa per-batch (commit `1ff3da9`, 2026-05-27)

- Nuovo file `training_batch_log.csv` per ogni run
- 20 colonne: epoch, batch_idx, loss components, spike_rate, gn per-layer, weight_max, flags inf/nan
- `BatchCSVLogger` classe che flusha ogni 50 righe (append-only, sopravvive a crash)
- Helper `_make_batch_row` riusato dai 3 path di `train_epoch` (normale/NaN/inf)
- Visibile in grafici **G8-G13**

---

## 🚦 PF — Pre-flight doppio smoke (commit `1ff3da9`)

- Script `scripts/preflight.py`
- Lancia 2 smoke consecutivi prima di ogni FULL training
- Verifica 7 criteri pass su ENTRAMBI: exit code 0, no `[EARLY-STOP]`, CSV >= righe minime, ≥5 PNG, best_model loadable, no `RuntimeError/Traceback`
- Costo ~2× ~2 min (CPU) / ~30s (GPU)
- ROI: 1 FULL salvato (~30 min) ripaga 100× il costo di tutti i preflight precedenti
- **Regola permanente**: obbligatorio prima di ogni training ≥3 epoche

---

## 🗝️ D1-D3 — Soluzioni a P2 (checkpoint compat)

| Codice | Soluzione | Status |
|--------|-----------|--------|
| **D1** | Cancellare manualmente `best_model.pt` stale | applicato una tantum |
| **D2** | `load_state_dict(..., strict=False)` (fix permanente) | ✅ applicato in `train.py` |
| **D3** | Print delle chiavi missing/unexpected per audit | ✅ incluso in D2 |

---

## 🚀 STEP 2A / 2B / 2C — Roadmap post-P9-confermato

Sequenza di esperimenti per risolvere P9 (capacity insufficiency) sfruttando l'osservazione che la rete converge nel 10% di E1 (Eureka 2 utente).

| Codice | Significato | Status | Tempo |
|--------|-------------|--------|-------|
| **STEP 2A** | Fast iteration baseline: `n_train=500, epochs=10, early_stop_delta=0.005` con architettura attuale (32/8). Validare il regime fast | 🟡 in attesa Azure | ~15-25 min |
| **STEP 2B** | Parametric sweep su `CF_HIDDEN_SIZE` (32, 48, 64, 96) ± `CF_RANK` (8, 16). 4-6 run con fast-iteration mode | ⏸️ pianificato post-2A | ~2-3h totali |
| **STEP 2C** | Architettura definitiva post-sweep: aggiorna `config.py` con valori ottimali, test su dataset full-mix | ⏸️ futuro | variabile |

**Pattern TAG**: `P9_S2A_*`, `P9_S2B_h<HIDDEN>_r<RANK>` (es. `P9_S2B_h64_r16`), `P9_S2C_*`.

---

## 💡 Concetti emersi dalle sessioni (eurekas + diagnosi)

| Concetto | Significato | Riferimento |
|----------|-------------|-------------|
| **Plateau val_loss** | Limite asintotico inferiore della val_loss su un dato dataset. Per CF_FSNN: 0.35 su full-mix, 0.28 su highway-only. È strutturale (P9). | P8 |
| **Plateau dancing** | Pattern oscillatorio della loss quando la rete ha raggiunto il plateau ma il training continua. Std≈0.024 sul nostro modello. Rivelato dall'eureka 1 utente | Eureka 1 |
| **Fast iteration mode** | Regime di training con `n_train` ridotto (500 vs 5000) + `epochs` aumentate + `early_stop_delta` aggressivo (0.005). Permette parametric sweeps in poche ore | STEP 2A, Eureka 2 |
| **Capacity insufficiency** | La rete (864 param) è troppo piccola per il task. Sintomi: plateau val_loss, oscillazione spike rate, esplosione gradiente. Conferma: highway 0.28 ≠ full-mix 0.35 | P9 |
| **Task complexity vs Capacity** | Il plateau scala con la complessità del task: più scenari/cut_in = più capacity richiesta. Permette di "calibrare" capacity al task | P9, Eureka 1 verificata |
| **Convergenza in 10% di E1** | Il 90% del miglioramento si raggiunge nei primi 298 batch su 3047 (di un dataset 5000). Il resto è plateau dancing. | Eureka 2 |
| **Po2 ≠ plateau** | Po2 quantization NON determina il plateau (i pesi raw sono float). Determina solo la "forma" del dancing | Eureka 1 corretta |

---

## ⚙️ CLI args di `train.py` (post-STEP 2A)

### Training base
| Arg | Default | Esempio |
|-----|---------|---------|
| `--epochs` | 50 (config) | `--epochs 10` |
| `--batch_size` | 64 | `--batch_size 128` |
| `--seq_len` | 100 | `--seq_len 50` |
| `--lr` | 0.001 | `--lr 1e-3` |
| `--scheduler` | plateau | `--scheduler onecycle` |
| `--max_lr` (per onecycle) | 5e-3 | `--max_lr 2e-3` |
| `--T0` (per cosine) | 5 | `--T0 5` |
| `--optimizer` | adam | `--optimizer adamw` |
| `--smoke` | False | `--smoke` (1 epoca, n≤100) |
| `--tag` | 'run' | `--tag P9_S2A_fast` |

### Dataset (P10)
| Arg | Default | Esempio |
|-----|---------|---------|
| `--n_train` | 5000 | `--n_train 500` |
| `--n_val` | 500 | `--n_val 100` |
| `--scenario_mix` | 'default' | `--scenario_mix highway` |
| `--cut_in_ratio` | None (= config) | `--cut_in_ratio 0.0` |
| `--data_cache` | None | `--data_cache data/cache_500_highway_cut0.0.pt` |

### PINN loss
| Arg | Default (config) | Esempio |
|-----|-----------------|---------|
| `--lambda_data` | 1.0 | `--lambda_data 1.0` |
| `--lambda_phys` | 0.1 | `--lambda_phys 0.1` |
| `--lambda_ou` | 0.05 | `--lambda_ou 0.05` |
| `--lambda_bc` | 1.0 | `--lambda_bc 1.0` |
| `--lambda_sr` (B5) | 0.5 | `--lambda_sr 0.5` |

### Early stopping (P11)
| Arg | Default | Esempio |
|-----|---------|---------|
| `--early_stop_patience` | 0 (disabled) | `--early_stop_patience 2` |
| `--early_stop_delta` | 1e-4 | `--early_stop_delta 0.005` (STEP 2A) |

### Diagnostica
| Arg | Default | Esempio |
|-----|---------|---------|
| `--max_inf_streak` | 20 | `--max_inf_streak 20` |
| `--log_every` | 50 | `--log_every 50` |

### Da implementare per STEP 2B (NON ancora presenti)
| Arg | Significato |
|-----|-------------|
| `--cf_hidden_size` | Sovrascrive `CF_HIDDEN_SIZE` (default 32) — TBD STEP 2B |
| `--cf_rank` | Sovrascrive `CF_RANK` (default 8) — TBD STEP 2B |

---

## 🖼️ G1-G13 — Grafici diagnostici (in `plots/<TAG>/`)

### Per-epoca (G1-G7) — letti da `training_log.csv`
| Codice | Cosa mostra | Quando utile |
|--------|-------------|--------------|
| **G1** | Train/val total loss vs epoch | Visione globale convergenza |
| **G2** | Componenti loss val (data, phys, OU, bc, sr) | Capire quale termine domina |
| **G3** | LR schedule | Verifica scheduler (onecycle/cosine/plateau) |
| **G4** | grad_norm medio per epoca | Trend instabilità |
| **G5** | Scatter T_pred vs T_true (sul val set) | Quanto la rete riconosce il T |
| **G6** | Spike rate per epoca | Trend dead network vs saturation |
| **G7** | Violin plot dei 5 parametri predetti | Distribuzione vs bound fisici |

### Per-batch (G8-G12) — letti da `training_batch_log.csv` (T)
| Codice | Cosa mostra | Quando utile |
|--------|-------------|--------------|
| **G8** | gn pre/post clip per batch (scala log) | Vedere ESATTAMENTE quando esplode |
| **G9** | Heatmap log10(gn) per-layer × batch | Quale layer esplode PRIMA |
| **G10** | Componenti loss per batch (4-5 linee) | Quale termine diverge prima del totale |
| **G11** | Spike rate per batch (oscillazioni rapide) | Pattern saturazione vs degenerazione |
| **G12** | Max\|w\| globale per batch | Conferma che il clip mantiene pesi finiti |

### Per-trajectory (G13) — 3 PNG per scenario
| Codice | Cosa mostra |
|--------|-------------|
| **G13_traj_<scenario>.png** | Triplo subplot: V2V signals (TOP) / T_pred vs T_true (MID) / v0,s0,a,b predetti vs scenario constants (BOT). 3 traiettorie: highway, urban, highway_cutin |

---

## 🏷️ TAG dei run (convenzioni)

| Pattern | Significato |
|---------|-------------|
| `<NAME>_preflight_1` / `_2` | I 2 smoke del preflight (auto-generati da `scripts/preflight.py`) |
| `<NAME>_validation` | Smoke esteso post-preflight per validare config |
| `A1`, `A2`, `A3` (storici) | Run di confronto fra scheduler (onecycle/cosine/plateau) |
| `P6_T*` | Tier-N del piano P6 (T1=tier1, T2=tier2, ...) |
| `P9_S*` | Step-N del piano P9 (S1=highway-only, S2=capacity-increase) |
| `local_*` | Smoke locale per validazione, non per analisi |

---

## 🧮 Altri termini

- **ACC-IDM**: modello fisico = Adaptive Cruise Control IDM con base IIDM + CAH blend (Treiber Ch12 §12.4)
- **IDM**: 5 parametri `[v0, T, s0, a, b]` (free speed, time gap, min gap, accel max, decel max)
- **IDM-2d** (minuscolo): processo OU stocastico su T (Treiber Ch12 §12.6), NON un modello complessivo
- **IIDM**: Improved IDM (Treiber Ch12 §12.4), base del nostro ACC-IDM
- **CAH**: Constant Acceleration Heuristic (Treiber Eq.12.35), anticipa frenata leader
- **ALIF**: Adaptive Leaky Integrate-and-Fire neuron (con soglia adattiva via fatigue)
- **LI**: Leaky Integrator (output layer, no spike)
- **BPTT**: Backpropagation Through Time
- **Surrogate gradient**: derivata sostitutiva del Heaviside (la nostra è hardware-friendly, no propagation al threshold)
- **V2X**: Vehicle-to-Everything (i 4 segnali input: gap s, vel ego v, Δv = v−v_l, vel leader v_l)
- **PYNQ-Z1**: target FPGA hardware (Xilinx Zynq-7020)
- **PINN**: Physics-Informed Neural Network (loss = data + physics constraints)
- **OU**: Ornstein-Uhlenbeck (processo stocastico per T)

---

## 📋 Convenzioni di status nelle tabelle

| Marker | Significato |
|--------|-------------|
| `[ ]` | proposta, non implementata |
| `[~]` | in test |
| `[x]` | applicata |
| `[!]` | scartata definitivamente |
| ✅ | completato/funzionante |
| ⚠️ | warning/parziale |
| ❌ | fallito/scartato |
| ⏸️ | in stand-by / pianificato per futuro |
