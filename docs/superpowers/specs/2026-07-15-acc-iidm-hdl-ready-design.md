# SP3 — ACC-IIDM **HDL-Ready** (fixed-point) — Design

**Data:** 2026-07-15 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Rendere l'ACC-IIDM **HDL-Ready** in fixed-point, così che `Donatello_ACC_IIDM` (catena `s,v,dv,v_l → accel`)
smetta di essere «sola simulazione» e HDL Coder ne generi il VHDL.

**Perché adesso, e perché conta:** serve al **confronto MPC ↔ SNN**
(`docs/superpowers/specs/2026-07-13-mpc-vs-snn-comparison-design.md`). Quella spec dice due cose che oggi
sono in contraddizione fra loro:
- §5: «la legge ACC-IIDM **appartiene al nostro controllore**» (la SNN ne fornisce solo i parametri);
- §3, Piano 2: «FPGA synthesis (**both realized**) — what does each cost in silicon?».

Con l'IIDM in double, il Piano 2 conterebbe **solo la rete (~4,2k LUT)** e ometterebbe **in silenzio** la legge
che produce `a_cmd`, mentre per l'MPC conterebbe tutto il risolutore QP. La headline attesa («l'MPC è
FPGA-hard, la SNN no») sarebbe **viziata a nostro favore**. Questo SP chiude quel buco.

**Obiettivo esplicito:** HDL-Ready **+ numeri OOC** (LUT/DSP/Fmax su `xc7z020`). **Niente bitstream, niente
deploy** su PYNQ-Z1.

## 2. ⚠️ Premessa smentita — perché questo SP è piccolo
La spec SP2 §7 e `document/SP2_ACC_IIDM.md` dichiaravano: *«ACC-IIDM su FPGA è un SP a sé — `sqrt(a·b)` e le
divisioni sono lo stesso genere di problema che per la sigmoide ha richiesto una LUT»*. Era una **claim mai
verificata**. Misurata il 2026-07-15 dando a HDL Coder una operazione per volta, in fixed, isolata:

| operazione | HDL Coder | conseguenza |
|---|---|---|
| `sqrt(x)` | ✅ VHDL generato | **nessuna LUT** |
| `tanh(x)` | ✅ VHDL generato | **nessuna LUT** |
| `x^4` | ✅ VHDL generato | — |
| `a / b`, `1 / b` | ❌ rifiutato… | …**solo per l'arrotondamento** (sotto) |
| `exp(x)` | ❌ rifiutato | irrilevante: `ALPHA = exp(−0.1)` è **costante** → si bake |

Il rifiuto della divisione **non** è una mancanza di supporto. Messaggio testuale del report:

> *«"Zero" rounding method is supported for signed or unsigned division, whereas "Floor" rounding method is
> supported for unsigned division»*

Il default della chart è `Nearest` → rifiutata. Con `RoundingMethod = 'Zero'` **il VHDL si genera**
(verificato in due forme: `setfimath` + `/`, e `divide(numerictype(…), a, b)`).

> **Nota**: il precedente della sigmoide era reale ma **non trasferibile**: σ(x) = 1/(1+**exp**(−x)) e `exp` è
> davvero l'unica non supportata. `tanh` no. Analogia plausibile, e falsa.

⇒ **Niente LUT, niente Newton-Raphson, niente time-mux del divisore.** Resta una **tipizzazione fixed-point**.

## 3. Dinamica misurata (60 traiettorie × 1000 step, parametri veri stimati)
| intermedio | min | max | note |
|---|---|---|---|
| `a_z`, `a_iidm` | **−288.33** | 1.13 | `z→20 ⇒ a·(1−z²)≈−288`: grande ma **limitato** |
| `s_star` | 2.02 | 465.77 | |
| `dd` | **−163.06** | 4.81 | ingresso di `tanh`: **satura** a ±1 |
| `s_safe` | 2.00 | 150.00 | |
| `dv²/(2·s_safe)` | 0.00 | 105.09 | |
| `alf` / `z` | −21.19 | 20.00 | |
| `accel` | −9.00 | 1.08 | |
| `min(v/v0,10)` | 0.00 | 1.34 | il clamp **non morde mai** |

**Nessuna dinamica patologica**: il peggiore chiede **10 bit interi** (≈23 bit con 13 frazionari), mentre la SNN
usa già `accw` a 26 bit. I clamp **attivi** sono `z≤20`, `a_cah≥−9`, `accel∈[−9,a]` (toccano esattamente il
limite); `min(v/v0,10)` non morde ma **resta** (è protezione, non ottimizzazione).

## 4. Architettura — `acc_iidm_open` **type-parametrico** (il pattern di `snn_core`)
`snn_core.m` è già «core type-parametrizzato: double **e** fixed»: **una sola fonte**, i tipi decidono.
Si applica lo stesso schema:

```
acc_iidm_open(s, v, dv, v_l, p, rst, T)
    T = []        -> double  (riferimento algoritmico + plant cf_plant_lib/ACC_IIDM)
    T = <tipi>    -> fixed   (blocco Donatello_ACC_IIDM, HDL-ready)
```

**Alternativa scartata:** un `acc_iidm_fixed.m` separato ⇒ **due copie della stessa matematica**, cioè la deriva
che questa sessione ha eliminato e che `run_plant_parity` esiste per impedire.

**Conseguenza sui cancelli** (importante): oggi i test confrontano il blocco (IIDM double) col riferimento
double → `dmax = 0`. Col blocco in **fixed**, il riferimento di quei test diventa il **path fixed** (resta
`dmax = 0`), e la distanza fixed↔double diventa **un cancello nuovo e separato** — è lo studio di quantizzazione.

I tipi vivono in una funzione dedicata sul modello di `snn_types` (`acc_types(mode, fracBits)`), così sono
**una fonte sola** e sweepabili.

## 5. Budget di accuratezza — **derivato**, non scelto
L'utente ha indicato «sotto la quantizzazione SNN (0.028)». Applicato alla lettera sarebbe **sbagliato**: 0.028
è un budget su **`v0` [m/s]**, non su **`accel` [m/s²]**. Traduzione fedele allo spirito (è il criterio di
`DECODE_LUT_SWEEP.md` §5bis: *l'approssimazione non deve diventare la fonte d'errore dominante*):

1. **Misurare** `E_snn` = |accel(IIDM double, params dalla SNN **fixed**) − accel(IIDM double, params dalla SNN
   **double**)| sul dataset. È l'errore in accel che il progetto **ha già accettato** a monte.
2. **Pretendere** `E_iidm` = |accel(IIDM **fixed**) − accel(IIDM double)|, **a parità di parametri**, con
   `E_iidm < E_snn` (percentile p99 e max, riportati entrambi).

Criterio: l'IIDM in fixed **non deve diventare la fonte d'errore dominante**. I bit frazionari si scelgono col
**minimo che rispetta il budget**, via sweep — esattamente come `run_fixed_sweep.m` fa già per la SNN e come
`DECODE_LUT_SWEEP` ha fatto per la LUT.

## 6. Verifiche (sul DATASET, mai su un caso singolo)
| cancello | criterio |
|---|---|
| **`run_plant_parity`** (esistente) | **invariato**: il path double non si muove di un bit. È la prova che il type-parametrico non ha toccato il riferimento |
| **sweep frazionari** (nuovo) | `E_iidm < E_snn` su tutto il dataset; si sceglie il **minimo** numero di bit che passa |
| **`run_block_acciidm_test`** (adattato) | riferimento = path **fixed** → resta **`dmax = 0`** |
| **`run_block_closed_loop_test`** (adattato) | idem, **`dmax = 0`**, e l'anello resta stabile/segue il leader |
| **`run_block_hdl_gate`** (esteso) | ⚠️ oggi **rifiuta** `Donatello_ACC_IIDM` (cabla 5 uscite, il blocco ne ha 1). Va generalizzato per accettare blocchi a 1 uscita → **makehdl genera VHDL col solo `.slx`** |
| **OOC su `xc7z020`** (nuovo) | LUT/DSP/Fmax dell'IIDM e della catena completa. Alimenta il **Piano 2** del confronto MPC |
| **`run_block_sync_check`** | il blocco inlina i sorgenti attuali |

## 7. Fuori scope (esplicito)
- **Bitstream / deploy** su PYNQ-Z1 (decisione dell'utente).
- Rigenerare il bitstream della SNN (resta il debito noto: forward §2.1 + decode-256).
- L'MPC stesso e l'esecuzione del confronto: sono la loro spec/branch.
- **Ottimizzare** area o Fmax. L'area è al 7,94% e un control-step dura ~800.000 clock contro i 341 usati ⇒ **né
  area né latenza sono vincoli**. L'unico numero da sorvegliare è l'**Fmax (8,5 MHz)**.

  **Regola per questo SP (decisa dall'utente): un calo di Fmax non è un problema, ma non è licenza di andarci
  leggeri.** Cioè: non si ottimizza, non si peggiora **gratuitamente**, e **si registra il numero** (Fmax +
  slack + path critico) perché lo sweep futuro abbia una baseline. Lo sweep del punto a slack minima (Timing
  Analysis) è previsto ma **non è questo il momento**.

  **Rischio noto, da misurare non da assumere.** `fpga-expert` ch02: *«Division is the slowest arithmetic —
  always multi-cycle on FPGA»*; le digit-recurrence (restoring/non-restoring/SRT) producono **1 bit di
  quoziente per ciclo**. Da un `/` dentro una chart — che non ha stato né handshake — HDL Coder plausibilmente
  **srotola l'array in combinatorio** (~32 livelli per divisione): con 4 divisioni in cascata l'Fmax può
  scendere parecchio. **È un'ipotesi, non un fatto**: la sintesi OOC (§6) la conferma o la smentisce, e il path
  critico va guardato, non dedotto.

  **Se l'Fmax collassa → è un risultato da riportare, non un problema da inseguire in questo SP.** La via
  d'uscita è già identificata e fondata: *tutti* i divisori (`v0`, `b`, `sqrt(a·b)`, `s_safe`) sono **costanti
  entro il control-step**, quindi si possono calcolare i 4 **reciproci una volta** e ridurre l'IIDM a sole
  moltiplicazioni — è la tecnica di folding di `fpga-expert` ch09 (*«replace divisions with reciprocal
  multiplications»*) con Newton-Raphson (ch02: *«compute 1/y then multiply»*). **SP a sé**, insieme al
  pipelining.

## 8. File
- `matlab/acc_iidm_open.m` → **type-parametrico** (double + fixed), unica fonte
- `matlab/acc_types.m` (nuovo) → tipi `fi` dell'IIDM, sul modello di `snn_types.m`
- `matlab/build_hdl_variants.m` → `Donatello_ACC_IIDM` diventa **fixed/HDL-ready**; Description da riscrivere
- `matlab/run_block_hdl_gate.m` → generalizzato ai blocchi a 1 uscita
- `matlab/run_acc_fixed_sweep.m` (nuovo) → sweep dei bit frazionari vs budget derivato
- `document/SP2_ACC_IIDM.md` · `document/SESSION_RESUME.md` · `matlab/README.md` → **correggere la claim
  smentita** (§2) e il verdetto «sola simulazione / non sintetizzabile»
- `document/SP3_ACC_IIDM_HDL.md` (nuovo) → doc di processo, coi numeri OOC
