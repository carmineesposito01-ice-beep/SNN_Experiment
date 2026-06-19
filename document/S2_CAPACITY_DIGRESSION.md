# S2 — Digressione "Capacità": studio NON esaustivo (2026-06-18)

> **Stato: SOSPESA, non conclusa.** Non possiamo affermare né che la capacità sia il
> collo di bottiglia, né che non lo sia. Le esplosioni di training hanno confuso il
> segnale. Strade future lasciate aperte: **LAMB**, **vincolo sul raggio spettrale**,
> **multi-seed**. Tornati alla strada principale (osservabilità — S3).

---

## 1. Perché l'abbiamo intrapresa

In S1b (dato freeflow) la NRMSE per-canale converge allo **stesso valore (~0.35) per tutti
e 5 i parametri** → ipotesi (utente): la rete *bilancia* l'errore perché a corto di
**capacità**. Il rifiuto passato (P9_S2B, sweep h32→h128) era a **4 epoche** → non
confrontabile. Valeva ritestarla a 50 epoche.

## 2. Cosa abbiamo fatto

**Sweep capacità** su dataset freeflow FISSO (unica variabile: h/rank), ratio params
×1/2/4/8/10. Tag `LS2_x{ratio}_h{h}_ff` in `results/Loss_Study/S2_Capacity/`.

| ratio | h | rank | params | epoche | min val_data | esito |
|---|---|---|---:|---:|---:|---|
| ×1 | 32 | 8 | 864 | 50 | **0.154** | CLEAN (unica) |
| ×2 | 50 | 12 | 1750 | 39 💥 | 0.174 | esplosa |
| ×4 | 74 | 18 | 3478 | 5 💥 | 0.218 | esplosa subito |
| ×8 | 108 | 27 | 7020 | 50 | 0.257 | **50ep su gradienti inf = spazzatura** |
| ×10 | 122 | 30 | 8662 | 50 | 0.265 | **idem (garbage)** |

## 3. I due fallimenti della guard (e i fix)

1. **Troppo severa (S1b)**: marcava "epoca esplosa" se *un solo* batch su 100 superava la
   soglia (criterio `max_gn > soglia`). Abortiva run pulite. → **fix v1**: frazione di
   batch esplosi > `--epoch_explosion_frac` (default 0.5).
2. **Troppo lasca (S2)**: la frazione contava solo i batch con gn **finito** sopra soglia;
   i batch **inf** erano esclusi → x8/x10 hanno girato 50 epoche su gradienti inf senza
   abort, producendo spazzatura. → **fix v2**: inf/nan contano come esplosi
   (`n_seen` al denominatore). **Validato** sul campo (ha catturato x10+AGC a ep9-10).

## 4. Ricerca optimizer (intuizione LAMB → scoperta AGC)

Verificata l'intuizione utente su **LAMB** (You et al. 2019): variante AdamW, trust ratio
`‖w‖/‖u+λw‖` (clampato a 10), scala lo step per dimensione dei pesi. **Corretta.** Ma:
- **LAMB** sostituisce l'optimizer → perderemmo Prodigy; beneficio provato = large-batch
  (batch 65k), non il nostro (batch 8). Richiamabile come Lion (`--optimizer lamb`), non
  ancora implementato.
- **AGC** (Brock et al. 2021, NFNets): stessa intuizione ma come **clip del gradiente
  per-unità** relativo a `‖w‖` → **optimizer-agnostico, mantiene Prodigy**. Implementato:
  `--grad_clip agc --agc_lambda L` (default off), esclude `layer_out` + param 1-D.

## 5. Test AGC su x10 — risultati

| | epoche | min val_data | NRMSE@best | esito |
|---|---:|---:|---|---|
| no-AGC | 50 | 0.265 | caotica (v0=0.52) | garbage |
| **AGC λ=0.01** | 9 | **0.202** | pulita (v0=0.34, s0=0.08, b=0.21) | 8 ep buone, poi esplosa |
| AGC λ=0.005 | 3 💥 | 0.263 | — | esplosa **prima** |

AGC λ0.01 ha dato **8 epoche pulite e risultati migliori** del no-AGC, ma esplode comunque
a ep9. AGC **più stretto (0.005) PEGGIORA** (esplode a ep2-3) → la direzione "più stretto =
più stabile" è falsa; e il timing (2 vs 8 ep) è in parte rumore di seed.

## 6. Diagnosi (con ipotesi falsificata)

**Ipotesi scartata**: NON è il `d` di Prodigy (growth_rate=inf). Smentita dai dati:
`d` stabile (x1=0.0265, x10=0.011) e **lr_eff in calo** (5e-3→1.4e-3) quando esplode.
Quindi **non è learning-rate**.

**Causa reale**: instabilità **intrinseca del ricorrente grande in BPTT** — i pesi
ricorrenti driftano verso raggio spettrale > 1, il forward stesso diventa instabile su
sequenze specifiche (gn_max spike a 1e18 su singoli batch). Un clip per-step (AGC, di
qualsiasi forza) **ritarda ma non cura** un problema di spazio-pesi.

## 7. Perché NON è esaustiva (onestà intellettuale)

- L'**unica run pienamente pulita è x1** (864p). Tutte le taglie ≥2× sono esplose →
  **nessun confronto a convergenza** possibile.
- Segnale ambiguo sul poco salvabile: x2 (39ep) ha val_data *peggiore* di x1 (0.174 vs
  0.154) ma NRMSE media *migliore* (0.307 vs 0.351). Mixed, inconcludente.
- **Non possiamo dire né che la capacità aiuti, né che sia il limite.** Le esplosioni
  hanno confuso tutto.
- Controargomento alla teoria: il problema vero (S1) è il **manifold molle**, proprietà di
  *loss+dati* non di capacità → una rete più grande sulla stessa loss probabilmente si
  siede sullo stesso manifold. Ma è un argomento, non una prova.

## 8. Strade future (lasciate aperte)

| Pista | Cosa | Stato |
|---|---|---|
| **LAMB** | `--optimizer lamb` (vendorizzato come Lion, ~60 righe) | non implementato |
| **Vincolo raggio spettrale** | normalizzazione/penalità spettrale su ricorrente `U@V` low-rank → impedisce spettro > 1 (rimedio da manuale per la causa diagnosticata) | non implementato |
| **Multi-seed** | il timing di esplosione è rumoroso → N seed per disambiguare | non fatto |
| **Stabilizzatori alternativi** | TBPTT, regolarizzazione ricorrente | non esplorati |

## 9. Infrastruttura GUADAGNATA (riusabile, già in main path)

- **guard v2** (frazione + inf) in `train.py` — robusta in entrambe le direzioni.
- **AGC** (`--grad_clip agc`) — optimizer-agnostico, pronto all'uso.
- **G19** plot NRMSE per-canale in `plot_all` — su ogni run.

## 10. Decisione

Per il principio "studio rigoroso ≠ infinito": **sospesa** (non chiusa). Torniamo alla
strada con evidenza positiva — l'**osservabilità** (il freeflow ha migliorato v0 da 0.50 a
0.39 senza esplosioni a h=32). Prossimo: **S3 — eccitazione forte di `a`** (versione forte
dell'approccio A), che colpisce il problema strutturale reale (identificabilità).
