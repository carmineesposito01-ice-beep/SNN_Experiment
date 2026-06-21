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

---

## 7. IMPLEMENTAZIONE & RISULTATI SCOUT (2026-06-21) — studio PRONTO per Azure

**Fix e nuovo codice (tutto opt-in, backward-compat bit-identico verificato):**
- **Fix C8** (`core/eventprop.py`): `jump_clamp`+`lv_clamp` sull'adjoint ALIF → EventProp ora STABILE
  (gn 87 vs `inf`/1e17 storico). Scout AdamW: val 0.350→0.267 monotona, spike 0.17 in-banda.
- **ProdigyEvent** (`core/prodigy_event.py`, `--optimizer prodigy_event`): Prodigy adattato a EventProp.
  Prodigy-std si CONGELA su EventProp (d=1e-6: gradiente esatto sparso → incoerente per lo stimatore di d).
  Meccanismi (tutti iper-parametri sweepabili): (1) stima d su **gradiente EMA** (`--prodigy_ema_beta`) →
  sblocca d (1e-6→0.018); (2) **throttle adattivo** su trend norma-gradiente (`--prodigy_instab_kappa`)
  con **decay morbido** (`--prodigy_d_decay 0.99`) → d si assesta al confine stabile invece di collassare;
  (3) **ProbeUp MPPT P&O** (`--prodigy_probe_up`) → esce dallo stuck-low; (4) gate spike-rate
  (`--prodigy_rate_band`). Scout: ProdigyEvent+ProbeUp val **0.299** (= AdamW-class), d assestato 0.0066.
- **Controllo rate attivo** (`--lambda_sr_adapt_gamma`): lam_sr cresce fuori banda (richiamo direzionale).
  Finding: si **accoppia con la stima di d** di ProdigyEvent (la perturba → overshoot) → più pulito su AdamW.

**Findings scout (5ep locali, n_train 400):**
- EventProp stabile (AdamW) val 0.267; ProdigyEvent+ProbeUp 0.299 (parameter-free); Prodigy-std frozen 0.69.
- **Viewpoint anteprima** (gradiente esatto, epoche stabili): v0 ~0.2% (gradient-starved come la surrogata,
  metodo-indipendente); **a/b ricevono ~64%** (a 43% > T 32% > b 21%) → il muro a/b NON è flusso-gradiente.
- ProdigyEvent+ProbeUp = **candidato canonico** (se conferma a 50ep diventa il ProdigyEvent di default).

**Arm dello studio** (`EventProp_Study.ipynb`, EventProp primi → pushati prima, 50 ep, launch/freeflow,
n_train 1500): EVP_ADAMW · EVP_PRODIGYEVENT · EVP_PRODIGYEVENT_PROBE · EVP_PE_PROBE_LSR · EVP_ADAMW_LSR ·
PEAK_BASELINE (BPTT champion custom_restart) · PEAK_SINGLECYCLE (BPTT Prodigy canonico). Diagnostica:
val_data/NRMSE/spike/stabilità + viewpoint gradiente esatto-vs-surrogato + correlazione per-driver r_a/r_b
+ traiettoria d. Plumbing end-to-end validato. **Da girare su Azure.**

**Deliverable atteso**: due metodi di training ottimizzati (BPTT+Prodigy-canonico, EventProp+AdamW/ProdigyEvent),
+ il viewpoint sul perché del floor/a/b da un secondo paradigma. Qualunque insight = valore aggiunto.
