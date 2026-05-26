# CF_FSNN — Scelta del Modello di Car-Following per la PINN
> **Questo è il documento decisionale più importante del progetto.**
> Analisi degli use case UC0–UC15 vs modelli disponibili (Treiber & Kesting 2025).
> Aggiornato: 2026-05-25

---

## 1. La domanda

> "Quale modello di car-following devo usare come nucleo fisico della mia PINN?"

Il modello CF determina:
- **L'equazione del moto** usata nel termine `lambda_phys` della loss PINN
- **Il generatore di traiettorie sintetiche** per il training
- **I parametri che la rete deve predire** (`[v0, T, s0, a, b]`)
- **La capacità di gestire gli use case safety-critical** (UC2, UC10, UC11)

---

## 2. Candidati analizzati

### 2a. IDM puro (attuale, con estensione IDM-2D stocastica)
```
v̇ = a · [1 − (v/v₀)^δ − (s*(v,T)/s)²]
s*(v,T) = s₀ + max(0, v·T + v·Δv/(2·√(a·b)))
T(t) ∈ [T₁, T₂]  via processo OU, τ=30s  (IDM-2D stocastico)
```
**Vantaggi**: semplice, già implementato, 5 parametri noti.
**Difetti critici**:
- Reagisce a un cut-in con decelerazione istantanea → panic braking (Ch12, §12.4)
  - Esempio: gap scende da 30m a 8m in 0.5s → IDM calcola `v̇ ≈ −9 m/s²` immediatamente
  - In una ADAS reale questo causa discomfort grave o catena di frenate (UC2 FAIL)
- Non ha meccanismo di anticipazione: non usa informazioni su cosa sta facendo il leader
- String instability in CACC mode se T non è calibrato con cura (UC1, UC4)

### 2b. ACC-IDM (Treiber & Kesting, Ch12, Eq 12.35)
```
a_IDM = a · [1 − (v/v₀)^δ − (s*/s)²]      (componente IDM standard)
a_CAH = v² · ā_l / (v·ā_l/s + (v−v_l)²/(2s))  (Constant Acceleration Heuristic)
             dove ā_l = min(a_l, a)  [leader's clipped acceleration]

Se a_IDM ≥ a_CAH:
    a_ACC = a_IDM
Altrimenti:
    a_ACC = (1−c)·a_IDM + c·[a_CAH + b·tanh((a_IDM − a_CAH)/b)]
    con coolness c = 0.99
```
**Vantaggi**:
- Gestisce cut-in con risposta fluida (c=0.99 ≈ quasi sempre CAH)
- CAH = "il leader frenerà gradualmente" → risposta anticipatoria
- Riduce a IDM quando a_IDM ≥ a_CAH (free flow, no cut-in) → backward compatible
- Stessi 5 parametri [v0, T, s0, a, b] + costante fissa c=0.99
- String stability migliorata per CACC (Ch12, §12.5)

**Difetti**:
- Richiede `a_l` (accelerazione del leader) per il calcolo di CAH
  - Soluzione: `a_l[t] ≈ (v_l[t] − v_l[t−1]) / Δt` (calcolabile dalla sequenza V2X senza aggiungere input)
  - In alternativa: `a_l = 0` (conservative estimate) se non disponibile

### 2c. IIDM (Improved IDM, Ch12 §12.3.1)
```
v̇_free = a · [1 − (v/v₀)^δ]           (identico a IDM per v ≤ v₀)
z = s*(v,Δv) / s
Se z < 1:  v̇ = v̇_free · (1 − z²)
Se z ≥ 1:  v̇ = −a · (z² − 1) / (1 + z)²   (deceleration capped)
```
**Vantaggi**: rimuove la dispersione di v0 (i veicoli raggiungono effettivamente v0).
**Problema**: non risolve il cut-in (non ha CAH). Migliora UC1/UC4 ma non UC2.

### 2d. HDM (Human Driver Model, Ch13)
Aggiunge a IDM: reaction time Tr, errori di stima OU, multi-anticipazione.
**Troppo complesso** per essere il nucleo PINN. Utile come UC14 fallback model, non come core.

### 2e. Gipps' Model (Ch12)
Modello a doppia velocità (free + safe). 6 parametri. Non produce fisica PINN differenziabile.
**Non adatto** per training gradient-based.

---

## 3. Analisi UC → Modello

| Use Case | IDM puro | ACC-IDM | IIDM | Vincitore |
|----------|----------|---------|------|-----------|
| UC1 CACC sync | ⚠️ instabile a stringa | ✅ stabilità + anticip. | ✅ v0 preciso | ACC-IDM |
| **UC2 Cut-in abrupt** | **❌ FAIL (panico)** | **✅ CAH gestisce** | ❌ FAIL | **ACC-IDM** |
| UC3 Cut-in called | ⚠️ risposta brusca | ✅ | ⚠️ | ACC-IDM |
| UC4 Shockwave | ⚠️ amplifica onde | ✅ string-stable | ✅ | ACC-IDM |
| UC5 Classificazione | ✅ | ✅ | ✅ | indifferente |
| UC6 Crossroad | ✅ virtual leader | ✅ | ✅ | indifferente |
| UC7 Speed limit | ✅ (v0 adattivo) | ✅ | ✅ | indifferente |
| UC8 Hazard | ⚠️ | ✅ | ⚠️ | ACC-IDM |
| UC10 Semaforo rosso | ❌ FAIL (come UC2) | ✅ | ❌ FAIL | ACC-IDM |
| UC13 Pedone | ✅ virtual leader | ✅ | ✅ | indifferente |
| UC14 Degraded V2X | ⚠️ | ✅ (graceful degrad.) | ⚠️ | ACC-IDM |

**UC2 è il discriminante assoluto**: plain IDM fallisce per un sistema ADAS reale.

---

## 4. Raccomandazione

### MODELLO SCELTO: **ACC-IDM con estensione IDM-2D stocastica su T**

```
v̇(t) = ACC-IDM(s, v, Δv, v_l, a_l ; v0, T, s0, a, b, c=0.99)
T(t) ∈ [T1=0.8, T2=1.6]  via processo OU con τ=30s
```

**In sintesi**:
1. Il NUCLEO del modello fisico è **ACC-IDM** (non plain IDM)
2. Il parametro T è il time gap dell'ACC-IDM, con stochastic band [T1,T2] (IDM-2D)
3. Il coolness factor c=0.99 è FISSO (non predetto dalla rete)
4. I 5 parametri predetti dalla rete rimangono **identici**: `[v0, T, s0, a, b]`
5. **Nessun cambio all'architettura della rete** (4→32→5 rimane invariato)

---

## 5. Cosa cambia nell'implementazione

### 5a. config.py
```python
# Aggiungere:
ACC_COOLNESS = 0.99          # fattore coolness ACC-IDM (fisso, non appreso)
```

### 5b. train.py — funzione pinn_loss()
Sostituire il calcolo del residuo IDM:
```python
# PRIMA (IDM puro):
accel_idm = a * (1 - (v/v0)**4 - (s_star/s)**2)
residual = v_dot - accel_idm

# DOPO (ACC-IDM):
a_l = (v_l[1:] - v_l[:-1]) / DT      # stima a_l da sequenza (no new inputs!)
a_IDM = a * (1 - (v/v0)**4 - (s_star/s)**2)
a_l_clip = torch.minimum(a_l, a)       # ā_l = min(a_l, a)
a_CAH = v**2 * a_l_clip / (v * a_l_clip / s + (v - v_l)**2 / (2*s + 1e-6))
mask_IDM_wins = (a_IDM >= a_CAH).float()
a_ACC = mask_IDM_wins * a_IDM + (1-mask_IDM_wins) * (
    (1-c)*a_IDM + c*(a_CAH + b*torch.tanh((a_IDM - a_CAH)/(b + 1e-6)))
)
residual = v_dot - a_ACC
```
(~10 righe aggiuntive, nessun cambio strutturale)

### 5c. data/generator.py
Sostituire `idm_step()` con `acc_idm_step()` per generare traiettorie con cut-in.
Aggiungere scenari cut-in (gap riduzione brusca 30–60%) al loop di simulazione.

---

## 6. Cosa NON cambia

| Componente | Stato |
|-----------|-------|
| CF_FSNN_Net architettura | INVARIATA (4→32→5, ALIF+LI) |
| Parametri predetti [v0,T,s0,a,b] | INVARIATI |
| IDM-2D stocastico su T | INVARIATO (OU in [T1,T2]) |
| Normalizzazione input | INVARIATA |
| Loss PINN (struttura) | INVARIATA (solo formula fisica cambia) |
| TBPTT seq_len=100, stride=50 | INVARIATO |
| Hardware target PYNQ-Z1 | INVARIATO |

---

## 7. Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|------------|---------|-------------|
| a_l da differenze finite è rumoroso | ALTA | MEDIO | Applicare OU smoothing a a_l prima del CAH |
| CAH diverge se s→0 (epsilon nel denominatore) | MEDIA | ALTO | Aggiungere `1e-6` nel denominatore (già mostrato sopra) |
| Training più lento (più calcoli) | BASSA | BASSO | Overhead ~5% stimato |
| Mismatch tra ACC-IDM e dati reali | MEDIA | MEDIO | Validare con dataset UrbanIng-V2X disponibile in `dataset/` |

---

## 8. Decisione finale — Tabella sommario

```
+-------------------------------------------------------+
|  PINN CORE MODEL                                      |
|                                                       |
|  v̇ = ACC-IDM(params) + IDM-2D-T(band)               |
|                                                       |
|  Parametri predetti:  [v0, T, s0, a, b]              |
|  Parametri fissi:     c=0.99, T1=0.8, T2=1.6, τ=30s |
|  Use cases coperti:   UC1,2,3,4,5,6,8,10,13,14       |
|  Use cases parziali:  UC7,9,11,12,15                  |
+-------------------------------------------------------+
```

**Questa scelta è definitiva per il progetto corrente e non richiede
di cambiare l'architettura della rete né i parametri di output.
L'unica modifica è nella funzione di fisica della PINN loss e nel generatore.**
