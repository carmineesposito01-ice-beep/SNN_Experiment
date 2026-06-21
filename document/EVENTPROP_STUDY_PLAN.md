# EventProp_Study — Piano

**Branch**: `EventProp_Study` (da `main`, 2026-06-21). **Study 2** del piano post-Loss_Study.
**Doc collegati**: `EVENTPROP_DESIGN.md` (math + roadmap storica F2.0-2.3), `EVENTPROP_OPTIMIZER_SWEEP.md`
(chiusura storica, sweep 44 run), `EVENTPROP_GRID2X2.md`. Codice: `core/eventprop.py`.

---

## 1. Obiettivo (inquadramento utente, 2026-06-21)

**Traslare la nostra baseline ATTUALE migliore** — PEAK (ALIF A1, 864p) + **ricetta Prodigy canonica
single-cycle** (`cosine_no_restart + lr=0.5 + growth_rate 1.05`, warmup morbido, ~15-20 ep) — **su
EventProp**, usandolo *bene* (cosa che lo studio storico non fece pienamente).

Non si insegue il muro: condividiamo la sensazione che **non abbatteremo val_data** (vedi §2, C2 floor
architetturale). L'obiettivo è **sperimentale**: vedere cosa emerge da un gradiente ESATTO usato bene —
potrebbe dare un **punto di vista diverso** sul problema (es. su a/b, sul floor) da cui derivare soluzioni
nuove. Le SNN sono reti sperimentali: qualunque insight è valore aggiunto.

## 2. Cosa sappiamo già (studio storico, 44-run, da non ripetere)

- **Accuratezza: PAREGGIO** — `eventprop_alif_full` 0.2226 vs baseline 0.2218 (Δ nel rumore).
- **C2 — floor ARCHITETTURALE**: BPTT-surrogato ed EventProp-esatto convergono allo stesso 0.222 → il muro
  NON è un artefatto della surrogata. (È il limite probabile anche per questo studio sull'accuratezza.)
- **C3 — fragilità**: 6/11 config fallirono (grad ~10¹⁷, cascade su 500 tick), CV 22× il baseline.
- **C4 — spike rate 6× più alto** (25.7% vs 4.1%) → peggio per FPGA.
- Unico vantaggio storico: **39% più veloce** in training.

**Gap dello studio storico (perché "usato male")**: solo 5 ep · `scheduler=none` (no warmup) → Prodigy frozen
10/16 · **nessun AGC** (le esplosioni 10¹⁷ non erano domate) · mix highway-only · adjoint con `thresh_jump`
a **gradiente congelato** (λ_fatigue non implementato).

**Strumenti NUOVI dall'epoca** (non disponibili allora): **AGC** (`--grad_clip agc`, clip per-unità ∝ ‖w‖,
domabile il cascade) · **ricetta Prodigy canonica** single-cycle (risolve il warmup/frozen) · sapere che
~15-20 ep bastano · mix launch/freeflow. → la fragilità C3 potrebbe essere stata **misuso risolvibile**.

## 3. Stato implementazione (`core/eventprop.py`)

- `ALIFLayer_EventProp_Full` = A1 con adjoint (864p), variant `--training_method eventprop_alif_full`.
- Denominatore adjoint `drive[k+1]−V_th_eff[k+1]` **ha già il guard eps** (1e-3).
- **`thresh_jump` gradiente = 0** (congelato): λ_fatigue non propagato (C8). Limite noto, non causa di
  divergenza; significa che il "salto di fatigue" resta all'init (0.5). Fix completo = 3-5h, RINVIATO salvo
  motivazione dallo scout.

## 4. Design

Confronto **a parità di ricetta moderna** (apples-to-apples), su mix launch/freeflow:

| Arm | training_method | gradiente | note |
|---|---|---|---|
| **A (controllo)** | `baseline` | BPTT + surrogate | la nostra baseline attuale |
| **B (trattamento)** | `eventprop_alif_full` | EventProp esatto | stessa arch A1, stessa ricetta |

Ricetta comune: `cosine_no_restart + lr=0.5 + growth_rate 1.05` + **`--grad_clip agc`** + launch/freeflow +
~18 ep + guard esplosione ON.

### Diagnostica — standard + IL PUNTO DI VISTA NUOVO
- **Standard**: val_data, NRMSE per-param (v0/T/s0/a/b), spike rate, robustezza (esplode ancora con AGC?
  grad norms), tempo.
- **Viewpoint (il vero deliverable)**: confronto della **struttura del gradiente** tra esatto e surrogato —
  `gn_decoded_{v0,T,s0,a,b}` (quanto gradiente arriva a ciascun parametro). Domande: il gradiente ESATTO
  alloca diversamente su a/b? conferma che a/b ricevono ~0 gradiente (→ floor strutturale confermato da un
  secondo angolo) o lo distribuisce diversamente (→ la surrogata nascondeva qualcosa)? + per-driver r (L1d-style)
  su entrambi.

## 5. Roadmap (scout-prima-del-test-lungo)

0. **SCOUT locale** (~10 ep): Arm B (`eventprop_alif_full` + ricetta canonica + AGC). Domanda: **AGC+canonica
   domano la fragilità C3?** (gn limitato, 0 esplosioni) e che val_data/struttura-gradiente escono. Decide se
   ha senso il full su Azure e se serve il fix C8.
1. **Full A-vs-B su Azure** (~18 ep, launch/freeflow, n_train pieno): confronto completo + diagnostica viewpoint.
2. **(condizionale)** fix adjoint C8 (λ_fatigue + thresh_jump grad) se lo scout mostra che la fragilità o il
   thresh_jump congelato limitano l'esperimento.

**Stop/honest-close**: se lo scout esplode anche con AGC → l'instabilità è intrinseca all'adjoint (serve C8 o
si chiude). Se pareggia val_data ma la struttura-gradiente NON dà insight nuovi → si documenta il pareggio
(2ª conferma C2) e si chiude verso multi-seed→FPGA. Qualunque insight su a/b/floor = valore aggiunto.

## 6. Principio
Niente workaround; estensione non modifica (i nuovi run usano flag esistenti opt-in già verificati
bit-identici al pre-modifiche). Champion `normal` resta il deploy a prescindere.
