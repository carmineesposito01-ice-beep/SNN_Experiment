# PRODIGY DEEP STUDY — parte 1: How it Works

> **Stato**: parte 1 (math + source walkthrough). Parte 2 (lessons learned dai 5 esperimenti diagnostici) sarà aggiunta al termine di R2.2.
>
> **Obiettivo**: capire COME funziona Prodigy, non trovare il best. Da chiudere solo con modello mentale completo che permetta di predire qualitativamente cosa Prodigy farà in setup nuovi.
>
> **Reference**: Mishchenko & Defazio 2024, "Prodigy: An Expeditiously Adaptive Parameter-Free Learner", arXiv:2306.06101. Source code: `prodigyopt==1.1.2` (`pip show prodigyopt`).

---

## 1. Cos'è Prodigy — riassunto in 3 righe

Prodigy è un ottimizzatore Adam-like che **auto-tunes il learning rate** durante il training senza richiedere all'utente di sintonizzarlo. Internamente mantiene uno stimatore `d` (D-adaptation) che approssima la distanza ottima dal punto iniziale; il vero passo applicato ai pesi è `dlr = d · lr_nominale`. L'utente dovrebbe lasciare `lr=1.0` e modificare solo `d_coef` se necessario.

In una riga: **`lr=1.0` è "nominale", il vero rate è `lr × d` dove `d` cresce auto durante il training**.

---

## 2. Math overview — D-adaptation in 1 minuto

### Il problema che risolve

In SGD/Adam, il learning rate ottimo `η*` dipende dalla scala della loss landscape, in particolare dalla distanza `D` tra il punto iniziale `x_0` e l'ottimo `x*`:

```
η* ≈ D / (G · √T)        (per SGD su funzioni Lipschitz)
```

dove `G` è la magnitudo tipica del gradiente e `T` il numero di step. Trovare `η*` richiede tipicamente grid search. Prodigy lo elimina **stimando D direttamente dai dati**.

### L'idea D-adaptation

Per ogni step `t`, Prodigy mantiene:
- `r_t = sum_{s ≤ t} γ_s · ⟨g_s, x_0 - x_s⟩` — correlazione cumulata tra gradiente e spostamento dall'inizio
- `s_t = sum_{s ≤ t} γ_s · g_s` — gradiente cumulato (analogo a momentum)

Allora `D ≈ r_t / ||s_t||` è un sano stimatore della distanza dall'ottimo. Lo stimatore viene aggiornato monotonamente: `d_max = max(d_max, d_hat)`, e `d = d_max` (mai decresce).

### Il vero step applicato

```
dlr = d · lr · bias_correction
update: p ← p - dlr · m_t / (√v_t + d·ε)         (Adam-style)
```

dove `m_t, v_t` sono i momenti Adam standard (con `(1-β)` rimpiazzato da `d · (1-β)` e `d² · (1-β2)` per stabilità numerica nel passaggio a regime).

**Conseguenza fondamentale**: quando `d ≈ 1e-6` (inizio), `dlr ≈ 1e-6 · lr_nominale`. Anche con `lr=1.0` il primo step è microscopico → **niente esplosione iniziale**.

---

## 3. Source code walkthrough (`prodigyopt/prodigy.py`)

Numerazione righe da `/c/Miniconda/Lib/site-packages/prodigyopt/prodigy.py` (v1.1.2).

### Stato per ogni parametro (init)

```python
state['s']        # accumulatore (eq. s_t sopra), zeros_like(p)
state['p0']       # copia di p al primo step (eq. x_0 sopra)
state['exp_avg']  # momentum Adam m_t
state['exp_avg_sq']  # variance Adam v_t
state['step']     # counter
```

### Stato globale (per ogni `step()`)

```python
group['d']            # stima corrente di D (parte a d0 = 1e-6)
group['d_max']        # max storico di d_hat (monotono crescente)
group['d_numerator']  # accumulatore r_t (decay con beta3 ogni step)
group['d_coef']       # coefficiente scaling user (default 1.0)
group['k']            # step counter globale
```

### Pseudocode del singolo step (semplificato)

```python
# Constants per step
beta3 = sqrt(beta2)              # default β3 ≈ 0.9995
dlr = d · lr · bias_correction

# === Phase 1: accumula numeratore e denominatore di d_hat ===
d_numerator *= beta3             # decay esponenziale del passato
delta_numerator = 0.0
d_denom = 0.0

for p in params:
    g = p.grad

    # Adam EMA con scaling d
    exp_avg.mul_(β1).add_(g, alpha=d·(1-β1))
    exp_avg_sq.mul_(β2).addcmul_(g, g, value=d²·(1-β2))

    # CORRELAZIONE GRADIENTE-DEVIAZIONE (cuore della D-adaptation)
    delta_numerator += (d/d0) · dlr · dot(g_sliced, p0 - p_current)

    # ACCUMULATORE s_t (denominatore di d_hat)
    if safeguard_warmup:
        s.mul_(β3).add_(g, alpha=(d/d0) · d)      # NO dlr
    else:
        s.mul_(β3).add_(g, alpha=(d/d0) · dlr)    # con dlr
    d_denom += s.abs().sum().item()

# === Phase 2: aggiorna d ===
d_hat = d_coef · (d_numerator + delta_numerator) / d_denom

if d == d0:                             # kickoff (solo primo step)
    d = max(d, d_hat)
d_max = max(d_max, d_hat)               # monotono crescente
d = min(d_max, d · growth_rate)         # cap multiplicativo per-step

# === Phase 3: applica step Adam con nuovo dlr ===
dlr = d · lr · bias_correction
for p in params:
    denom = sqrt(exp_avg_sq) + d·eps
    p.data.addcdiv_(exp_avg, denom, value=-dlr)
```

### Punti chiave da capire

1. **`d` non decresce mai** (è il max storico di `d_hat`). Solo cresce.
2. **`d_hat` è calcolato su TUTTI i param insieme** (somma globale di numerator e denom). Per reti piccole con grad concentrati, `d_denom` può restare basso → `d_hat` può schizzare.
3. **Il primo step usa `d = d0 = 1e-6`** → dlr microscopico → niente esplosione anche con lr=1.0.
4. **`safeguard_warmup=True`** rimuove `dlr` dall'accumulatore `s`. Questo serve quando `dlr` cresce rapidamente e gonfia artificialmente `s` → mantiene la stima di `d` più conservativa durante la fase di warmup naturale.
5. **`growth_rate=1.02`** previene jumps grandi di `d` in singolo step (kind of natural warmup). Default `inf` = no cap (rischio di salto repentino se d_hat schizza).

---

## 4. Iperparametri — guida pratica

| Param | Default | Cosa fa | Quando modificare |
|---|---|---|---|
| `lr` | `1.0` | Moltiplica `d` per ottenere `dlr`. Idealmente lasciare a 1.0 | Solo se Prodigy diverge anche con `safeguard_warmup` → ridurre a 0.5 o 0.1 |
| `betas=(0.9, 0.999)` | std Adam | Adam EMA decay | Mai (lasciali Adam-default) |
| `beta3=None` | `sqrt(beta2) ≈ 0.9995` | Decay del `d_numerator` storico | Mai (default OK) |
| `eps=1e-8` | std Adam | Stabilità numerica | Mai |
| `weight_decay=0` | — | L2 reg | Se serve, attivare con `decouple=True` |
| `decouple=True` | default ✅ | AdamW-style decoupled WD | Lasciare True |
| `use_bias_correction=False` | — | Adam bias correction sul `dlr` | OFF default, ma se si è in regime "early training" può aiutare |
| **`safeguard_warmup=False`** | OFF (!) | Rimuove `dlr` dal denominatore `s` per stabilità | **Attivare quasi sempre** (vedi §5 per failure mode) |
| `d0=1e-6` | — | Stima iniziale di D | Praticamente mai. Se la rete ha pre-training, può essere ridotto |
| **`d_coef=1.0`** | default | Scala diretta dello stimatore `d_hat` | Tuning principale. `<1.0` = brake, `>1.0` = accelerator |
| `growth_rate=inf` | no cap | Cap multiplicativo per-step su `d` | Valori `1.02` → smooth warmup naturale, raccomandato per training instabile |

**Regola sintetica del paper**: lascia tutto default + `lr=1.0` + `safeguard_warmup=True` + cosine annealing su `lr` post-warmup naturale.

---

## 5. Failure modes noti (e perché)

### F1 — d esplode al primo step

**Sintomo**: `d_hat` salta da 1e-6 a 10+ al primo step → ogni step successivo è enorme.

**Causa**: `d_denom = ||s_t||` con `s_t` calcolato sull'ultimo gradiente moltiplicato per `(d/d0) · dlr` (microscopico). Quindi `s` è quasi zero, `d_denom` quasi zero, `d_hat = numerator / 0 → ∞`.

**Fix**: `safeguard_warmup=True` (rimuove `dlr` dal moltiplicatore di `s`, mantiene `s` proporzionale al gradiente puro).

### F2 — d resta a d0 (frozen)

**Sintomo**: per tutto il training, `d ≈ 1e-6`, training quasi fermo, val_loss costante.

**Causa**: `delta_numerator = (d/d0) · dlr · ⟨g, p0 - p⟩` resta piccolo perché `d ≈ d0` mantiene il moltiplicatore a 1.0 ma `dlr ≈ 1e-6 · lr_nominale` è microscopico. Le correlazioni gradient-deviation sono dell'ordine `1e-6`, e `d_denom ~ 1e-6 · ||grad||`. Quindi `d_hat` resta basso, `d_max` non cresce, loop infinito.

**Trigger tipico**: pochi step totali (es. nostri 950 = 5 ep × 190 step). Prodigy paper raccomanda **>10k step** per warmup naturale.

**Fix**:
1. Più step totali (training più lungo)
2. Attivare `safeguard_warmup=True` (può aiutare ma non risolve sempre)
3. Aumentare `d_coef` (es. 2.0 o 5.0) per scalare lo stimatore
4. Verificare che il gradiente sia "robusto" (no NaN, no clip estremo)

### F3 — d cresce ma loss esplode

**Sintomo**: `d` cresce normalmente, ma a un certo punto loss diverge.

**Causa**: il gradient pattern cambia bruscamente a metà training (es. cambio di regime). Prodigy ha calibrato `d` per il regime iniziale e ora `dlr` è troppo alto per il nuovo regime.

**Fix**:
1. `growth_rate=1.02` (rallenta l'incremento di `d`)
2. Cosine annealing su `lr` esterno (Prodigy stesso non decresce mai `d`, ma `dlr = d · lr` cala se `lr` cala via scheduler)
3. `d_coef<1.0` (brake permanente)

---

## 6. Pattern attesi — la "scala"

Il pattern caratteristico di un Prodigy "in salute" (training lungo, safeguard attivo):

```
d
1.0 |                    ___________________________ plateau ~ d*
    |                ___/
0.1 |            ___/
    |        ___/
0.01|    ___/
    |   /
1e-3|  /  ← rapid early growth
    | /
1e-6|/  d0
    +----+----+----+----+----+----+----+----+
    0   1k   2k   3k   4k   5k   6k   7k   step
```

Lo schema "a scala" è dovuto al fatto che `d = d_max` è max-monotono: `d` salta in alto solo quando `d_hat` supera il record precedente. Senza `growth_rate`, gli step di crescita possono essere salti netti (scalini). Con `growth_rate=1.02`, la crescita è più liscia (esponenziale capped).

In parallelo:

```
lr_eff = d · lr
```

ha la stessa forma. Se applichiamo cosine annealing post-warmup, `lr_eff` ha forma:

```
lr_eff
       ___________
      /           \___
     /                \___
    /                     \___
   /                          \___
  /                               \___
 /                                    \___
+----+----+----+----+----+----+----+----+
     warmup naturale  | annealing cosine
```

Questa è la "scala" che l'utente ha visto in altri training Prodigy: warmup naturale (d cresce) + cosine annealing (lr nominale cala) = bell-shape.

---

## 7. Perché Prodigy nel nostro caso degenera in SGD lento

Dal sweep 4×11 (`EVENTPROP_OPTIMIZER_SWEEP.md`) e dai T30:

**Setup nostro**:
- 5 ep × 190 step = 950 step totali (sweep)
- 30 ep × 190 step = 5700 step totali (T30)
- lr=1.0 d_coef=1.0 → frozen (F2 failure mode)
- lr=0.1 d_coef=1.0 → meglio ma `d` resta a ~0.01 (sotto regime)
- lr=1.0 d_coef=0.1 → brake forte, `d` resta basso ma stabile

**Diagnosi pre-esperimento**: il numero di step è troppo basso per il warmup naturale di Prodigy (paper raccomanda >10k step per esempi simili). Inoltre noi NON abbiamo attivato `safeguard_warmup`, quindi `d_denom` è gonfiato da `dlr` micro, → numeratore/denominatore entrambi micro → `d_hat ≈ d` → `d` non cresce.

**Test diagnostici R2.2** verificheranno questa diagnosi.

---

## 8. Cosa ci aspettiamo nei 5 esperimenti diagnostici (R2.2)

| ID | Setup | Predizione |
|---|---|---|
| P-D1 | lr=1.0 d_coef=1.0 sched=none safeguard=False | `d` resta a 1e-6 (F2 frozen) per 10 ep |
| P-D2 | + safeguard_warmup=True | `d` cresce lentamente, forse raggiunge 1e-3 a ep10 |
| P-D3 | + cosine post 5ep + safeguard_warmup=True | warmup naturale + decay → pattern "scala" |
| P-D4 | lr=0.1 d=1.0 sched=none (nostra config attuale) | replica T30, `d` ~ 1e-2 plateau, equivalente a SGD lento |
| P-D5 | lr=1.0 d_coef=0.5 sched=none safeguard=True | brake medio, `d` cresce stably ma sotto P-D2 |

**Outcome atteso**: confermare che il problema è *durata di warmup* + *safeguard mancante*, NON Prodigy in sé.

Se confermato:
- Per task con <10k step, attivare safeguard E aumentare `d_coef` (2-5) → forza `d` a crescere più velocemente.
- Per task con >10k step, default+safeguard funziona.
- In ogni caso, mai usare `lr=1.0 d_coef=1.0 safeguard=False` con pochi step (failure mode F2 garantito).

---

## 9. Riferimenti

- Mishchenko & Defazio 2024, "Prodigy: An Expeditiously Adaptive Parameter-Free Learner", arXiv:2306.06101.
- D-adaptation original paper: Defazio & Mishchenko 2023, "Learning-Rate-Free Learning by D-Adaptation", arXiv:2301.07733.
- Source code: https://github.com/konstmish/prodigy (v1.1.2)
- Repository nostra: `EVENTPROP_OPTIMIZER_SWEEP.md` per i fallimenti Prodigy osservati nel nostro task (10/16 frozen)
- AUDIT: `document/AUDIT_2026-06-02.md` §2.2 ("Prodigy non aggiunge valore" → DICHIARAZIONE NON DIMOSTRATA, da rivalutare con questo studio)
