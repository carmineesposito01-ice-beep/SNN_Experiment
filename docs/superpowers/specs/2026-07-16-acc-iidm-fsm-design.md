# SP4-M-FSM — ACC-IIDM time-mux via FSM + blocco Divide pipelinato: recuperare l'Fmax — Design

**Data:** 2026-07-16 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Recuperare l'Fmax dell'ACC-IIDM in fixed a **≥ 11,65 MHz** (pari alla SNN dopo la correzione Fase B) **e** tagliare
l'area, **sequenziando le 5 divisioni su un unico divisore pipelinato** controllato da una macchina a stati (FSM).
Vincolo invalicabile: **bit-identico a SP3 (`dmax = 0`)** — nessuna approssimazione (la differenza chiave rispetto
a L, scartata proprio perché approssimava).

## 2. Contesto — perché la FSM (dopo M-config)
`document/SP4_ACC_IIDM_FAST.md` §Variante M: il **resource sharing config-based** (SP4-M v1) è stato eseguito
(make-or-break 2026-07-16). Esito misurato OOC (xc7z020 @8 MHz):

| config | LUT | FF | DSP | Fmax | path critico |
|---|---|---|---|---|---|
| baseline (=SP3) | 10 846 | 1 653 | 69 | **2,01 MHz** | 5 divisioni **incatenate** (1077 liv.) |
| share5_cp (SF5, CRP on) | 25 557 | 22 922 | 38 | **9,51 MHz** | **1 divisione** (`quotient_tmp`, 172 liv.) |

Il resource sharing sequenzia le 5 divisioni in una e fa chiudere il timing, **ma**: (1) Fmax 9,5 < 11,65 (collo =
**singola divisione digit-recurrence non pipelinata**); (2) area **esplosa** (LUT ×2,36, FF ×13,9 dal clock-rate
pipelining) → contro la visione «taglia le risorse». Decisione utente: **FSM esplicita**.

**Cosa insegna M-config alla FSM:** il collo residuo è **dentro** la singola divisione (i 172 livelli della
digit-recurrence combinatoria). Recuperare l'Fmax richiede quindi di **pipelinare la divisione stessa**, non solo di
condividerla. E va fatto **senza** il clock-rate pipelining che esplode l'area.

## 3. Approccio — deciso da una VERIFICA (API HDL Coder)
Verificato sulle docs MathWorks (2026-07-16): la divisione **pipelinata bit-esatta** in HDL Coder passa per il blocco
**`Divide`** (architettura `ShiftAdd`, digit-recurrence iterativa), **non** per la funzione `divide()` dentro una
MATLAB Function (quella genera la digit-recurrence **combinatoria**, i 172 livelli). Il blocco `Divide`:
- interfaccia `dividendDataIn, divisorDataIn, validIn → dataOut, validOut`;
- **latenza fissa e nota** (deterministica), es. 39 cicli — schedulabile da una FSM;
- `LatencyStrategy` regolabile: `Max` (L=N+4), `Custom(PerIteration)` (L=2+⌊N/K⌋, K=`IterationsPerPipeline`) →
  baratto latenza↔Fmax↔area.

**Nodo (misurato, non assunto):** la doc **non garantisce** che il blocco `Divide` sia bit-identico a
`divide(numerictype(T.acc),·,·)` di SP3 (l'unico confronto mostrato è vs `double`, errore ~1,5e-5). Quindi la
bit-identità è **da verificare per prima cosa** (Task 1, §6 G1), non data by construction. Scelta utente
(2026-07-16): **Approccio #1 — blocco `Divide` condiviso + gate di bit-identità**; fallback **#2** (divisore
sequenziale a mano che replica `divide()`) o **#3** (ri-baselinare SP3 sul divisore pipelinato) se il gate fallisce.

## 4. Architettura
Nuovo blocco **`Donatello_ACC_IIDM_M`** in `snn_champions_lib`. L'attuale `Donatello_ACC_IIDM` (SP3) **resta**: è il
riferimento di bit-identità e il baseline OOC. Interno del subsystem:

```
 s,v,dv,v_l ──►┌─────────────────────────────┐  num,den,validIn   ┌──────────────┐
               │  MATLAB Function  IIDM_CTRL │ ─────────────────► │ Divide (HDL) │
               │  • matematica IIDM non-÷    │                    │  ShiftAdd    │
               │    (sqrt,mul,add,clamp,     │ ◄───────────────── │  latency L   │
               │     tanh, z², filtro OU)    │   quot, validOut    └──────────────┘
               │  • FSM di scheduling        │       (feedback ritardato di L)
               └─────────────┬───────────────┘
                             └──► accel
```

- **`IIDM_CTRL`** (MATLAB Function, gira a rate di clock come `snn_b2_fsm`): tutta la matematica IIDM **non-÷**,
  copiata **verbatim** da `acc_iidm_open` (stessi cast, stessi tipi `acc_types`), *non riscritta* — la lezione §2.1
  (due implementazioni della stessa matematica divergono in silenzio). In più la **FSM di scheduling** che serializza
  le 5 divisioni. Stato `persistent`: fase FSM, risultati parziali (`s_star, z, a_iidm, a_cah…`), stato OU
  (`alf, vlp`).
- **1 blocco `Divide` HDL** condiviso (ShiftAdd, `LatencyStrategy` custom), esterno alla chart: `(num,den,validIn) →
  (quot,validOut)` dopo latenza fissa L. La latenza rompe il loop algebrico del feedback.
- **Interfaccia esterna:** identica a SP3 — fisica `s,v,dv,v_l → accel`, **edge-triggered** internamente (1 campione
  = 1 inferenza), **niente `start`/`done` esposti** (§3.1.2, fail-silenzioso).

Scelte fissate: **un solo divisore, 5 divisioni seriali** (le dipendenze impongono quasi-serialità, il budget 341
clock la copre); **matematica non-÷ verbatim**, con la bit-identità M-vs-SP3 sul dataset come rete di sicurezza.

## 5. Data flow e timing della FSM
Le 5 divisioni (da `acc_iidm_open`) e le dipendenze:

| slot | divisione | den | serve a | dipende da |
|---|---|---|---|---|
| 1 | `q1 = vq·dq / (2·sab)` | `2·sab` (`sab=√(af·bf)`) | `s_star` | — |
| 2 | `q2 = vq / v0f` | `v0f` | `v_free` | — |
| 3 | `q3 = s_star / s_safe` | `s_safe` | `z=min(q3,20)` | **q1** |
| 4 | `q4 = max(dq,0)² / (2·s_safe)` | `2·s_safe` | `a_cah` | — |
| 5 | `q5 = (a_iidm−a_cah) / bf` | `bf` | `dd→a_blend` | **q3, q4** |

Ordine seriale **q1→q2→q3→q4→q5** soddisfa tutte le dipendenze (q3 dopo q1; q5 dopo q3 e q4). FSM:

```
IDLE ─(nuovo campione: edge-trigger)─► PREP0: OU(alf), guardie, sab, s_safe   (matematica non-÷ iniziale)
  per k = 1..5:
    PREP_k : calcola (num_k, den_k) dallo stato
    ISSUE_k: validIn=1, invia (num_k,den_k) al Divide
    WAIT_k : attende validOut=1        (≈ L cicli)
    USE_k  : latcha quot_k, calcola ciò che dipende (q1→s_star ; q3→z,a_iidm ; q4→a_cah ; …)
  DONE   : dd,a_blend, clamp finale → accel ; torna in IDLE
```

- **Attesa su `validOut`, non a contatore** — non dipende dal numero magico L (robusto alla config del Divide).
- **La divisione per `DT`** (filtro OU, denominatore **costante** 0,1) **resta inline** (`divide()` costante →
  moltiplicatore shallow, non è un collo): la FSM orchestra **solo le 5 divisioni a divisore variabile**.
- **Latenza totale** ≈ 5·(1+L) ≈ 150-220 cicli ≪ **341** di budget → un divisore basta, niente pressione sul
  throughput.

## 6. Bit-identità e verifica — la batteria di cancelli
Ogni problema Donatello ha il suo cancello, **sul dataset, assertivo, provato sensibile**.

| # | cancello | verifica | previene | sensibile |
|---|---|---|---|---|
| **G1** | gate divisore (**Task 1**) | blocco `Divide` == `divide()`-SP3 su **300k coppie reali**, `assert dmax==0` | cast/aritmetica divergente §2.1 | rounding `Nearest` → **deve** fallire |
| **G2** | parità dataset (MEX) | `acc_iidm_fsm`(+`divide()`) == `acc_iidm_open` fixed su **60×1000**, `assert dmax==0` | buco copertura 16/1000 (§2.1) | mis-ordine ÷ / cast prematuro → fallisce |
| **G3** | blocco vs model (streaming, campione K) | blocco Simulink M **reale** == `acc_iidm_fsm` model | il buco §2.1 (2 implementazioni) | — |
| **G4** | edge-trigger | latenza misurata; ingresso costante → **1 sola** inferenza | free-running §3.1.4 / `start` scollegato §3.1.2 | forzo free-running → più inferenze → fallisce |
| **G5** | hdl gate (`run_block_hdl_gate` esteso) | VHDL dal solo `.slx` + entità Divide pipelinato | non-HDL-ready | blocco non self-contained → fallisce |
| **G6** | OOC (`synth_acc_iidm.tcl`) | **Fmax ≥ 11,65** · area ≪ M-config (LUT/FF giù) | — (bersaglio) | baseline SP3 riprodotto = coerenza |
| **G7** | plant parity (`run_plant_parity`) | `acc_iidm_open` **double** invariato | regressione del riferimento | — (invariato per costruzione) |

**Il gate G1 (Task 1) in dettaglio:** dati **reali, non sintetici** (il bug vive nelle code) — strumentando
`acc_iidm_open` fixed sul dataset intero si estraggono le ~300k coppie `(num,den)` che le 5 divisioni assumono
davvero (denominatori sui clamp, numeratori grandi inclusi). Per ogni coppia: `Divide(num,den)` (ShiftAdd, rounding
per matchare 'Zero', I/O `T.acc`) vs `divide(numerictype(T.acc),num,den)`; `assert(dmax==0)` bit-per-bit. Provato
sensibile col rounding `Nearest`. Esito `dmax==0` → M bit-identico a SP3 by construction; `dmax>0` → STOP, si valuta
#2/#3 coi dati in mano.

> **Operandi al blocco Divide.** `num/den` nascono con tipi diversi (`T.st`, `T.par`, `T.acc` a seconda della
> divisione), mentre `divide(numerictype(T.acc),·,·)` gestisce internamente lo scaling. Il blocco `Divide` opera sui
> tipi delle sue porte → G1 deve determinare **l'eventuale pre-scaling/cast** degli operandi che rende il risultato
> bit-identico a `divide()` per **tutte** e cinque le divisioni. Il pre-scaling, se serve, è parte della definizione
> del gate: senza, `dmax==0` non è nemmeno raggiungibile. È un output atteso del Task 1, non un dettaglio rinviato.

**Bit-identità per transitività** (chiude la catena senza un unico cancello lento):
```
G1: Divide == divide()            (isola il divisore)
G2: acc_iidm_fsm+divide == acc_iidm_open   (isola la ristrutturazione FSM)
G3: blocco reale == acc_iidm_fsm model     (isola l'integrazione Simulink/handshake)
   ⇒  blocco M == SP3  bit-per-bit sul dataset
```

**Difese strutturali (anti-§2.1):**
- **Single-source, o si ricrea il buco.** Il buco §2.1 erano *due* implementazioni. La logica FSM `acc_iidm_fsm` è
  **una**: il blocco la inlina e G2 la chiama (stesso codice); la matematica non-÷ è in **funzioni locali condivise**
  fra model e chart. L'unico pezzo che il model MEX non esegue è il blocco `Divide` (è Simulink) → coperto da G1+G3.
- **MEX obbligatorio.** Girare il blocco Simulink su 60×1000×~341 clock ≈ 20 M passi = ore (il muro di Donatello) →
  G2 gira il **model MEX-abile** sul dataset (secondi); G3 gira il **blocco reale** solo su un campione K. Nessun
  campionamento silenzioso: se si restringe, si dichiara.
- **Disciplina dei tipi:** risultati parziali nei `persistent` con **esattamente** i tipi `acc_types` (fimath 'Zero'
  parte del tipo), **nessun cast che stringe un valore prima di usarlo** (il meccanismo del bug 82,4%); `x(:)=…` per
  non cambiare tipo/fimath (§9); range dei `fi` costanti verificati; warning HDL Coder letti.

## 7. File (previsti)
| file | ruolo |
|---|---|
| `matlab/probe_divide_bitexact.m` | **NUOVO** — G1 (Task 1) |
| `matlab/acc_iidm_fsm.m` | **NUOVO** — logica FSM: matematica non-÷ verbatim (funzioni locali condivise) + scheduling; single-source per model e chart |
| `matlab/build_acc_iidm_fsm_mex.m` (+ MEX) | **NUOVO** — G2 sul dataset in secondi |
| `matlab/run_acciidm_m_dataset.m` | **NUOVO** — G2 |
| `matlab/run_block_acciidm_m_test.m` | **NUOVO** — G3 + G4 |
| `matlab/build_hdl_variants.m` | **MODIFICA** — costruisce `Donatello_ACC_IIDM_M` (chart + blocco `Divide` + feedback) |
| `matlab/run_block_hdl_gate.m` | **MODIFICA** — criterio M: VHDL + Divide pipelinato |
| `scripts/synth_acc_iidm.tcl` · `matlab/run_plant_parity.m` | **RIUSO** — G6 · G7 |
| `document/SP4_ACC_IIDM_FAST.md` · `document/SESSION_RESUME.md` | **MODIFICA** — esito/stato |

**Punto implementativo delicato:** il rischio §2.1 residuo è fra il *model* `acc_iidm_fsm` e la *chart* del blocco
(due contenitori della stessa matematica). Difesa: matematica non-÷ in **funzioni locali condivise** (single-source),
e **G3** confronta blocco reale vs model. Se divergono, G3 li becca.

## 8. Ordine dei task
1. **Task 1 = G1, make-or-break.** Blocco `Divide` == `divide()`-SP3 (300k coppie, assert, sensibile). **Se fallisce
   → STOP**, si torna dall'utente coi dati per #2 (divisore a mano) o #3 (ri-baselinare).
2. **Task 2** — `acc_iidm_fsm.m` (matematica verbatim + FSM, `divide()` inline) + MEX + **G2** (parità dataset).
3. **Task 3** — blocco `Donatello_ACC_IIDM_M` (chart + blocco `Divide` + feedback) + **G3** + **G4**.
4. **Task 4** — **G5** (hdl gate) + **G6** (OOC): il **verdetto Fmax ≥ 11,65** e l'area vs SP3 e vs M-config.
5. **Task 5** — doc + **G7** + cancelli finali + commit/push.

## 9. Fuori scope (esplicito, YAGNI)
- **Overlap** SNN(k+1)‖IIDM(k) (throughput) — secondo giro.
- **Sweep a slack minima** (massimo Fmax assoluto) — studio separato.
- **Bitstream / `.bit` / deploy** — M resta HDL-ready + OOC.
- **Promuovere M a deploy o sostituire SP3 in-place** — decisione dopo la validazione.
- **v2** = sequenziare *tutto* il datapath (non solo le ÷) — confronto successivo, solo se serve.
- Altri champion, chiudere il loop nel blocco.
