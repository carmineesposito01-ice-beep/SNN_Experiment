# EventProp Design — Branch `Training_Method_Exploration`

**Data**: 2026-06-01
**Branch base**: `main` HEAD `5a2c7ee`
**Riferimenti**:
- Wunderlich & Pehle, *"Event-based backpropagation can compute exact gradients for spiking neural networks"* (Sci. Rep. 2021)
- Repo reference: `lolemacs/pytorch-eventprop` (LIF MNIST classification, single layer)
- SNN-expert `ch08-surrogate-gradient.md` §8.4 (EventProp)

---

## 1. Motivazione

P14 ha chiuso il floor decomposition: `val~0.28` baseline scompone in `OU=19.3%` + `Po2=0.2%` + `SR=0.2%` + `interaction=1.9%` + **`residuo architettura/training=78.4%`**.

STEP 2E (Architecture_Exploration) ha testato 3 varianti finora (A1=0.2256, A2=0.2271, A3=0.2219) confermando che il muro NON è capacità (A2 con 2.85× parametri non migliora). **Tutte le 3 curve schiantano sullo stesso plateau ~0.225 entro epoca 3** e poi nessun progresso. Firma classica di **BPTT+surrogate-gradient bloccato in minimo locale** (gradiente troppo rumoroso/biased).

**EventProp** è il candidato fisico: calcola **gradienti esatti** event-based attraverso un sistema adjoint, senza approssimazione surrogate. Se il muro è davvero il gradiente surrogate, EventProp lo rompe.

---

## 2. Matematica EventProp (sintesi operativa)

### 2.1 Forward dynamics (LIF discreto)

Per ogni neurone post-sinaptico, due stati: corrente sinaptica `I` e potenziale di membrana `V`.

```
I[t] = (1 - dt/τ_s) · I[t-1] + Σ_j W_ij · s_j[t-1]      (synaptic current)
V[t] = (1 - dt/τ_m) · V[t-1] + (dt/τ_m) · I[t-1]        (membrane)
s[t] = Θ(V[t] - V_th)                                    (spike)
V[t] ← V[t] · (1 - s[t])     (hard reset; soft reset = V - V_th · s[t])
```

Convenzioni: `dt` = step size, `τ_m`, `τ_s` = costanti tempo. Soglia `V_th = 1.0` (fissa).

### 2.2 Backward adjoint (Wunderlich & Pehle Eq. 6–9)

Si introducono variabili adjoint `λ_V[t]`, `λ_I[t]` e si propaga il gradiente **all'indietro nel tempo**:

```
λ_V[t-1] = (1 - dt/τ_m) · λ_V[t]                                       [tra spike]
λ_I[t-1] = λ_I[t] + (dt/τ_s) · (λ_V[t] - λ_I[t])                        [tra spike]
```

**Jump alle spike times** (qui sta la magia event-based):

```
Δλ_V(t*) = [λ_V(t*+) + ∂L/∂s(t*)] / (V'(t*) - V_th)
```

Nella forma discreta di `lolemacs`:
```
λ_V[t] += s[t+1] · (λ_V[t+1] + grad_output[t+1]) / (I[t] - 1 + ε)
```

Gradiente sui pesi (sum over time):
```
∂L/∂W_ij = -Σ_t s_j_pre[t] · λ_I_i[t]      (j = presyn, i = postsyn)
```

Gradiente sull'input (per propagare a layer precedenti):
```
∂L/∂s_j_pre[t] = Σ_i W_ij · (λ_V_i[t+1] - λ_I_i[t+1])
```

### 2.3 Differenze vs SurrogateGradient

| | Surrogate | EventProp |
|---|---|---|
| Forma backward | `∂s/∂V ≈ γ · σ'(V-V_th)` ovunque (smooth surrogate) | `∂s/∂V = δ(V-V_th)` esatto + jump adjoint |
| Bias del gradiente | sì (dipende dalla forma surrogate) | no (esatto rispetto alla loss event-based) |
| Costo | uguale al forward | uguale al forward |
| Hardware-friendly | sì (deriv. semplice) | sì (eventi sparsi → backward sparso) |

---

## 3. Adattamento al nostro problema

### 3.1 Vincoli

| Aspetto | Status F2.0 (minimal) | Fasi successive |
|---|---|---|
| Hidden neuron model | **LIF puro** (no ALIF/fatigue) | F2.1 → ALIF |
| Recurrence | **OFF** (no rec_U/rec_V) | F2.2 → recurrent adjoint |
| Delayed synapses | **OFF** (no max_delay) | F2.3 → delay-aware adjoint |
| Po2 quantization | **OFF** | F2.3 → STE post-grad |
| Output | LI standard PyTorch (no spike → BPTT classico) | invariato |
| Loss | `pinn_loss` esistente (solo data per F2.0) | full PINN da F2.1 |

### 3.2 Architettura F2.0

```
Input (B, T, 4) ──► [direct current injection, no spike encoding] ──►
   LIFLayer_EventProp (4 → 32)        ◄── custom autograd.Function
   ──spikes (B, T, 32)──►
   LILayer_Standard (32 → 5)          ◄── PyTorch standard
   ──raw (B, T, 5)──►
   sigmoid + F5 scaling ──► params (B, T, 5)
```

**Insight chiave**: EventProp è custom **solo nella hidden LIF**. Il LI output è standard PyTorch, autograd compone i due naturalmente. Loss → backward grad arriva a LIFLayer.backward come `grad_output_spikes (B, T, 32)` → EventProp adjoint risolve `grad_input (B, T, 4)` + `grad_weight (32, 4)`.

### 3.3 Input encoding (decisione importante)

**Direct current injection**: il continuous input `x[t] ∈ R^4` viene moltiplicato per `W (32, 4)` direttamente come `I_external = W @ x[t]`. Niente conversione a spike. Pattern classico per task di regression con input continuo (vs MNIST dove i pixel sono spike binary).

Forma discreta:
```
I[t] = (1 - dt/τ_s) · I[t-1] + W @ x[t-1]          (al posto di W @ s_pre[t-1])
```

Adjoint resta identico, solo il gradiente sui pesi diventa:
```
∂L/∂W_ij = -Σ_t x_j[t] · λ_I_i[t]      (input continuo, non spike)
```

---

## 4. Roadmap incrementale

| Fase | Cosa | Obiettivo metrico | Test validazione |
|---|---|---|---|
| **F2.0** | LIF puro feedforward, no Po2, loss data-only | val < 0.225 vs A1 baseline (0.2256) entro 5 epoche | Smoke locale 5×190 step |
| **F2.1** | + ALIF fatigue/adaptive threshold | val < 0.220 entro 15 epoche | Re-test cache F2 |
| **F2.2** | + recurrence low-rank (rec_U·rec_V) | val ≤ F7 (0.2198) | Confronto deploy-realistic |
| **F2.3** | + Po2 (STE) + delays + scenari completi | val < 0.20 target deploy | Full sweep Azure |

**Stop condition**: se F2.0 NON batte 0.225 entro 5 epoche locali, EventProp non è la cura → riconsiderare strategia (encoding diverso, task reframing, o accettare floor).

---

## 5. Implementation notes (per implementatore)

### 5.1 Pattern `WrapperFunction` (da `lolemacs`)

```python
class WrapperFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input, weight, forward_fn, backward_fn):
        ctx.backward_fn = backward_fn
        pack, output = forward_fn(input, weight)
        ctx.save_for_backward(*pack)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        pack = ctx.saved_tensors
        grad_input, grad_weight = ctx.backward_fn(grad_output, *pack)
        return grad_input, grad_weight, None, None
```

Permette di scrivere `forward`/`backward` come metodi del Module, non come static. Pulito.

### 5.2 Shape conventions (nostre)

Tutto `(B, T, dim)` time-second (vs lolemacs `(B, dim, T)` time-last). Allinea con `CF_FSNN_Net.forward_sequence_with_stats()` esistente.

### 5.3 Silent neuron repair

`lolemacs` ha un trucco: durante training, se un neurone non spara mai nel batch, bump dei suoi pesi di +0.1. Lo riportiamo (utile per inizializzazione fragile).

### 5.4 Device-agnostic

`lolemacs` ha `.cuda()` hardcoded — sostituiamo con `device=input.device` ovunque.

### 5.5 Numerical guard

Il denominatore `(I[t] - 1 + ε)` può esplodere se `I[t] ≈ 1` (vicino alla soglia). Usiamo `clamp(min_abs=1e-3)` come safety (Wunderlich&Pehle §3.3).

---

## 6. Test plan F2.0

**Smoke locale** (CPU, ~15 min):
```bash
python train.py --arch_variant eventprop_lif \
    --epochs 5 --max_steps_per_epoch 190 \
    --batch_size 8 --val_batch_size 64 \
    --seq_len 50 --scheduler onecycle --max_lr 2e-3 --lr 2e-3 \
    --optimizer adamw \
    --scenario_mix highway --cut_in_ratio 0.0 \
    --cf_hidden_size 32 --noise_scale 0.0 --po2_enabled 0 \
    --lambda_data 1.0 --lambda_phys 0.0 --lambda_ou 0.0 --lambda_bc 0.0 --lambda_sr 0.0 \
    --data_cache data/cache_1500_highway_cut0.0_ou0.0.pt \
    --tag F20_eventprop_lif_smoke
```

**Confronto con baseline A1** (prime 5 epoche già osservate):
```
A1 (surrogate, po2=1):  0.347 → 0.240 → 0.228 → 0.228 → 0.227
F2.0 atteso:            ??? → ???  → ???  → ???  → < 0.225 ✅?
```

Se F2.0 finisce a val < 0.225 → segnale forte di direzione giusta → procediamo F2.1. Se finisce ≥ 0.230 → EventProp non basta da solo, serve ripensare loss/encoding.
