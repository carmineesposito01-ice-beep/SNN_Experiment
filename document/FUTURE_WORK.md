# FUTURE_WORK.md — Esperimenti differiti

> File "parcheggio" per idee e re-test da fare DOPO aver risolto il limite
> attuale (plateau val~0.28). Ogni voce è un'opzione di ritorno, non un
> impegno. Aggiornare data quando si esegue/scarta.

---

## 🔬 [F1] Re-sweep Prodigy con parametri estesi (post-floor)

**Quando**: dopo aver superato il floor strutturale val~0.28 (STEP 2D+).

**Razionale**: Lo sweep STEP 2C-bis (2026-05-30) ha confermato che Prodigy
con `lr=0.1, b=1` raggiunge essenzialmente lo stesso plateau di AdamW
(0.2823 vs 0.2805). Conclusione: per QUESTO problema (con il floor a 0.28),
Prodigy non offre vantaggi sufficienti per giustificare un cambio.

**Ma**: una volta abbattuto il floor, lo "spazio di apprendimento" si apre.
In un regime dove val può davvero scendere sotto 0.20, Prodigy potrebbe
esibire comportamenti diversi — soprattutto perché:
- L'analisi a 360° ha mostrato che Prodigy ha train_loss più basso di AdamW
  (0.256 vs 0.274) — capacità di apprendimento più aggressiva
- Stabilità late phase migliore (std 0.00065 vs 0.00109)
- Gap train-val più ampio (overfit moderato) → margine per regolarizzazione

**Parametri non ancora esplorati**:

| Parametro | Default | Da provare | Razionale |
|-----------|---------|------------|-----------|
| `weight_decay` | 1e-4 | 1e-3, 1e-2 | Combattere il +0.028 gap train-val |
| `growth_rate` | inf | 1.02, 1.05 | Limitare crescita aggressiva di `d` |
| `beta3` | None (= √β₂) | 0.999, 0.9999 | Smoothing dell'adapter `d` |
| `slice_p` | 11 | 5, 20 | Subset di parametri usati per stimare `d` |
| `d0` | 1e-6 | 1e-3 | Skip warmup interno di `d` |
| `use_bias_correction` | False | True | Bias correction tipo Adam su `d` |

**Possibili sweep mini-grid** (16 config max, ~8h Azure):
- `weight_decay × growth_rate` (4×4)
- `lr × d0` (3×3)
- `beta3 × slice_p` (2×3)

**📌 Regola empirica scoperta nello sweep 2026-05-30 (6 config tested)**:
La soglia di stabilità per CF_FSNN è `lr_effective = lr × d_coef`:
- `lr_eff ≤ 0.10` → converge come AdamW (#1: 0.2823)
- `0.10 < lr_eff ≤ 0.30` → converge ma rapido poi piatto (#6: 0.2857 @E3)
- `lr_eff > 0.30` → **frozen immediato in E1** (#2, #3, #4)

Quindi `d_coef` agisce come "freno di sicurezza": consente lr base più alti
mantenendo stabilità. Per il re-sweep esteso, vale la pena testare combo
"lr alto + d_coef molto basso" (es. lr=2.0 + d_coef=0.1 → lr_eff=0.2)
per vedere se aumentare lo spazio adattativo di Prodigy può portare benefici.

**Strumenti già pronti**:
- `--prodigy_d_coef` esposto in `train.py` (commit `08087bd`)
- Logging di `prodigy_d`, `prodigy_d_max`, `prodigy_lr_eff` in BatchCSVLogger
  (commit `ac40a8f`)

**Cosa serve aggiungere a train.py**: 5 nuovi CLI flag (`--prodigy_growth_rate`,
`--prodigy_beta3`, `--prodigy_slice_p`, `--prodigy_d0`, `--prodigy_use_bias_correction`).
Costo: ~30 min implementazione + smoke test.

**Decisione**: rimandare a quando avremo `val < 0.20` reale. A quel punto valutare
se Prodigy può ulteriormente migliorare o se AdamW resta sufficiente.

---

## 📌 Altre idee parcheggiate (placeholder per il futuro)

_(Aggiungere qui altri esperimenti differiti)_
