# PRODIGY DEEP STUDY

> **Stato**: parte 1 (math + source walkthrough) **+ parte 2 (community wisdom multi-fonte)**. Parte 3 (lessons dai nostri esperimenti R2.2) sarà aggiunta dopo.
>
> **Obiettivo**: capire COME funziona Prodigy, non trovare il best. Da chiudere solo con modello mentale completo che permetta di predire qualitativamente cosa Prodigy farà in setup nuovi.
>
> **Reference**: 
> - Paper: Mishchenko & Defazio 2024, "Prodigy: An Expeditiously Adaptive Parameter-Free Learner", arXiv:2306.06101 (ICML 2024)
> - Source code: `prodigyopt==1.1.2`, `https://github.com/konstmish/prodigy`
> - GitHub Issues #3, #8, #10, #18, #27 (community wisdom dagli sviluppatori e da practitioner)
> - OneTrainer Wiki "Optimizers" sezione Prodigy
> - kohya-ss/sd-scripts community (LoRA training settings)
> - `prodigy-plus-schedule-free` (LoganBooker, variante moderna 2025)
> - DeepWiki konstmish/prodigy Usage Guide

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

---

# PARTE 2 — Community wisdom multi-fonte (verità incrociate)

> Questa parte rilegge la parte 1 alla luce di evidenza pratica raccolta da: GitHub Issues konstmish/prodigy (#3, #8, #10, #18, #27), OneTrainer Wiki, kohya-ss community, `prodigy-plus-schedule-free` (LoganBooker 2025). Alcune mie predizioni di parte 1 sono state **confermate** da fonti, altre **corrette/raffinate**, una **ribaltata**.

## 10. Le 4 verità ufficiali confermate da konstmish (sviluppatore)

Dalle risposte dirette di Konstantin Mishchenko negli issue:

### V1 — "Senza scheduler, Prodigy è agnostico al numero di epoche" (Issue #3)
> *"the optimizer is completely agnostic to how long you run it for, it should have exactly the same behavior after a fixed number of epochs. In other words, the optimizer is not aware of the total number of epochs when there is no scheduler."*

**Implicazione**: se `scheduler=none`, il pattern "impara solo a fine training" osservato dagli utenti è dovuto al fatto che `d` impiega del tempo a calibrarsi, NON a una qualche awareness del numero totale step. Se si raddoppia il numero step con `scheduler=none`, il modello continua semplicemente a migliorare da dove era arrivato (a meno di plateau intrinseco).

### V2 — "Se d resta troppo piccolo, aumenta d0" (Issue #27, confermato da konstmish)
LoganBooker propose, konstmish accettò ufficialmente (chiuse l'issue):
> *"If `d` rises very slowly or not at all, you might need to bump up `d0` (to say, 1e-5 or 1e-4). I've found sometimes Prodigy just needs to get a larger read of the gradients to start with, otherwise it can take quite a few steps before it finds a good LR, by which point you're already a good portion through training."*

L'utente turbo-boo confermò: *"I set d0 from 1e-6 to 1e-5 and prodigy seems to be working well!"*

Konstmish: *"Thanks for sharing your experience and a especially thanks to @LoganBooker for giving a solution to the problem. I'll also add a comment on changing `d0` in the readme."*

**Implicazione critica per il nostro caso**: il default `d0=1e-6` è MOLTO conservativo. Se il training ha pochi step (<5000) e/o reti piccole con gradienti concentrati, `d` può semplicemente non avere tempo di salire dal valore microscopico iniziale a un regime utile.

### V3 — "Cosine annealing è raccomandato. T_max=total_steps. Niente restarts" (Issue #8, Issue #10)
> *"We recommend having no restarts, which corresponds to setting T_max in cosine annealing to the total number of steps the scheduler.step() is called. If you decide to use restarts, make sure to set safeguard_warmup=True."*

E in #10 (immagine inclusa di lr trajectory): T_max=1050 → cosine annealing pulito dall'inizio fino a near-zero. Prodigy lavora sopra questa scala.

In #8 konstmish suggerisce ANCHE: *"I'd suggest trying PolynomialLR with power=1.0, it seems to be quite helpful when using Adam."* (alternativa a cosine)

### V4 — "Prodigy è una variante di Adam" (Issue #18, konstmish)
> *"Prodigy is based on Adam/AdamW, which works better with cosine annealing."*

E:
> *"Prodigy itself is a variant of Adam with on-the-fly estimation of the learning rate."*

Conferma: Prodigy = AdamW + D-adaptation. Tutto quello che Adam fa, Prodigy fa, più auto-tuning di `dlr`.

---

## 11. La community wisdom non documentata (verificata da practitioner)

Pratiche che la community ha verificato sperimentalmente e che gli sviluppatori hanno accettato/raccomandato successivamente:

### W1 — `betas=(0.9, 0.99)` produce miglioramenti drammatici (Issue #8 madman404 → community)

Madman404 (Issue #8, 2023-11-09):
> *"the parameters that worked for me were betas of (0.9, 0.99), weight_decay of .1, and batch size of 5 over about 1000-2000 steps. ... I suspect the most important parts were the lowered beta2 (which, as far as I can tell, should improve 'remembering' details from previous steps) and raised weight decay."*

Brandostrong (originale issue): *"Wow. Your betas suggestion is a dramatic improvement, thank you."*

**Spiegazione tecnica** (LoganBooker, Issue #27): *"If beta3 is not set explicitly, then beta2 ** 0.5 is used in its place, so beta2 affects more than just the second moment."*

Cioè: `beta2=0.999 → beta3=0.9995` (decay molto lento del numeratore `d_numerator`). Cambiando a `beta2=0.99 → beta3=0.995`, il decay è 10× più reattivo → Prodigy "vede" più velocemente la dinamica corrente, `d` cresce più rapidamente, lo stimatore è meno laggy.

> **Caveat (phageous, Issue #8, 2024-11)**: su Flux1.dev anime LoRA, `betas=(0.9, 0.99)` causa Prodigy a NON imparare colori capelli chiari. Su task fine-grained colori, il "memoria corta" può perdere dettagli sottili.

### W2 — `d_coef=2` per accelerare convergenza (community-consensus, bdsqlsz, OneTrainer)

Il default `d_coef=1.0` produce un'estimazione di `d` "conservativa". Tutta la community LoRA training raccomanda `d_coef=2`:
- bdsqlsz (Civitai, kohya rentry): `d_coef=2` parte del setup "Prodigy is ALL YOU NEED"
- OneTrainer wiki: "D coefficient of 0.5 will slow Prodigy while a D coefficient of 2 will speed it up"
- DarkAlchy (Issue #3) confermò: dopo settimane di fallimenti con default, `d_coef=2 + use_bias_correction=True + safeguard_warmup=True` ha funzionato.

`d_coef` scala direttamente la stima `d_hat = d_coef * d_numerator / d_denom`, quindi raddoppiando si accelera la salita verso il regime ottimale.

### W3 — `use_bias_correction=True` è universalmente raccomandato

Default `False` (off) nel codice. README ufficiale per diffusion: *"set use_bias_correction=True"*. OneTrainer: *"Recommended True"*. Community: tutti lo attivano.

Effetto tecnico (source code): `bias_correction = sqrt(1-beta2^(k+1)) / (1-beta1^(k+1))`, applicato a `dlr`. Per i primi step quando `k` è piccolo, bias_correction è maggiore di 1 → dlr leggermente boosted → d esce più velocemente dal regime micro iniziale.

### W4 — `weight_decay=0.01` (AdamW default) > `weight_decay=0` per evitare overtraining

Tutte le fonti raccomandano weight_decay non-zero per Prodigy:
- konstmish (Issue #3): *"AdamW's default value of weight decay is 0.01. I'd suggest trying weight_decay=0.01 or weight_decay=0.05."*
- OneTrainer: *"Recommended 0.001 to 0.01"*
- community kohya: 0.01 default

**Razionale**: Prodigy + nessuno scheduler → `dlr` cresce monotonamente. Senza wd, weights divergono nel tempo → overfitting / overtraining nella seconda metà del training. WD = freno che lascia espressività a `dlr` ma stabilizza la norma dei pesi.

### W5 — Diagnostic principale: monitorare `d` E la norma dei pesi (LoganBooker, prodigy-plus-schedule-free FAQ)

> *"Don't observe only d (LR calcolato da Prodigy). Track also weight norm: its growth rate decreases over time. Log: `group['effective_lr'] * group['d']` per rappresentazione accurata."*

Combinazione di metriche:
- `d` o `lr_eff = d × lr`: dovrebbe crescere/plateau
- `||w||`: dovrebbe crescere all'inizio, poi stabilizzarsi
- Train loss: monotono decrescente (dopo iniziale assestamento)

Se `d` cresce ma `||w||` esplode → `d_coef` troppo alto, ridurre. Se `d` non cresce ma `||w||` cambia poco → `d0` troppo basso, aumentare.

### W6 — Numero step minimo: ~200-300 per "warmup naturale", 1000+ per regime stabile

LoganBooker (Issue #27, con grafico tensorboard SDXL Unet): *"the Unet took until steps 200-300 to find a decent LR, and even then it continued to search."*

Madman404 (Issue #8): *"about 1000-2000 steps"* (regime LoRA tipico).

**Implicazione**: training con <500 step sono al limite del praticabile per Prodigy default. <200 step sono sicuramente troppi pochi.

### W7 — Discrepanza safeguard_warmup True vs False

Esiste una **discrepanza reale** tra README ufficiale e community:
- README ufficiale (diffusion section): `safeguard_warmup=True`
- bdsqlsz / kohya rentry "Prodigy is ALL YOU NEED": `safeguard_warmup=False`
- OneTrainer: `True?` (con punto interrogativo, segno di incertezza)
- konstmish (Issue #8): True solo se restarts O linear warmup

**Risoluzione**: `safeguard_warmup` rimuove `dlr` dal moltiplicatore di `s` (denominatore di `d_hat`). 
- Con linear warmup esterno (lr cresce nei primi step): TRUE evita che dlr piccolo iniziale gonfi artificialmente s → d esagerato.
- Senza warmup esterno e con scheduler stabile: FALSE è OK (defaults paper).
- Con cosine annealing standard senza warmup: ambiguo (FALSE secondo paper, TRUE per sicurezza).

**Decisione pratica**: in dubbio, TRUE. Non c'è downside documentato.

---

## 12. Setup canonico CONSOLIDATO dalla community

Sintetizzando paper + sviluppatori + community + practitioner consolidati (kohya-ss + OneTrainer + Civitai bdsqlsz tutorial), il **setup "Prodigy is ALL YOU NEED"** è:

```python
optimizer = Prodigy(
    model.parameters(),
    lr=1.0,                           # MAI cambiare (nominale)
    betas=(0.9, 0.99),                # beta2 da 0.999 a 0.99 — DRAMATIC IMPROVEMENT (W1)
    weight_decay=0.01,                # AdamW default (W4)
    decouple=True,                    # default Prodigy (AdamW-style WD)
    use_bias_correction=True,         # boost early steps (W3)
    safeguard_warmup=True,            # safer default (W7)
    d_coef=2.0,                       # accelera convergenza (W2)
    d0=1e-6,                          # default; AUMENTA a 1e-5 / 1e-4 se d frozen (V2)
    growth_rate=float('inf'),         # default; valori 1.02 per smoother
)

# Scheduler raccomandato:
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer, T_max=total_training_steps  # senza restarts (V3)
)
```

**Numero step**: minimo 1000, ideale 5000+. <500 step → Prodigy in regime "warmup non completato".

---

## 13. Failure modes mappati (verità da fonti incrociate)

Tabella aggiornata vs parte 1 §5 con evidenza da issue:

| Failure | Sintomo | Causa documentata | Fix raccomandato (fonte) |
|---|---|---|---|
| F1 (mio in parte 1) | `d_hat` esplode al primo step | `d_denom` ≈ 0 con `dlr` micro | **RIBALTATO**: in pratica non osservato (d0 micro = dlr micro = s micro, MA delta_numerator anche micro → d_hat resta a d0). safeguard_warmup è precauzione, non fix obbligatorio per primo step. |
| F2 (mio in parte 1) | `d` frozen al valore d0 per tutto training | d0 troppo basso vs gradient scale | ✅ **CONFERMATO** (konstmish + LoganBooker, Issue #27): aumenta d0 a 1e-5 o 1e-4. Alternativa: aumenta d_coef. |
| F3 (community) | "impara solo nelle ultime epoche" con cosine | d ha bisogno di tempo per calibrarsi + cosine forza decay finale | (a) Aumenta d0, (b) Aumenta d_coef, (c) betas=(0.9, 0.99) per beta3 più reattivo (W1) |
| F4 (community) | Convergence per LoRA: 80 ep stragglini | Stessa F3, con d_coef=1.0 e default betas | Setup kohya canonical (§12) |
| F5 (community, Issue #8) | Overtraining tardivo (ottimo a metà, peggio a fine) | dlr cresce monotonamente senza freno, weights divergono | Cosine annealing + weight_decay=0.01 |
| F6 (phageous, Issue #8) | Perdita di dettagli fine-grained con beta2=0.99 | Memoria troppo corta | Mantenere beta2=0.999 per task fine-grained |
| F7 (LoganBooker) | LR cresce ma loss NaN | `d_coef` troppo alto in run lungo | Riduci d_coef, oppure `prodigy_steps>0` per freeze dopo N step (`prodigy-plus-schedule-free`) |

---

## 14. Cosa abbiamo SBAGLIATO finora nei nostri esperimenti

Riguardando i nostri sweep (SW + T30) con questa lente:

**Errori di setup confermati** (rispetto al canonical kohya/community):

| Param | Nostro valore | Canonical kohya | Severità |
|---|---|---|---|
| `betas` | `(0.9, 0.999)` (default) | `(0.9, 0.99)` | **ALTA** — beta3=0.9995 troppo lento per 1000 step |
| `d_coef` | `1.0` (default) | `2.0` | **ALTA** — d non sale abbastanza |
| `d0` | `1e-6` (default) | `1e-6` ma aumentare se frozen | **ALTA** — sintomo F2 osservato (frozen) → andava bumped |
| `use_bias_correction` | `False` (default) | `True` | MEDIA — early boost mancante |
| `weight_decay` | `1e-4` (hardcoded in train.py) | `0.01` | BASSA — più aggressivo a regime |
| `lr` | `0.1` o `1.0` testati | `1.0` | OK (provato entrambi) |
| `safeguard_warmup` | `True` (hardcoded) | `True` | OK |
| `scheduler` | `none` | `cosine T_max=total` | **ALTA** — niente schedule fa overtraining + non aiuta convergenza finale |
| step totali | 950 (SW) / 5700 (T30) | 1000+ minimo | OK ma al limite |

**Diagnosi del nostro Failure (T30 Prodigy)**:
1. `d_coef=1.0` + `betas=(0.9,0.999)` + `d0=1e-6` + scheduler=none
2. Numero step (5700) borderline-OK
3. Combinazione: Prodigy non raggiunge mai il regime D-adattato, resta in regime "SGD con lr piccolo"
4. Conferma: `prodigy_d` ~ 0.001 in tutti i T30 Prodigy run

**Tre cose da provare PRIMA di concludere "Prodigy non aiuta"**:
1. **Setup canonical kohya** completo (betas + d_coef=2 + use_bias_correction + cosine T_max + d0=1e-5 if frozen)
2. **Training più lungo** (10k+ step) se la rete lo tollera
3. **Monitorare DAVVERO `d`** per-batch nel CSV (già abilitato) per vedere se sale o resta a 1e-3

---

## 15. Riferimenti consolidati (parte 2)

### Repository / source code
- https://github.com/konstmish/prodigy (v1.1.2, ufficiale)
- https://github.com/LoganBooker/prodigy-plus-schedule-free (variante moderna 2025, defaults migliorati)

### GitHub Issues con risposte dello sviluppatore
- [Issue #3](https://github.com/konstmish/prodigy/issues/3) — DarkAlchy "doesn't begin to really learn until almost done" (V1, V4, W2 spiegati da konstmish)
- [Issue #8](https://github.com/konstmish/prodigy/issues/8) — brandostrong "low steps per epoch" → konstmish (V3) + madman404 (W1, W4) + community recommendations
- [Issue #10](https://github.com/konstmish/prodigy/issues/10) — josemerinom "T_max value cosine" → konstmish risposta con plot (V3)
- [Issue #18](https://github.com/konstmish/prodigy/issues/18) — ppbrown "convergence question SDXL" → konstmish (V4)
- [Issue #27](https://github.com/konstmish/prodigy/issues/27) — Bocchi-Chan2023 "SD 3.5 Medium" → LoganBooker (V2, W5, W6) + konstmish (acceptance)

### Community resources
- [OneTrainer Wiki — Optimizers](https://github.com/Nerogar/OneTrainer/wiki/Optimizers) — recommended settings practitioner-validated
- [kohya-ss/sd-scripts community](https://github.com/kohya-ss/sd-scripts/) — setup "Prodigy is ALL YOU NEED"
- [LoganBooker prodigy-plus-schedule-free README](https://github.com/LoganBooker/prodigy-plus-schedule-free) — variante 2025 con defaults migliorati e FAQ

### Paper
- Mishchenko & Defazio 2024, ICML, arXiv:2306.06101
- Defazio & Mishchenko 2023, D-Adaptation original, arXiv:2301.07733

---

# PARTE 3 — Lessons dai nostri esperimenti R2.2

## 16. Risultati 5 esperimenti diagnostici (10 ep × 100 step)

| Exp | Lever isolato | val_total best | val_data @best | d_start | d_max | lr_eff end | spike rate avg |
|-----|---|---:|---:|---:|---:|---:|---:|
| **P-A** | Baseline (default Prodigy lib) | **0.3026** ❌ | 0.2921 | 1e-6 | 0.017 | 1.74e-02 | 9.5% |
| **P-B** | + `betas=(0.9, 0.99)` (W1) | **0.2279** ✅ | 0.2227 | 1e-6 | **0.096** | 9.57e-02 | 19.5% |
| **P-C** | + `d_coef=2.0` (W2) | 0.2461 | 0.2380 | 1e-6 | 0.195 | 1.95e-01 | 21.7% |
| **P-D** | + `d0=1e-5` (V2 fix konstmish) | 0.2299 | 0.2227 | **1e-5** | 0.112 | 1.12e-01 | 21.3% |
| **P-E** | CANONICAL KOHYA + cosine_no_restart | **0.2281** ✅ | 0.2227 | 1e-5 | 0.188 | **4.59e-03** ← cosine | 17.1% |

**Reference BPTT+AdamW (F2 baseline 15ep)**: val_total = 0.2262

## 17. Tre predizioni mie SBAGLIATE (corrette dai dati)

### ❌ Predizione 1 (parte 1 §7): "d frozen a 1e-3 in tutti i nostri T30"

**Reality**: d sale eccome. Tutti i 5 esperimenti raggiungono d > 0.017 entro epoca 1. Anche P-A (default lib) arriva a 0.017 (170× più alto di 1e-6).

**Spiegazione corretta**: nei T30 (5700 step) Prodigy era stabilizzato a d~0.001-0.003 perché aveva avuto tempo di esplorare e si era assestato. Con 1000 step (R2), d sale rapidamente e si ferma a un plateau più alto (0.017-0.195). La differenza tra T30 e R2 è probabilmente dovuta a: (a) diverso dataset n_train=1500 stesso ma random seed/order diverso, (b) `lambda_sr=0.5` attivo qui vs 0 in T30, (c) altre micro-differenze.

**Conclusione**: "d frozen" era una mia caratterizzazione affrettata. **d in realtà si stabilizza presto a un plateau, e quel plateau è il driver della velocità di convergenza.**

### ❌ Predizione 2 (parte 2 §11.W1): "W1 betas=(0.9, 0.99) sblocca Prodigy"

**Reality**: SI sblocca **numericamente** (val_total da 0.303 → 0.228) ma **NON sblocca le distribuzioni params**.

**Evidenza**: violin G7 di P-B mostra **TUTTI e 5 i params completamente collassati ai bounds** (v0=45 max, T=0.5 min, s0=5 max, a=0.3 min, b=0.5 min). La rete predice costanti. Idem P-C, P-D, P-E. Anche P-A ha 4/5 params collassati (solo v0 ha spread 30-45).

**Spiegazione**: in highway-only training, gli scenari hanno TUTTI gli stessi 5 params IDM (IDM_HIGHWAY={v0=33.3, T=1.2, s0=2.5, a=1.1, b=1.5}). La rete che predice CONSTANTS qualunque esse siano ottiene val_total basso perché tutti i target sono uguali. **W1 fa convergere la rete più velocemente a un fitting di costanti, NON a un decoding parametrico vero.**

### ❌ Predizione 3 (implicita in tutti i nostri ranking): "val_total è metric robusta per ranking optimizer"

**Reality**: val_total in highway-only è **INGANNEVOLE**. La rete che predice costanti ottiene val_total decente. Non distingue "ha imparato a decodificare" da "ha imparato una media".

**Evidenza**: P-B/P-D/P-E pareggiano F2 baseline NUMERICAMENTE (val_total 0.228 vs 0.226), ma F2 baseline ha SR=0.5 + 15 ep + AdamW e altrettanto violin probabilmente collassati. Cinque setup diversi (Prodigy + AdamW) **convergono allo stesso val_total perché stanno predicendo tutti la stessa media** — non c'è informazione discriminativa nel ranking.

## 18. Verdetto onesto su Prodigy

### Cosa abbiamo veramente stabilito (alta confidenza)

1. **Prodigy NON è "broken" né "non aggiunge valore"** (AUDIT §2.2 confutato). Con W1 attivo, pareggia BPTT+AdamW numericamente in 10 ep vs 15 ep di F2 (= 33% meno epoche), su setup di confronto degenere.
2. **W1 (`betas=(0.9, 0.99)`) è il singolo lever più impattante** per la nostra rete: val_total da 0.303 → 0.228 (drop relativo del 25%). Conferma "dramatic improvement" di madman404 (community wisdom Issue #8).
3. **V2 (`d0=1e-5`) funziona quasi quanto W1**: val_total 0.230. Conferma fix konstmish ufficiale (Issue #27).
4. **W2 (`d_coef=2.0`) da solo è subottimo**: val_total 0.246. Più alto non sempre meglio.
5. **Setup CANONICAL kohya completo (P-E)** NON batte P-B singolo: **W1 è il driver principale**, gli altri lever danno guadagno marginale o trascurabile in questo task.
6. **Cosine_no_restart modula correttamente `lr_eff` sul finale**: P-E `d_max=0.188` ma `lr_eff_end=0.0046` (decay cosine a fine training). Comportamento atteso.

### Cosa NON abbiamo potuto stabilire (impossibile in highway-only)

1. **Prodigy migliora la qualità del fit dei params IDM?** → IMPOSSIBILE rispondere: violin G7 collassati in tutti gli esperimenti.
2. **Prodigy generalizza meglio di AdamW su scenari diversi?** → IMPOSSIBILE: scenari mai testati, solo highway.
3. **Setup canonical batte AdamW+OneCycle su training lungo (30+ ep)?** → IMPOSSIBILE: solo 10 ep testate per ragioni di tempo.

### Decisione operativa post-R2

- **Prodigy è OPZIONE VALIDA equivalente a AdamW** sui task in cui abbiamo evidenza (highway, 10 ep). Non superiore, non inferiore. Da preferire se vuoi `lr` "free" (no scheduler tuning manuale).
- **Setup minimo raccomandato per Prodigy nel nostro CF_FSNN**: `lr=1.0 betas=(0.9, 0.99) safeguard_warmup=True d_coef=1.0 d0=1e-6` (= solo W1 attivo). Il resto è opzionale.
- **Frase corretta per AUDIT §2.2**: NON più "Prodigy non aggiunge valore" → "Prodigy con setup canonical pareggia AdamW sul setup di test degenere; un verdetto rigoroso richiede scenari misti (R4 futuro)".

## 19. Lezioni meta (le più importanti)

### Lezione #M1 — `val_total` in highway-only è INGANNEVOLE
Con tutti gli scenari aventi target IDM identici, una rete che predice costanti ottiene val_total decente. Non c'è informazione discriminativa per ranking optimizer/arch. **Tutti i nostri ranking pregress (T30, SW, P15) sono CONFUSI dallo stesso problema** — il "best" e il "worst" potrebbero essere entrambi reti che predicono costanti, solo a valori leggermente diversi.

### Lezione #M2 — VIOLIN G7 è il metro reale di apprendimento
Per validare che la rete stia veramente decodificando i 5 params IDM e non solo medie, **violin G7 va sempre controllato** prima di celebrare un val_total. Se violin sono collassati, val_total non è confrontabile fairly.

### Lezione #M3 — Studi optimizer su dati degeneri sono inconcludenti
Tutto questo R2 è un esercizio di calibrazione Prodigy ma NON un test della sua superiorità/inferiorità per il nostro task. **Per conclusioni operative serve scenari diversi** (R4: mixed highway/urban/truck/cut-in con IDM params variabili).

### Lezione #M4 — "d frozen" era una mia caratterizzazione affrettata
Caratterizzare un sistema come "broken" senza dato granulare per-batch (avevamo solo per-epoch nei T30) porta a diagnosi sbagliate. Il logging per-batch di R2.2 ha mostrato che d sale a 0.017 → 0.195 nei nostri test, NON resta a 1e-3 come pensavo.

## 20. Criterio di chiusura R2 — RIVALUTATO

Dei 5 criteri di chiusura previsti nel plan:

1. ✅ Capisco la formula esatta di update di `d` (parte 1 §3)
2. ✅ Capisco perché `lr=1.0` canonical NON esplode (parte 1 §5 + parte 2 §10)
3. ⚠️ "Riprodotto pattern scala" — **NO, non si vede**: i nostri d salgono e si fermano subito (non a scala). Tipico di task convex-like con 864p su data ridotti.
4. ✅ `PRODIGY_DEEP_STUDY.md` completo (parte 1+2+3, ~750 righe)
5. ✅ Posso predire qualitativamente cosa Prodigy farà su nuovo setup: setup default = SGD lento, W1 attivo = pareggio AdamW, canonical = idem W1, brake (d_coef<1) = più lento. 

**R2 può essere considerato CHIUSO**, con il caveat che il vero verdetto Prodigy vs AdamW richiede R4 (scenari misti).

## 21. Aggiornamento skill SNN-expert (opzionale, da fare)

Aggiungere a `~/.claude/skills/SNN-expert/` capitolo "Optimizers for SNN": Prodigy lessons (W1, V2, W2), setup canonical, failure modes (highway-only confounder, d plateau caratterizzazione), monitoring (d + violin params). Da fare dopo R3 EventProp per coerenza.

---

# PARTE 4 — Post-fix BUGS_2026-06-03 + R24F + R25 + R26 (2026-06-04 → 10)

> **Contesto**: la parte 3 ha chiuso R2 con il caveat "violin G7 collassati universalmente — verdetto richiede R4 scenari misti". Prima di R4 abbiamo scoperto i 4 bug strutturali (`BUGS_2026-06-03.md`), che spiegano IL caveat. Post-fix, abbiamo rifatto R2.4 (R24F) e poi avviato R25 (ablation causale) + R26 (fusion). Parte 4 documenta i nuovi findings.

## 22. R24F — Rerun Prodigy MultiParam post-fix (93 esperimenti)

### 22.1 Setup
- Branch: `Prodigy_Deep_Study` post-fix (HEAD `d9d558a`)
- Arch: `baseline` (864p, post-fix), 10 ep × 100 step
- 90 Prodigy: 3 scenari (highway, mixed, full) × 3 LR × 10 varianti (V01..V10)
- 3 AdamW baseline (1/scenario, lr=1e-3) per misurare valore aggiunto
- Notebook: `Prodigy_MultiParam_Study_PostFix.ipynb`, results `MultiParam_PostFix/`

### 22.2 Risultati (best per scenario)

| Scenario | Best Prodigy | LR | val_total | AdamW ref | Guadagno |
|---|---|---:|---:|---:|---:|
| highway | V08 cosine_no_restart | 1.0 | **0.169** | 0.186 | -9% |
| mixed | V08 cosine_no_restart | 0.5 | **0.189** | 0.230 | -18% |
| full | V08 cosine_no_restart | 1.0 | **0.222** | 0.253 | -12% |

**V08 (cosine_no_restart) DOMINA su tutti e 3 gli scenari**:
```
lr=1.0 (o 0.5 mixed), d_coef=1.0, d0=1e-6, growth=inf
scheduler=cosine_no_restart, betas=(0.9, 0.99), use_bias_correction=1
safeguard_warmup=1, weight_decay=0.01
```

### 22.3 Problema scoperto: T-tracking flat
Da G7 + G13:
- v0 satura vicino MAX (40-45)
- s0 satura vicino MAX (3-5) o MIN (1-1.5) a seconda dello scenario
- `a` sempre vicino MIN (0.3-0.45)
- **T predetto piatto intra-sample**: T_pred(t)=costante, ignora T_true(t) step
- Cross-driver: rete distingue driver con T diversi (corr ~0.35), ma intra-driver no

La rete fa **"average estimation cross-driver"**, NON **"system identification intra-driver"**.

## 23. R25 — Ablation causale (18 esperimenti, 5 assi)

### 23.1 Setup
- Scenario `mixed` (più informativo), Prodigy V08 lr=1.0, seed=42
- 5 assi: A memoria, B loss balancing, C spike rate, D capacity, E training duration
- Notebook: `Prodigy_Ablation_Study_R25.ipynb`

### 23.2 Infrastruttura R25

**`train.py` modifiche**:
- `pinn_loss` 4-tuple `(loss, comps, sr, params_seq)` + `lam_T_aux` + `retain_params_grad`
- Nuovo termine: `L_T_aux = masked MSE(params_seq[:,:,1], y_seq[:,:,1])` se `lam_T_aux > 0`
- Train epoch: cattura `params_seq.grad` post backward → 15 gradient values per canale
- Val epoch: Pearson `val_T_tracking_corr` + 5×pred_mean + 5×intra_std
- CSV: +11 col epoch + 16 col batch
- CLI: `--lambda_T_aux`, `--cf_max_delay`, `--cf_bit_shift`

**`utils/plot_diagnostics.py`**:
- **G16** gradient raw per canale (log scale)
- **G17** gradient decoded post-sigmoid (log scale)
- **G18** gradient direction sign mean ([-1, +1]) — cattura cancellazione cross-sample

### 23.3 Risultati — 3 WIN INDIPENDENTI

**Baseline R25_A1** (replica V08 mixed): val=0.195, T_corr=**0.353**.

| Asse | Run | Modifica | ΔT_corr | Δval |
|---|---|---|---:|---:|
| **A** | A4 | max_delay 6→18 | **+0.090** | -0.015 |
| **B** | **B1** | lambda_T_aux 0→0.1 | **+0.147** | -0.006 |
| **C** | C1 | lambda_sr 0.5→0 | **+0.088** | -0.014 |
| D | D2 | h=64, r=16 | +0.068 | -0.004 |
| E | E1 | epochs=5 | -0.010 | -0.006 |

### 23.4 Findings critici R25

**1. L_sr regularizer è CONTROPRODUCENTE per T-tracking**
- C2 (sr=5): spike rate 14% (target FPGA) MA T_corr crolla del 70%
- Trade-off duro spike rate ↔ T-tracking

**2. Più training PEGGIORA T-tracking**
- E2 (20ep): val_data ↓ MA T_corr ↓ a 0.23
- E3 (30ep): val_total esplode, T_corr 0.08
- **Early stop ≈ 10 ep è la scelta giusta**

**3. Capacity NON è bottleneck**
- D3 (128h) crasha (best_ep=1)
- D2 (64h) solo +0.07 su T_corr

**4. A6 COMBO — interazione negativa**
- A6 = seq_len=100 + max_delay=18 + bit_shift=5
- Atteso: somma effetti ≈ +0.06
- **Misurato: T_corr = 0.20 (peggio di baseline!)**
- Sospetto colpevole: bit_shift=5 (A5 isolato già aveva -0.07)

**5. Gradient unbalance INVERTITO post-fix**
- Pre-fix: v0 dominante (gradient 10× degli altri)
- Post-fix: **T dominante** (gn_out_fc_T=0.23 vs v0=0.01, 23×)
- B1 NON cambia magnitudo gradient T (0.23→0.24) ma cambia la **direzione semantica**
- B3 (T_aux=10) gn_out_fc_T → **2.43**: budget gradient tutto su T, fisica esplode

**6. Caveat metric T_tracking_corr**
La Pearson aggregato cattura 2 fenomeni:
- (1) **Cross-driver alignment** (driver con T_true diversi → T_pred diversi)
- (2) **Intra-driver dynamics** (T_pred(t) segue T_true(t) intra-seq)

I 0.35 baseline sono quasi tutti (1). Il +0.15 di B1 è probabilmente (2). Per disambiguare servirebbe `val_T_intra_corr` (Pearson dopo aver rimosso la media per-sample). TODO post-R26.

## 24. R26 — Fusion Study (6 esperimenti, IN ESECUZIONE)

### 24.1 Ipotesi
Se A4, B1, C1 sono ortogonali:
- Somma teorica: ΔT_corr = 0.090 + 0.147 + 0.088 = **+0.325**
- T_corr atteso F1 TRIPLE = 0.353 + 0.325 = **0.678** (linearity 100%)
- Realisticamente per non-linearità: **0.55-0.62** (linearity 70-90%)

### 24.2 Design (6 run, ~1h Azure)

| Tag | max_delay | T_aux | sr | epochs | Scopo |
|---|---:|---:|---:|---:|---|
| F0_baseline_replica | 6 | 0.0 | 0.5 | 10 | sanity |
| **F1_TRIPLE_win** | 18 | 0.1 | 0.0 | 10 | TOP candidato (A4+B1+C1) |
| F2_A4_B1 | 18 | 0.1 | 0.5 | 10 | isola C1 |
| F3_B1_C1 | 6 | 0.1 | 0.0 | 10 | isola A4 |
| F4_A4_C1 | 18 | 0.0 | 0.0 | 10 | isola B1 |
| F5_TRIPLE_short | 18 | 0.1 | 0.0 | 5 | F1 + asse E |

### 24.3 Linearity test automatico (Cell 6 notebook)
```
R25 sum predicted: dval=-0.035, dTcorr=+0.325
F1 measured:        dval=??       dTcorr=??
Ratio T_corr:       (measured/predicted)*100 = ??%
```
- ratio > 80% → effetti sommano (success)
- 50-80% → saturazione
- < 50% → forte non-linearità

### 24.4 Decision tree post-R26

- **Caso A — F1 batte F2/F3/F4**: i 3 fattori sommano. R26_F1 nuovo champion.
- **Caso B — F1 ≈ max(coppie)**: saturazione, un fattore dominante.
- **Caso C — F5 > F1**: early stop conferma asse E.
- **Caso D — F1 < max(coppie)**: interazione negativa (raro).

## 25. Criteri di chiusura aggiornati

1. ✅ Math di Prodigy capita (parte 1+2)
2. ✅ Setup canonical kohya identificato (W1+V2+bias_corr+safeguard)
3. ✅ R2.4 → V08 cosine_no_restart è il setup vincente (R24F)
4. ✅ T-tracking flat scoperto + diagnosticato (R24F)
5. ✅ R25 ablation → 3 win indipendenti (A4, B1, C1)
6. ⏳ R26 in corso — verifica ortogonalità
7. ⏳ Post-R26 candidato risolutivo per T-tracking
8. ⏳ R3 EventProp riapre quando T sotto controllo

## 26. Lessons learned post-R24F (Lezioni N1-N5)

### N1 — Il floor 0.22 era BUG-INDOTTO, non architetturale
Pre-fix tutti gli optimizer raggiungevano val ~0.22 → "floor architetturale". Post-fix V08 fa 0.169 → il floor era sigmoid saturation. **Sempre testare config minime prima di concludere "architettura ha plateau"**.

### N2 — Il gradient unbalance può INVERTIRSI tra fix
Pre-fix v0 dominava. Post-fix T domina. Un fix corretto su un asse può spostare il problema su un altro asse. **Misurare gradient per canale è OBBLIGATORIO**.

### N3 — Le ablation "ortogonali" possono interagire negativamente
A6 COMBO ha mostrato che A3+A4+A5 ensemble = peggio della baseline. **Test combinatorio prima di concludere ortogonalità**.

### N4 — Spike rate target FPGA può essere incompatibile con T-tracking
C2/C3 hanno mostrato trade-off duro: 14% spike rate impone -70% T_corr. Per FPGA target serve approccio diverso (weight decay anti-saturation, non loss penalty).

### N5 — Linearity test prima di "ortogonali"
Da R25 abbiamo 3 win singoli. Da R26 capiamo se sommano. Pattern: ablation 1-at-a-time → ipotesi → test combinatorio. Senza step 3 le ablation sono solo correlate.
