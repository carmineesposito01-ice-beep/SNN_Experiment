# EventProp — Stato attuale (2026-06-24)

Branch `EventProp_Study`. Documento di stato vivo: dove siamo, cosa funziona, cosa resta da spremere.

---

## 1. Risultato: EventProp è risolto e competitivo

EventProp era **sempre instabile** (esplodeva/abortiva). Ora è un metodo di training **stabile e
convergente**, con due ottimizzatori funzionanti, e su `val_data` (loss accel) **batte il BPTT-ref**
(0.219 vs 0.244 nel BigSweep). Sotto il BPTT champion storico (~0.19) resta un piccolo gap, attribuibile
ai lock per-canale qui sotto.

### Cosa ha sbloccato la stabilità — la catena di fix (tutti flag opt-in, backward-compat)

| Fix | Cosa | Esito |
|---|---|---|
| **C8 / C8b** | clamp adjoint (`jump_clamp`/`lv_clamp`) + gate denom | failsafe; NON meccanismo di stabilita' |
| **C10** | correzione scala denom per il bit-shift leak | parziale, perturba il training -> non usato |
| **C11 — vincolo spettrale** | `lambda*relu(sigma_max(U@V)-target)^2` | **LA CURA**: la causa era il raggio spettrale della ricorrenza che cresce (0.83->2.8) e fa divergere l'adjoint Rᵀ. Vincolarlo = stabile per costruzione |
| **C12 — ProdigyEvent loss-aware** | P&O bidirezionale su `d` guidato dal trend della LOSS + peso spike-rate | ProdigyEvent (parameter-free) ora STABILE su EventProp: `d` auto-trova il range buono, si ritira sulle finestre cattive. ~pari AdamW |
| **C13 — adjoint completo del fatigue** | `lambda_fatigue` -> `thresh_jump` si allena (era congelato, gradiente 0) | tecnicamente corretto e funziona (thresh_jump impara), ma **neutro sull'accuratezza** |

### Operating point (sweep)
- **AdamW**: il knob e' il **target spettrale** (non lambda). Stabilita' pulita richiede `sigma_max <=~1.4`.
  Migliore: **lr alto (3e-3) + target basso (0.8)** -> val 0.216. Trend monotono: target piu' basso = meglio
  -> **l'ottimo e' sotto 0.8** (sweep fine 0.5-0.7 da fare).
- **ProdigyEvent loss-aware**: `lr 0.5, growth 1.02, loss_aware 1, po_period 25, po_bad_decay 0.5,
  spettrale 0.5/target 1.2` -> ~0.24, ancora in discesa. `po_good_probe 0.02` = troppo aggressivo (rumore).

### ALIF (soglia adattiva) — analizzato a fondo
Lo scan `thresh_jump in {0, 0.5, 1, 2}` mostra una **U con minimo a 0.5**:
- `0` (no ALIF) -> **ESPLODE** (grad 67000, firing a raffica 0.30). L'ALIF e' il **regolatore di sparsita'
  del firing**: senza, i neuroni non hanno freno refrattario e divergono. E' infrastruttura PORTANTE.
- `0.5` -> ottimo (val 0.261, firing 0.17 ~ banda sana).
- `1, 2` -> stabile ma underfit (firing soffocato 0.14/0.11, val 0.270/0.274).
- C13 (addestrarlo) e' neutro perche' **0.5 e' gia' l'ottimo** (la rete vi ritorna anche se stimolata).
-> **ALIF = essenziale, gia' tarato. C13 off. Non e' una leva di accuratezza.**

---

## 2. Lock nascosti trovati (caccia ai colli di bottiglia, 2026-06-24)

Analisi dell'architettura sul checkpoint EP per cercare capacita' "morta" / saturazioni non viste.

### 2a. RISOLTO (2026-06-24) — Decoder machinery ASSENTE nella variante EventProp
**Causa radice**: `CF_FSNN_Net_EventProp_Full` NON registrava `decode_offset`/`logit_tau` ne' aveva
`calibrate_decode_offset` (il `_decode_params` era getattr-safe -> tau=1, offset=0). Quindi i flag
`--cf_init_bias_shift`/`--cf_logit_tau_per_channel` erano **silenziosamente inefficaci** su EP. **FIX**:
aggiunti i buffer + `calibrate_decode_offset` adatto al forward EventProp (opt-in, backward-compat).

**Conferma empirica (best-Adam, 10ep, decode OFF vs ON):**
| canale | DEC_OFF | DEC_ON | BPTT_REF (50ep) |
|---|---|---|---|
| v0 | 0.445 | **0.242** | 0.326 |
| T | 0.206 | **0.140** | 0.201 |
| s0 | 0.323 | **0.101** | 0.192 |
| a | 0.282 | **0.227** | 0.278 |
| b | 0.310 | **0.173** | 0.275 |
| val_min | 0.2563 | **0.2374** | 0.244 |

**Tutti i canali migliorano**; T-scatter ora segue y=x (era orizzontale). A 10ep EP+decode **batte il
BPTT-ref (50ep) su OGNI canale e sul val.** -> **AZIONE: ri-girare gli sweep EP CON la calibrazione**
(`--cf_init_bias_shift 1 --cf_logit_tau_per_channel 10.0,3.0,10.0,3.0,3.0`); a 50ep atteso val ben sotto
0.219, probabile sorpasso del champion storico 0.19.

(Storico) NRMSE per-canale prima del fix:

| canale | EP | BPTT | nota |
|---|---|---|---|
| v0 | 0.254 | 0.326 | EP meglio |
| **T** | **0.285** | **0.201** | BPTT meglio — T-scatter EP orizzontale (non segue y=x) |
| **s0** | **0.354** | **0.192** | BPTT MOLTO meglio |
| a | 0.262 | 0.278 | ~pari |
| b | 0.270 | 0.275 | ~pari |

EP vince su v0/a ma **perde T e s0** — proprio i canali che la `logit_tau` de-satura. Il decode NON satura ai
bound (frac 0.00) -> il problema e' la **pendenza** della sigmoid, non il clipping.
**AZIONE**: rifare le run EP con `--cf_init_bias_shift 1 --cf_logit_tau_per_channel 10.0,3.0,10.0,3.0,3.0`.
Atteso: T/s0 crollano -> val_data sotto 0.219, possibile sorpasso netto del BPTT champion.

### 2b. Ricorrenza in rank-collapse: rank effettivo ~3/8
`U@V` (rank max 8) ha **rank effettivo ~3** (singolari 0.82, 0.79, poi tutti <0.12): **6/8 dimensioni
ricorrenti quasi morte**. Coerente col fatto che il task vuole poca ricorrenza (best a target spettrale
basso). Probabilmente non e' un collo di bottiglia (la ricorrenza non serve), ma e' capacita' inutilizzata.
**DA VALUTARE**: ridurre `cf_rank` (8->2/3) semplifica senza perdere nulla? O il task la usa altrove?

### 2c. 4/32 neuroni morti (12.5% del layer nascosto)
4 neuroni hidden non sparano mai (firing < 0.5%, min 0.0000). Il `silent_repair` evita i neuroni
totalmente silenti all'init ma non quelli che muoiono in training. **Capacita' sprecata.**
**DA VALUTARE**: init migliore, soglia di repair piu' alta, o meno pressione di sparsita' (lambda_sr).

---

## 3. Zone grigie aperte (prossimo loop di analisi)
- **Decode calibration su EP** (2a) — la leva piu' promettente, da provare subito.
- **Dati**: launch peggiora un po' T (osservazione utente). Piu' dati / mix diverso aiuta T? (richiede run).
- **Rank ricorrenza** (2b) e **neuroni morti** (2c) — capacita' recuperabile?
- **Sweep fine target spettrale 0.5-0.7** (l'ottimo AdamW e' sotto 0.8).
- **Ottimizzazione knob ProdigyEvent loss-aware** (po_bad_decay/po_period/growth).
- **Per-regime**: T/s0 migliorano nei transitori (launch) o nella crociera (freeflow)?

## 4bis. BigSweep concluso + cap-scan (2026-06-24 sera)

### Mappa AdamW spettrale (decode OFF, 50ep) — ottimo confermato ≤0.8
| lr ＼ target | 0.8 | 1.0 | 1.2 | 1.4 |
|---|---|---|---|---|
| 5e-4 | 0.2422 | 0.2421 | 0.2448 | 0.2472 |
| 1e-3 | 0.2336 | 0.2318 | 0.2304 | 0.2331 |
| 2e-3 | **0.2186** | 0.2196 | abort | abort |
| 3e-3 | **0.2161** | 0.2210 | 0.2258(abort@37) | 0.2366(abort@15) |

- **Ottimo = lr 3e-3 + target 0.8 = 0.2161**; monotòno verso target più basso → **il vero ottimo è <0.8**.
- **lr alto + target ≥1.2 ESPLODE** (grad 2800-7200). Spingere lr richiede target basso.
- lr 5e-4/1e-3 inutili (0.24/0.23). → Sweep fine in `lr{2e3,3e3,5e3} x target{0.5,0.6,0.7}` (decode off).
- **BPTT_REF è ESPLOSO** (grad 2e17, abort@16) → riferimento inaffidabile in questo run; in BigSweep2
  riportato a `growth 1.02`.

### ProdigyEvent loss-aware — NON competitivo (archiviare)
Tutti gli arm PE a **0.29-0.51** (migliore completato bd03_gp002 = **0.295**) vs AdamW 0.216. Gli arm
aggressivi (lr/growth alti, bd07) esplodono (grad 1e5-2.5e5). Il C12 ha tamponato la divergenza ma il `d`
di Prodigy su questo paesaggio o rilancia lr_eff (esplode) o, se frenato (bd03), sotto-spara e si pianta a
~0.29. **Gap di OTTIMIZZAZIONE ~0.08, non di decode** → il decode non lo recupererebbe. In BigSweep2: 2 soli
arm PE (lr 0.3, bd03, decode+rank16) come ultimo tentativo; poi PE archiviato, AdamW = ottimizzatore di
produzione.

### Lock 2b/2c RISOLTI (cap-scan, decode ON, 8ep)
| config | val_min | rank effettivo | neuroni morti |
|---|---|---|---|
| h32 rank 2 | 0.2600 | 1.64/2 | 0/32 |
| h32 rank 8 | 0.2503 | 3.44/8 | 0/32 |
| **h32 rank 16** | **0.2403** | 5.84/16 | 0/32 |
| h64 rank 8 | 0.2410 | 3.90/8 | 4/64 |

- **2b (rank): è una LEVA, non capacità morta.** rank 16 batte rank 8 (0.240 vs 0.250); il rank effettivo
  SCALA col rank disponibile (~35-40% del max). La rete usa quanto rank le dai → **rank 8 era sotto-dimensionato.**
  Asse diverso dallo spettrale (magnitudine bassa) vs rank (dimensionalità): entrambi utili. → **rank 16 in
  config.** (Da provare rank 24/32.)
- **2c (neuroni morti): NON-issue.** Con decode ON, **0/32 morti** (i 4 di prima erano artefatto decode-off).
  **h64 non aiuta** (0.241 ≈ rank16) e spreca 4 neuroni → la rete non è limitata dalla width.

### BigSweep2 (in attesa, notebook pronto, non ancora girato)
`EventProp_BigSweep2.ipynb` — 24 arm, 50ep, best-first, SKIP+RESUME:
- **Parte 1** (9): conclude AdamW spettrale, `lr{2e3,3e3,5e3} x target{0.5,0.6,0.7}` (decode OFF).
- **Parte 2** (12): TUTTE le correzioni, `AdamW + decode + rank{8,16}` su `lr{2e3,3e3} x target{0.5,0.6,0.7}`.
- **PE** (2) + **BPTT_REF** (1, hardened). Atteso Parte 2: decode (~-0.02) + rank16 → val ben sotto 0.216,
  probabile sorpasso del champion storico ~0.19.

## 4. Infrastruttura
- `scripts/scout.sh ... --tag X` -> run spuria pushata in `results/_scratch/X` (recuperabile).
- Notebook: `EventProp_Spectral_Sweep.ipynb`, `EventProp_BigSweep.ipynb` (AdamW + ProdigyEvent, 50ep).
- Diagnostica permanente nel training_log: `marginal_frac`, `mean_spike_margin`, `mean_vth_at_spike`,
  `rec_spectral_radius` (NaN per non-EventProp).
- Flag EventProp (tutti opt-in): `--eventprop_lambda_spectral/_spectral_target`, `--eventprop_full_threshold_adjoint`,
  `--eventprop_thresh_jump_init`, `--eventprop_alpha_f`, `--eventprop_lambda_margin`, `--eventprop_denom_*`,
  clamp; ProdigyEvent `--prodigy_loss_aware/_po_*`.
- Backup pre-pulizia workaround: branch `backup/pre-cleanup-db592b7`.
