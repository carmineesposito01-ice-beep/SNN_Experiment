# CF_FSNN — Analisi e Idee di Ottimizzazione
> Brainstorming completo basato sui risultati del primo training e sull'analisi architetturale.
> **Modello CF corrente**: ACC-IDM con base IIDM (ver. aggiornata rispetto al training iniziale con IDM puro).
> Aggiornato: 2026-05-25

---

## DIAGNOSI — Problemi identificati nel training attuale

### P1 — LR scheduler: ReduceLROnPlateau congela il training
- **Osservato**: best val_loss = epoca 1/20; val_loss identica tra ep.10 e ep.20 → LR = 0
- **Tre cause concorrenti**:
  1. SRMSE ha varianza alta (std=0.443) → il plateau è rumoroso → ReduceLROnPlateau si spaventa e abbassa LR a ogni oscillazione
  2. λ_bc=1.0 aggressivo nelle prime epoche → picchi di loss che mimano plateau
  3. LR iniziale (1e-3) è già nell'intorno del minimo locale all'epoca 1 → le epoche successive "scavalcano" quel minimo
- **Stato**: CRITICO — da correggere prima di qualsiasi altro esperimento

### P2 — Bias su v0: +16% e varianza compressa 2.2×
- **Osservato**: predicted mean(v0)=29.8 m/s vs true mean≈25.8 m/s
- **Causa ipotizzata**: IDM plain non permette ai veicoli di raggiungere v0 esatto → rete compensa con v0 più alto. Risolto parzialmente dal passaggio a IIDM (base ACC-IDM).
- **Stato**: IMPORTANTE — monitorare dopo cambio a ACC-IIDM

### P3 — Bias su T: +0.15 s e varianza compressa 4×
- **Osservato**: predicted T concentrato intorno a 1.27 s invece di [0.84, 1.58]
- **Causa**: λ_OU=0.05 non forza abbastanza la dispersione; collasso low-rank di rec_U×V verso rank-1
- **Stato**: IMPORTANTE — problema strutturale legato all'ottimizzatore

### P4 — SRMSE = 0.871 (target < 0.3)
- Conseguenza diretta di P1+P2+P3
- **Stato**: indicatore aggregato, non causa

### P5 — Nessun sistema di logging/visualizzazione
- Training cieco — nessun grafico prodotto
- **Stato**: PRIORITÀ ZERO per qualsiasi ottimizzazione futura

---

## VISUALIZZAZIONE — 7 Grafici di Diagnostica (I15)

**File da creare**: `utils/plot_diagnostics.py`
Generazione automatica a fine ogni training run.

| # | Grafico | Cosa rivela |
|---|---------|-------------|
| G1 | Loss totale train/val per epoca (scala log) | Convergenza, overfitting, plateau |
| G2 | 4 componenti loss (train) su unico asse | Quale termine domina o diverge |
| G3 | Learning rate schedule vs step | Comportamento effettivo dello scheduler |
| G4 | Grad norm per epoca | Instabilità gradiente (vanishing/exploding) |
| G5 | T_pred vs T_true scatter (500 campioni) | Bias sistematico, compressione varianza |
| G6 | Spike rate media hidden layer per epoca | Health indicator SNN — target: 10–20% |
| G7 | Violin plot [v0, T, s0, a, b] pred vs true | Deriva dei parametri, bias per distribuzione |

**Nota G6 — Spike rate**: Se i neuroni ALIF sparano < 5% → dead neurons → gradiente zero → rete non si aggiorna. Se > 50% → saturazione → nessuna codifica temporale. Il range 10–20% è il regime biologicamente ottimale per SNNs.

**CSV di logging** da salvare ad ogni epoca:
```
epoch | lr | train_total | train_data | train_phys | train_ou | train_bc
      | val_total | val_data | val_phys | val_ou | val_bc
      | grad_norm | spike_rate | T_mae | T_bias | time_s
```

---

## SCHEDULER DEL LEARNING RATE

### I1 — OneCycleLR ✅ RACCOMANDATO PRIMO ESPERIMENTO
```python
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=5e-3,
    steps_per_epoch=n_batches, epochs=EPOCHS,
    pct_start=0.3, anneal_strategy='cos'
)
```
- **Meccanismo**: Phase 1 (30% steps): LR cresce da min → max (warmup). Phase 2 (70%): LR scende max → min (cosine decay). Il LR che CRESCE nelle prime epoche è il meccanismo chiave — forza il modello a uscire dal minimo locale dell'epoca 1.
- **Connessione**: usato nel training di ResNet (super-convergence), LoRA fine-tuning di Stable Diffusion XL
- **Pro**: LR non può morire; esplora attorno al minimo locale iniziale
- **Con**: richiede n_batches noto prima del training
- **Status**: Stage A, Run A1

### I2 — CosineAnnealingWarmRestarts
```python
scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=5, T_mult=2)
```
- Restart ogni 5, 10, 20... epoche — evita trappole locali
- **Rischio**: warm restarts possono destabilizzare la componente PINN loss nelle prime epoche
- **Status**: Stage A, Run A2

### I3 — ReduceLROnPlateau (patch minima)
```python
scheduler = ReduceLROnPlateau(patience=10, factor=0.5, min_lr=1e-5)
```
- Zero modifiche strutturali, ma il problema fondamentale rimane
- **Status**: fallback se I1/I2 non convergono

---

## OTTIMIZZATORI — Analisi comparativa

### I4 — Lion (EvoLved Sign Momentum) — Google DeepMind 2023
**Formula:**
```
m_t  = β₁ · m_{t-1} + (1−β₁) · g_t          ← aggiorna momentum
Δw   = sign(β₂ · m_{t-1} + (1−β₂) · g_t)    ← update = SOLO IL SEGNO
w_t  = w_{t-1} − lr · (Δw + λ · w_{t-1})    ← con weight decay
```

**Parametri raccomandati:**
```
lr = 3e-4   (3–10× più piccolo di Adam)
β₁ = 0.9
β₂ = 0.99
λ  = 1e-2   (weight decay più alto di Adam)
```

**Perché rilevante per PYNQ-Z1:**
- Δw ∈ {-1, 0, +1} → se lr è potenza di 2 (es. 2⁻⁸ = 3.9e-4), l'aggiornamento dei pesi è un bit-shift condizionato → zero moltiplicatori su FPGA
- Un solo buffer momentum (Adam ne usa due) → 50% meno memoria optimizer state
- Usato per addestrare Gemini e PaLM (Google)

**Connessione neuromorfica — STDP binaria:**
Lo STDP biologico modifica le sinapsi in modo discreto: la sinapsi si rafforza o si indebolisce di un'unità fissa in base alla correlazione spike pre/post. Lion è matematicamente equivalente — ogni peso si sposta di ±lr indipendentemente dalla magnitudine del gradiente.

**Status:** da testare dopo stabilizzazione con OneCycleLR

### I5 — Muon (Momentum + Orthogonalization) — Keller Jordan 2024
**Formula:**
```
m_t = β · m_{t-1} + (1−β) · g_t
Δw  = orthogonalize(m_t)     ← Newton-Schulz iteration (5 passi)
w_t = w_{t-1} − lr · Δw
```

**Perché è cruciale per rec_U e rec_V:**
Il problema di compressione della varianza di T è direttamente legato al collasso del rango della matrice ricorrente `W_rec = U×V`. Con Adam, le colonne di U e V diventano linearmente dipendenti → tutti i neuroni fanno la stessa cosa → T collassa verso la media. Muon, orthogonalizzando i gradienti, preserva il rango della ricorrenza e diversifica le rappresentazioni.

**Pattern d'uso corretto:**
- Muon si applica SOLO ai layer matrice: `fc_weight`, `rec_U`, `rec_V`
- Per bias e threshold → Adam standard
- Questo è il pattern usato nel training di GPT-like models con Muon

**Connessione neuromorfica — Competizione laterale:**
L'orthogonalizzazione di Muon è l'equivalente matematico della competizione laterale (inibizione laterale) nei sistemi neurali biologici. I neuroni si "respingono" nello spazio delle rappresentazioni, massimizzando la diversità — esattamente ciò che serve per far sì che i 32 neuroni ALIF coprano l'intera distribuzione di T invece di collapsar verso la media.

**Status:** PRIORITÀ 2 — da implementare dopo OneCycleLR

### I6 — Prodigy (auto-LR)
```python
# pip install prodigyopt
from prodigyopt import Prodigy
optimizer = Prodigy(model.parameters(), lr=1.0)
```
- Stima automaticamente il LR ottimale — elimina Stage B dello sweep
- Molto usato per fine-tuning LoRA di Stable Diffusion
- **Contro:** oscura il comportamento del modello — meglio capire il sistema prima
- **Status:** esplorativo — dopo Stage A+B

### I7 — Combinazione Ibrida Muon+Lion (ORIGINALE)
Questa combinazione non è pubblicata per SNN car-following:
```python
optimizer = MuonPlusLion([
    {'params': [rec_U, rec_V],      'optimizer': 'muon'},   # preserva rango
    {'params': other_weights,        'optimizer': 'lion'},   # hardware-friendly
])
# Nessun Adam nel deployment → Adam accumula statistiche di II ordine non mappabili su FPGA
```
**Razionale:** Muon per le matrici ricorrenti (rango), Lion per il resto (bit-shift). Potrebbe essere una contribuzione originale al campo SNN+PINN.

---

## PESI DELLA LOSS PINN

### I8 — Warm-up graduale dei lambda (curriculum PINN)
```
Ep 1–5:   λ_phys=0.00, λ_ou=0.00  (solo dati + BC)
Ep 6–10:  λ_phys=0.05, λ_ou=0.02
Ep 11+:   λ_phys=0.10, λ_ou=0.05  (regime nominale)
```
- Prima la rete apprende la struttura dei dati, poi si allinea alla fisica
- **Status:** Stage B, esperimento B-phys

### I9 — Aumentare λ_OU per ridurre bias T
- λ_OU da 0.05 → sweep {0.1, 0.2, 0.5}
- **Rischio:** troppo alto crea conflitto con λ_data
- **Status:** Stage C, esperimento C2

### I10 — Huber Loss invece di SRMSE
```python
loss_data = F.huber_loss(a_pred, a_gt, delta=1.0)
```
- Meno sensibile ai picchi di accelerazione nelle traiettorie cut-in
- Richiede ri-tuning di λ_data
- **Status:** da valutare dopo Stage A

---

## MECCANISMI BIOLOGICI TRASLABILI IN HARDWARE

### I11 — Regolarizzazione Omeostatica del Firing Rate
**Biologia:** Se un neurone corticale spara troppo, attiva meccanismi intracellulari che riducono la sua eccitabilità (downregulation canali Na⁺). Il cervello mantiene il firing rate in range ottimale (10–20%) per massimizzare la capacità informativa del codice neurale.

**Implementazione:**
```python
L_homeo = λ_h · mean((spike_rate_hidden − r_target)²)
# r_target ≈ 0.10 (10% dei tick)
# λ_h ≈ 0.01
loss += L_homeo
```
- Previene dead neurons e neuroni sempre attivi
- Su FPGA: spike rate calcolato comunque durante inferenza → zero overhead aggiuntivo
- **Status:** da aggiungere a partire da Stage B

### I12 — Curriculum Learning Biologico
**Biologia:** Il sistema nervoso impara prima le rappresentazioni semplici (riflessi → cortex motoria → prefrontale). Non espone il neonato a compiti cognitivi complessi prima che le basi siano consolidate.

**Implementazione a 3 stage:**
```
Stage 1 (ep  1– 5): solo HIGHWAY — dinamica lenta e regolare; seq_len = 50
Stage 2 (ep  6–15): + URBAN — variazioni medie;               seq_len = 75
Stage 3 (ep 16–30): + TRUCK + MIXED + cut-in;                 seq_len = 100
```
La progressione del seq_len è critica: sequenze corte → gradiente stabile → la rete impara prima i parametri "medi" poi raffina.
- **Status:** da implementare nel generatore — MEDIO termine

### I13 — Metaplasticità e Weight Decay Adattivo (BCM 1982)
**Biologia (BCM — Bienenstock-Cooper-Munro):** La soglia di apprendimento sinaptico dipende dalla storia di attivazione recente. Sinapsi molto usate diventano meno plastiche; sinapsi inattive diventano più plastiche.

**Implementazione:**
```python
# Peso grande → molto usato → weight decay alto
# Peso piccolo → poco usato → weight decay basso
wd_effective_i = wd_base * tanh(|w_i| / w_scale)
```
Diverso da L2 standard (stesso λ a tutti i pesi). Si implementa nel custom optimizer step.
- Su PYNQ-Z1: i pesi Po2 con magnitudine maggiore ricevono più regolarizzazione → si stabilizzano prima del deployment
- **Status:** sperimentale — solo dopo stabilizzazione training base

### I14 — Neuromodulazione: Layer-wise Learning Rate
**Biologia:** La dopamina modula selettivamente la plasticità sinaptica — alcune aree cerebrali cambiano velocemente durante l'apprendimento, altre rimangono stabili.

**Implementazione:**
```python
optimizer = Adam([
    {'params': model.layer_hidden.fc_weight.parameters(),            'lr': lr * 1.0},
    {'params': [model.layer_hidden.rec_U, model.layer_hidden.rec_V], 'lr': lr * 0.3},  # lenta: modella OU τ=30s
    {'params': model.layer_hidden.delays.parameters(),               'lr': lr * 0.5},
    {'params': [model.layer_hidden.cell.base_threshold,
                model.layer_hidden.cell.thresh_jump],                'lr': lr * 2.0},  # veloce: adatta eccitabilità
    {'params': model.layer_out.fc_weight.parameters(),               'lr': lr * 1.5},  # veloce: mapping spike→params
])
```
**Razionale:**
- Ricorrenza lenta (0.3×): W_rec modella correlazioni temporali lente (τ_OU=30s) → deve cambiare lentamente
- Soglie veloci (2×): la soglia ALIF è l'eccitabilità neuronale → risponde velocemente alle statistiche del dataset
- Output veloce (1.5×): il mapping da spike a parametri ACC-IDM deve adattarsi rapidamente

---

## GENERATORE DI DATI

### I15 — Scenari cut-in (CRITICO per ACC-IDM)
- Attualmente: solo car-following regolare → rete non esposta a UC2
- **Da aggiungere:** evento cut-in = riduzione brusca di `s` del 30–60% in 0.5–1.0 s con profilo realistico (non step, ma rampa)
- Il generatore deve tracciare `a_l` (accelerazione leader) per la formula CAH
- **Status:** NECESSARIO per il training con ACC-IDM (non opzionale)

### I16 — Bilanciare scenario mix per ridurre bias v0
- Attuale: highway=50%, urban=30%, truck=10%, mixed=10%
- `v0_mean ≈ 26.3 m/s` vs predicted 29.8 → verifica se la mix è effettivamente applicata
- Considerare: highway=40%, urban=35%, truck=15%, mixed=10%
- **Status:** diagnosi con statistiche generatore prima di agire

### I17 — Homeostatic Regularization su output parametri
```python
reg_homeo = torch.mean((predicted_params.std(dim=0) − true_params_std)**2)
loss += λ_homeo * reg_homeo
```
- Attacca direttamente P2 e P3 (varianza compressa)
- Richiede statistiche del dataset calcolate a priori
- **Status:** da testare in Stage C

---

## PIANO DI SPERIMENTAZIONE

### Stage A — Fix scheduler (≈ 1.5h, 3 run × 5 epoche con n_train=200)

| Run | Scheduler | Config |
|-----|-----------|--------|
| A1 | OneCycleLR | max_lr=5e-3, pct_start=0.3 |
| A2 | CosineAnnealingWarmRestarts | T_0=5, T_mult=2 |
| A3 | ReduceLROnPlateau (baseline) | patience=10, factor=0.5 |

**Criterio successo:** val_loss scende monotonicamente dopo ep.1 AND pendenza < 0 a ep.5.

### Stage B — Sweep LR con miglior scheduler di Stage A (≈ 1.5h, 3 run × 5 epoche)

| Run | LR iniziale | Note |
|-----|------------|------|
| B1 | 3e-4 | conservativo |
| B2 | 1e-3 | baseline |
| B3 | 3e-3 | aggressivo |

### Stage C — Sweep lambda PINN con best (scheduler, LR) (≈ 2h, 4 run × 5 epoche)

| Run | λ_data | λ_phys | λ_OU | λ_bc | Razionale |
|-----|--------|--------|------|------|-----------|
| C1 | 1.0 | 0.1 | 0.05 | 1.0 | Baseline |
| C2 | 1.0 | 0.1 | 0.20 | 0.5 | OU↑ BC↓ → riduce bias T |
| C3 | 2.0 | 0.05 | 0.20 | 0.3 | Data-first: priorità fit accelerazione |
| C4 | 1.0 | 0.2 | 0.10 | 0.5 | Phys↑ → coerenza ACC-IDM |

**Tempo totale Stage A+B+C:** ~5 ore in una mattinata.

---

## PRIORITÀ DI IMPLEMENTAZIONE

| Priorità | Intervento | Costo | Impatto atteso |
|----------|-----------|-------|----------------|
| **P0** | Logging CSV + 7 grafici (I15) | MEDIO | Indispensabile — senza questo è navigazione cieca |
| **P1** | OneCycleLR (I1) | BASSO | Risolve "best=epoch 1" nel 90% dei casi |
| **P2** | Muon per rec_U, rec_V (I5) | MEDIO | Risolve collasso varianza T strutturalmente |
| **P3** | Cut-in nel generatore (I15) | MEDIO | Indispensabile per ACC-IDM + UC2 |
| **P4** | Curriculum learning (I12) | MEDIO | Migliora strutturalmente qualità modello |
| **P5** | Layer-wise LR (I14) | BASSO | Stabilizza training senza costo architetturale |
| **P6** | Regolarizzazione omeostatica (I11) | BASSO | Previene dead neurons |

### Cosa NON fare subito
- **Prodigy:** utile, ma oscura il comportamento del modello. Capire prima cosa succede.
- **Aumentare λ a caso:** senza i grafici non si sa quale componente domina. Osservare prima.
- **Hidden size 32→64:** 864 parametri è azzeccato per PYNQ-Z1. Aumentare richiederebbe riprogettare il deployment.
- **Adam nel deployment finale:** Adam accumula statistiche di II ordine non mappabili efficientemente su FPGA. La combinazione target è Muon+Lion.

---

## ARCHITETTURA — Solo dopo stabilizzazione training

### I18 — Aggiungere a_l come 5° input (opzionale)
- Se ACC-IDM è il modello, CAH richiede `a_l` (acc. leader)
- Alternativa preferita: calcolarlo internamente nella loss senza cambiare CF_INPUT_SIZE=4
- **Status:** legato al design della pinn_loss() per ACC-IDM

### I19 — Aumentare hidden size (32 → 64)
- Solo se SRMSE con 32 neuroni non scende sotto 0.4 dopo ottimizzazione training
- **Attenzione:** su PYNQ-Z1 il limite è la BRAM; 64 neuroni potrebbero richiedere verifica
- **Status:** ultima ratio

---

> **Documenti correlati:**
> - `cf_model_recommendation.md` — analisi completa ACC-IDM vs IDM
> - `use_cases.md` — UC2 (cut-in) è il requisito safety-critical che guida I15
> - `training_plan.md` — piano esecutivo completo con configurazione per piattaforma
