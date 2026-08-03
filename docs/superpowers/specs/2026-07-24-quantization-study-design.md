# Studio di quantizzazione (nfrac unico) — design

**Data:** 2026-07-24
**Track:** HDL / Simulink_Importer
**Stato:** design approvato a voce (2026-07-24), in attesa di review della spec scritta

---

## 1. Contesto e motivazione

Lo Studio Trade-off (Blocco A) ha stabilito che, essendo il Fmax un **margine** enorme, il criterio di
progetto è l'**area** (lasciare spazio al blocco V2I sullo stesso Zynq-7020). La **quantizzazione** attacca
esattamente quella leva: meno bit fixed-point → meno LUT/DSP/FF (più area libera) e meno potenza dinamica, al
costo di accuratezza.

Il terreno è già in parte preparato:
- Il word-length è **parametrizzato**: `snn_types(dt, nfrac)` tiene **fissi gli interi per campo** (V=Q5,
  fatigue=Q3, acc=Q5, accw=Q8 largo, raw=Q7, w=Q2) e fa scalare a `nfrac` i soli bit **frazionari**.
- `run_fixed_sweep.m` **mappa già l'accuratezza vs `nfrac`** (max|d| sui 5 parametri, tutti i champion, tutta
  la sequenza golden) — la curva accuratezza esiste ed è fatta bene (dataset, non campione).

Lo studio **completa** ciò che manca: le curve **risorse / potenza / Fmax** vs `nfrac`, l'individuazione del
**ginocchio**, la validazione **car-following** al ginocchio, e — per ogni livello scelto — la
**configurazione canonica** (il Fmax massimo trovato stringendo il clock). I livelli risultanti diventeranno il
**menu quantizzazione** del blocco `Donatello_Tier` (una Fase a sé, dopo questo studio).

## 2. Obiettivo e criteri di successo

Obiettivo: **caratterizzare il trade-off quantizzazione** e produrre i livelli `nfrac` deployabili con la loro
configurazione canonica.

Successo = tutti veri:
1. Quattro curve vs `nfrac` — **accuratezza · risorse · potenza · Fmax/delay** — da **misura reale** (sintesi,
   non stima), sul dataset.
2. **Ginocchio** individuato e **provato in due modi**: max|d| dei parametri **+** car-following end-to-end.
3. Per **ogni** livello `nfrac` scelto, la **configurazione canonica** = Fmax massimo via ricerca a passo
   adattivo sul vincolo di clock.
4. Tutto **isolato** in `matlab/Quantizzation_Study/`; gli script originali **non modificati** (verificabile:
   `git diff` sugli originali resta vuoto).

## 3. Scope e isolamento

**In scope**
- Nuova cartella `matlab/Quantizzation_Study/` che contiene **tutto** lo studio.
- Le quattro curve, il ginocchio, la validazione car-following, la configurazione canonica, le figure e un doc.

**Fuori scope (ora)**
- Modificare qualunque script funzionante — **regola ferrea: si copia, non si tocca** (§3.1).
- Il **menu quantizzazione** del blocco (Fase successiva, brainstorming a sé).
- **Per-campo mixed-precision** (§8, future work).
- Ri-training / QAT (lo studio è **PTQ**: cambia i tipi, non ri-addestra il champion).

### 3.1 Regola di isolamento
Ogni script riusato viene **copiato** in `Quantizzation_Study/` (con suffisso o prefisso chiaro, es.
`qz_run_fixed_sweep.m`) e modificato **solo lì**. Gli originali (`run_fixed_sweep.m`, `snn_types.m`,
`snn_b2_fsm.m`, `build_tier_blocks.m`, `study_tradeoff/common/impl_point.tcl`, …) restano bit-identici.
Cancello di isolamento: `git diff --stat` sugli originali → nessuna riga cambiata.

## 4. Metriche (le quattro curve, vs `nfrac`)

| Curva | Fonte | Note |
|---|---|---|
| **Accuratezza** — max\|d\| sui 5 parametri | `qz_run_fixed_sweep` (copia di `run_fixed_sweep`) | primaria, conservativa; floor double ≈ 2e-6 |
| **Risorse** — LUT / DSP / FF | sintesi OOC per ogni `nfrac` | dalla util report |
| **Potenza dissipata** | `report_power` alla sintesi | **vectorless** per la mappa; **SAIF** (traiettoria) sul candidato |
| **Fmax / delay** | timing **io-timed** della sintesi | stesso metro dello Studio A |

Metrica di conferma: **accuratezza car-following end-to-end** (anello chiuso) al ginocchio — perché max|d| è
conservativo, e il vero obiettivo è il comportamento in strada.

## 5. Fasi

### 5.0 — Setup cartella + copie isolate
Creare `matlab/Quantizzation_Study/`. Copiare gli script da riusare con nome dedicato (`qz_*`). Verificare il
cancello di isolamento (§3.1).

### 5.1 — Accuratezza vs `nfrac`
`qz_run_fixed_sweep`: copia di `run_fixed_sweep` con **griglia estesa** attorno al ginocchio —
`nfrac ∈ {5,7,8,9,10,11,12,13}` (oggi 5/7/9/11/13). Output: tabella champion × `nfrac` → max|d| param, sul
dataset. Se il core `fi` interpretato è lento, **MEXare** (riuso di `build_traj_mex`/`snn_traj_fixed` copiati),
mai ridurre il dataset.

### 5.2 — Generazione del blocco a `nfrac` variabile
Il forward `snn_b2_fsm.m` **hardcoda** `snn_types('fixed', 13)`. Nella copia isolata (`qz_snn_b2_fsm.m`) il `13`
diventa un **parametro** `nfrac`. Un `qz_build_block(nfrac)` (copia mirata di `build_tier_blocks`) genera il
blocco Donatello a quel `nfrac`. **Cancello:** a `nfrac=13` il blocco copia deve essere **bit-identico**
all'originale (dmax=0 vs riferimento) — prova che la parametrizzazione non ha alterato la logica.

### 5.3 — Sintesi: risorse / potenza / Fmax vs `nfrac`
Per ogni `nfrac` della griglia: genera il blocco (§5.2), `makehdl`, **sintesi OOC** al vincolo io-timed di
deploy (copia di `impl_point.tcl` → `qz_impl_point.tcl`), estrai **LUT/DSP/FF** (util), **potenza** (report_power
vectorless) e **Fmax/delay** (timing). Determinismo: thread e seme fissi (come Studio A). Lento → background.

### 5.4 — Il ginocchio + livelli candidati
Incrocio **accuratezza ↔ risorse/potenza**: il `nfrac` **minimo** dove max|d| è ancora al floor (o sotto una
soglia comportamentale) mentre risorse/potenza sono già scese. La mappa è **non-lineare** (soglie brusche: a
bassa precisione uno spike si ribalta) → infittire la griglia dove la curva svolta. Escono i **livelli
candidati** (il minimo + un paio di margine) per il menu.

### 5.5 — Validazione car-following al ginocchio
Per i livelli candidati (non tutta la griglia): anello chiuso (`qz_snn_cl_step`/plant, copie) sul dataset →
verifica che l'errore sui parametri **non degradi il controllo reale** (metrica car-following, es. accuratezza
di inseguimento / gap). Conferma o corregge la scelta del ginocchio.

### 5.6 — Configurazione canonica (Fmax massimo, ricerca a passo adattivo)
Per **ogni** livello `nfrac` che andrà nel blocco, trovare il Fmax massimo stringendo il vincolo di clock:

```
input:  P0 (periodo iniziale con slack >= 0 comodo), step0 (passo iniziale, es. 4 ns),
        step_min (LIMITE sul PASSO, mandatory — niente default silenzioso, es. 0.25 ns)
P    = P0 ; step = step0 ; best = P0
while step >= step_min:
    P_try = P - step                      # clock più veloce
    slack = synth_io_timed(nfrac, P_try)  # una sintesi
    if slack >= 0:
        best = P_try ; P = P_try          # accetta e continua a stringere
    else:
        step = step / 2                   # torna indietro (non accetti) e dimezza il passo
Fmax_max = 1 / best
```

Il limite è sul **passo** (`step_min`), non sul periodo: si continua a raffinare il passo finché non scende
sotto la soglia (altrimenti la ricerca non termina). L'ultimo `P` con slack ≥ 0 è il Fmax massimo di quel
livello → **configurazione canonica** `(nfrac, Fmax_max, risorse@Fmax_max)`. Ogni iterazione è una sintesi
io-timed (riuso `qz_impl_point.tcl`). Costo per livello ≈ 5–10 sintesi.

## 6. Output

- **Quattro figure** (accuratezza · risorse · potenza · Fmax/delay vs `nfrac`), col **ginocchio** segnato.
- **Tabella livelli**: per ogni `nfrac` candidato → max|d|, car-following, LUT/DSP/FF, potenza, Fmax-deploy,
  **Fmax-max (config canonica)**.
- **Doc dello studio** (grounded sui dati, stile `DECODE_LUT_SWEEP.md`), sorgente per un futuro report.
- I livelli + config canonica = **materia prima del menu quantizzazione** (Fase successiva).

## 7. Metodo e gate (vincolanti)

- **Dataset, mai campione** — riportare *quanti su quanti* (già in `run_fixed_sweep`).
- **Risorse / potenza / Fmax da sintesi reale**, non stima.
- **Ginocchio provato in due modi** (max|d| + car-following).
- **`step_min` esplicito** nella ricerca del Fmax (parametro obbligatorio).
- **Cancello di isolamento** (§3.1) + **cancello bit-exact** della copia a `nfrac=13` (§5.2).
- **MEX** se lo sweep è lento; determinismo di sintesi (thread/seme fissi).

## 8. Future work (registrato)

- **Per-campo mixed-precision**: bit frazionari **indipendenti** per V / fatigue / acc / raw / w
  (fpga-expert: aggressivo sui campi insensibili, alta precisione sui sensibili). "Fin dove può arrivare la
  rete", a tempo perso — spazio di ricerca ampio, menu multi-asse. Fuori da questo studio.

## 9. Rischi e note

- **Parametrizzazione `nfrac` del forward**: rischio principale è alterare la logica copiando `snn_b2_fsm`; il
  cancello bit-exact a `nfrac=13` (§5.2) lo blinda.
- **Costo di sintesi**: griglia (~8 `nfrac`) × 1 sintesi (mappa) + livelli × ~5–10 (Fmax) → decine di sintesi,
  lente → background. `log()` di ciò che si salta se si campiona.
- **Potenza**: vectorless per la mappa (confronto **relativo** fra `nfrac`), SAIF solo sul candidato (assoluto).
- **Onestà su Fmax = margine**: la config canonica al Fmax massimo è **caratterizzazione del limite**, non una
  necessità operativa (il control-step ha margine ~10³–10⁴×); è però la definizione richiesta di "config
  canonica" e va documentata come tale.
- **Rounding/overflow**: lo sweep varia i soli frazionari con i default fixed attuali (già bit-exact a f=13);
  se a bassa precisione emergono bias, valutare convergent-rounding/saturation (fpga-expert ch09) — nota, non
  scope iniziale.

## 10. Riferimenti

| Riferimento | Tema |
|---|---|
| `matlab/run_fixed_sweep.m` · `matlab/snn_types.m` | accuratezza vs `nfrac`, tipi parametrici (da copiare) |
| `matlab/snn_b2_fsm.m` (Q?.13 hardcoded) · `matlab/build_tier_blocks.m` | generazione blocco (da copiare/parametrizzare) |
| `matlab/study_tradeoff/common/impl_point.tcl` · `RESULTS.md §15-16` | sintesi io-timed + ricerca Fmax (Studio A) |
| `snn_cl_step` + plant (anello chiuso) | validazione car-following |
| fpga-expert ch09 (Q-format, rounding, saturation, SQNR) · ch13 (PTQ vs QAT, uniform quant) | metodo e pitfall |
