# FPGA Fase C — Validazione su silicio (PYNQ-Z1) — design

> **Data:** 2026-07-11 · **Branch:** `Simulink_Importer` · **Stato:** design **LOCKED** (approvato)
> · **Target:** Donatello B2 su **PYNQ-Z1 fisica** (Zynq-7020, 28nm)
>
> Chiude il ciclo Fase A (op-count, `FPGA_REPORT`) → Fase B (stima Vivado+SAIF, `FPGA_PHASE_B_POWER.md`) →
> **Fase C (silicio)**. Predisposta in Fase B (§9 del deliverable: `.bit`/`.hwh`, `stim_typical.mem`,
> `run_on_pynq.py`, protocollo bozza). Questo doc progetta l'harness completo.

---

## 0. Decisioni di scope (dal brainstorming)

| Decisione | Scelta |
|---|---|
| **Disponibilità HW** | Board **non ancora presente, in arrivo** → **design-for-later**: codice + goldens pronti ORA, esecuzione quando arriva. |
| **Misura potenza** | **Solo total-board** (ingresso barrel/USB), niente sensing invasivo del rail PL. |
| **Obiettivo primario** | **Verifica funzionale su silicio**: il chip genera i 5 parametri corretti e coerenti col comportamento atteso. |
| **Obiettivi potenza** | **Sanity/upper-bound** sul PL dynamic + **potenza totale di deploy** (i ~9 mW del PL sono sotto la risoluzione total-board). |
| **Approccio** | **A + C**: sweep funzionale open-loop **+** closed-loop network-in-the-loop **+** potenza total-board. |

**Realtà tecnica dichiarata:** PL dynamic (Fase B) ~9 mW vs potenza totale PYNQ-Z1 ~1.5-2.5 W (dominata dai
2 core ARM del PS) → i 9 mW sono ~0.4% del totale, **sotto la risoluzione** di una misura total-board tipica.
La Fase C quindi **non** produce un numero PL preciso: produce (1) la **prova che il deploy funziona**, (2) un
**upper-bound** onesto sul PL, (3) la **potenza totale di sistema** (numero di deploy utile).

**Principio-chiave (il valore della Fase C):** il silicio esegue lo **stesso RTL** del cosim → i param su
silicio *devono* riprodurre la simulazione **bit-exact**. Una discrepanza **non è un bug d'algoritmo** (già
validato in Fase B, err=0) ma un **bug di deployment/integrazione** — normalize float sul PS, packing/endianness
`xn`, protocollo AXI (start-pulse/done-poll), timing I/O. La Fase C valida l'**ultimo miglio** (dal bitstream al
sistema funzionante), non la rete.

---

## 1. Architettura

Un **notebook Jupyter PYNQ** (workflow nativo della board) che orchestra deploy + validazione + potenza, con
tre deliverable. **Design-for-later:** i moduli si scrivono e si **unit-testano con un mock dell'overlay** ORA;
solo l'esecuzione reale (overlay + I/O + letture potenza) aspetta la board.

1. **Sweep funzionale (open-loop)** — feed traiettorie di test → normalize sul PS → xn/start/done/params →
   confronto col riferimento precalcolato → distribuzione d'errore. *Prova che il chip genera i param giusti.*
2. **Closed-loop network-in-the-loop** — SNN sul PL + plant ACC-IIDM sul PS → car-following in tempo reale →
   confronto col golden di simulazione. *Prova che il sistema deployato si comporta bene nel tempo.*
3. **Potenza total-board** — idle / PS-only / attivo → letture total-board → upper-bound PL + `P_deploy`.

---

## 2. Componenti (unità isolate, interfacce nette)

### (1) Generatore di riferimento — `matlab/gen_phase_c_reference.m` *(gira ORA sul PC)*
Esegue `snn_top_b2` fixed (cyclo-accurato) sulle traiettorie di test → **param attesi** per input; ed esegue
la **simulazione closed-loop** (rete fixed + plant ACC-IIDM, riusando la logica di `make_plant_golden.py`) →
**traiettoria golden** (ego x/v/gap nel tempo). Output: `phase_c/goldens/phase_c_reference.csv` +
`phase_c_closedloop_golden.csv`. Sono i goldens **spediti col harness**.
> **Correttezza (stato ricorrente):** il riferimento è generato dallo **stesso modello stateful** (snn_core/
> snn_top_b2 fixed) alimentato con la **stessa sequenza, nello stesso ordine**, come farà il silicio → il match
> è garantito **qualunque sia la semantica di reset/persist** dello stato ALIF tra inferenze/control-step: la si
> **eredita dal modello, non la si assume**. L'harness deve quindi alimentare il silicio nella stessa identica
> sequenza (nessun reset implicito tra i passi, se il golden non lo fa).

### (2) Driver — `matlab/axi/phase_c/pynq_snn.py` (classe `SnnDonatello`, estende `run_on_pynq.py`)
Carica l'overlay; **normalize sul PS** (float, costanti Donatello `norm=[150,40,20,40]`) → Q5.13; register-map
I/O (write `xn`, start-pulse, poll done, read params Q7.13 → fisico). **Interfaccia:** `infer(s,v,dv,vl) →
[v0,T,s0,a,b]`. Dipende solo da `.bit`/`.hwh`. Register map da `matlab/axi/README.md`.

### (3) Sweep funzionale — `matlab/axi/phase_c/test_functional.py`
Feed di tutte le traiettorie di test → `driver.infer()` → confronto coi param attesi (#1) → **distribuzione
d'errore** (max/RMS/istogramma per-param). Pass: bit-exact al fixed (≤1 LSB), ≤0.028 vs PyTorch.

### (4) Closed-loop — `matlab/axi/phase_c/test_closedloop.py` + `plant_iidm.py`
`plant_iidm.py` = port Python del plant ACC-IIDM (da `make_plant_golden.py`, **stesso codice** del golden per
match bit-exact). Loop: leader → (s,v,dv,vl) → `driver.infer()` → plant accel dai param → integra ego → next.
Registra la traiettoria ego, confronto col golden closed-loop (#1) → **errore di traiettoria**.

### (5) Potenza — `matlab/axi/phase_c/measure_power.py` (strumento-agnostico, procedura guidata)
Tre stati per **isolare il PL dal rumore del loop Python**: *idle* (overlay, nessuna inferenza) · *PS-only*
(loop Python a vuoto, stesso rate, senza triggerare il PL) · *attivo* (inferenza continua). L'utente legge la
potenza total-board dal suo strumento in ognuno; il modulo calcola `PL_dyn ≈ P_attivo − P_PS-only` e
`P_deploy = P_attivo`. Se il delta < risoluzione → **upper-bound onesto**.

### (6) Notebook orchestratore — `matlab/axi/phase_c/phase_c_validation.ipynb`
Cabla #2-#5: load overlay → sweep funzionale → closed-loop → potenza guidata → **riempie la tabella "Fase C"**
del deliverable Fase B + un breve `document/FPGA_PHASE_C_REPORT.md`.

### Mock per i test ORA — `matlab/axi/phase_c/mock_overlay.py`
Overlay fake che, su `read params`, rilegge i param attesi dal riferimento (#1) → i moduli #3/#4 si
unit-testano **senza board** (verificano la logica di normalize/confronto/loop, non l'hardware).

---

## 3. Flusso dati

```
[PC, ORA] gen_phase_c_reference.m:
   test_traj → snn_top_b2(fixed) ─────────────→ phase_c_reference.csv        (param attesi)
   leader + rete fixed + plant ACC-IIDM ──────→ phase_c_closedloop_golden.csv (ego x/v/gap)

[Board, DOPO] phase_c_validation.ipynb:
   overlay = Overlay(snn_b2_donatello.bit)
   sweep:   (s,v,dv,vl)→normalize(PS float)→Q5.13→AXI write→start→poll done→read Q7.13→fisico
            → vs reference.csv → distribuzione errore
   closed:  leader→[ego→(s,v,dv,vl)→driver.infer→plant accel→integra]→ego traj
            → vs closedloop_golden.csv → errore traiettoria
   power:   idle / PS-only / attivo → letture total-board → PL_dyn (upper-bound) + P_deploy
   → colonna "Fase C" + FPGA_PHASE_C_REPORT.md
```

---

## 4. Onestà / gestione errori (limiti dichiarati in testa)
- **Potenza < risoluzione:** se il delta idle/attivo è nel rumore → "PL_dyn < risoluzione, coerente con Fase B
  ~9 mW" (upper-bound, non numero). Lo stato *PS-only* isola il PL dal costo del loop Python; se resta nel
  rumore, upper-bound e basta. `P_deploy` (totale) resta comunque un numero utile.
- **Mismatch funzionale = bug di deployment, si investiga la causa** (normalize float-PS vs fixed a 1 LSB,
  packing/endianness `xn`, start-pulse/done-poll AXI, timing) — **non si aggiusta il numero**.
- **Divergenza closed-loop:** prima si verifica che i param **per-step** siano bit-exact (isola la rete), poi la
  dinamica → una divergenza è integrazione (dt/ordine/feedback), non la rete.

## 5. Criteri di successo
1. **Funzionale:** i 5 param su silicio == riferimento fixed **bit-exact** (≤1 LSB) su tutte le traiettorie di
   test; errore vs PyTorch ≤0.028 (v0). → il chip fa il task.
2. **Closed-loop:** ego su silicio == golden **bit-exact** (se il plant PS è lo stesso codice del golden;
   fallback RMS<soglia dichiarata se differenze float di piattaforma). → il sistema deployato si comporta bene.
3. **Potenza:** `P_deploy` totale caratterizzata; `PL_dyn` confermato trascurabile/upper-bound coerente con Fase B.
4. **Ready-to-run:** harness + goldens committati; **unit-test col mock verdi ORA**; solo l'esecuzione board resta,
   documentata in un **runbook "quando arriva la board"**.

## 6. Vincoli permanenti (dal progetto)
- **Core SNN congelato**: la Fase C non tocca `snn_core`/RTL; usa il `.bit` esistente. Il plant è port 1:1 del
  golden (nessuna logica nuova d'algoritmo).
- **Niente work-around**: mismatch → si investiga la causa (deployment), non si aggira.
- Commit **senza** `Co-Authored-By`.

## 7. Decisioni aperte (minori)
- Strumento di potenza: alimentatore da banco (lettura corrente) vs meter inline USB/barrel — **agnostico**;
  la procedura #5 chiede solo un numero di potenza total-board per stato.
- Numero di traiettorie nello sweep funzionale: default = tutte le 6 di `test_trajectories.mat` (già usate in
  Fase B).
- Soglia RMS del fallback closed-loop: da fissare in fase di piano (default: < 1 LSB fisico sui param → gap RMS
  trascurabile).
