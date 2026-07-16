# SP3 — ACC-IIDM HDL-Ready

> Doc di processo. Spec: `docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md`.
> Stato: **completo e verificato** (2026-07-16).

## Cos'è
`Donatello_ACC_IIDM` (catena `s,v,dv,v_l → accel`) è **HDL-Ready** dal 2026-07-16: l'IIDM gira in
fixed-point e HDL Coder ne genera il VHDL dal solo `.slx`, con `DualPortRAM` (l'architettura time-mux del
deployato). Prima l'IIDM era in double e HDL Coder rifiutava il blocco con 14 errori.

> ⚠️ **HDL-ready ≠ deployato.** Il bitstream PYNQ-Z1 resta la sola SNN. Questo blocco serve a dare il **costo
> in silicio del controllore completo** (rete + legge di controllo), non a essere flashato.

## Perché: il buco di equità del confronto MPC
La spec del confronto MPC (`docs/superpowers/specs/2026-07-13-mpc-vs-snn-comparison-design.md`) dice due cose
che con l'IIDM in double erano in contraddizione: (§5) «la legge ACC-IIDM appartiene al **nostro** controllore»
e (§3, Piano 2) «FPGA synthesis (**both realized**) — what does each cost in silicon?». Con l'IIDM non
sintetizzabile, il Piano 2 avrebbe contato **solo la rete** e omesso in silenzio la legge che produce `a_cmd`,
mentre per l'MPC avrebbe contato tutto il QP: headline viziata a nostro favore. Questo SP chiude quel buco.

## La premessa era falsa (e per questo l'SP è stato piccolo)
La spec SP2 §7 dichiarava: *«ACC-IIDM su FPGA è un SP a sé — `sqrt(a·b)` e le divisioni sono lo stesso genere di
problema che per la sigmoide ha richiesto una LUT»*. Era una **claim mai verificata**. Misurata il 2026-07-15
dando a HDL Coder una operazione per volta, in fixed, isolata:

| operazione | HDL Coder | conseguenza |
|---|---|---|
| `sqrt(x)`, `tanh(x)`, `x^4` | ✅ VHDL generato | **nessuna LUT** |
| `a / b`, `1 / b` | ✅ **ma solo con `RoundingMethod='Zero'`** | `'Nearest'` (default) viene rifiutata; `'Floor'` vale solo per unsigned |
| `exp(x)` | ❌ rifiutata | irrilevante: `ALPHA = exp(−0.1)` è **costante** → si ripiega a build-time |

Il precedente della sigmoide era reale ma **non trasferibile**: σ(x) = 1/(1+**exp**(−x)), e `exp` è davvero
l'unica non generabile. `tanh` no. ⇒ niente LUT, niente Newton-Raphson: è stata una **tipizzazione
fixed-point**.

## Tipi e budget — derivato, non scelto
`acc_iidm_open` è **type-parametrico** come `snn_core` (una fonte: `acc_types('double')` → riferimento + plant,
`acc_types('fixed')` → blocco). I bit interi vengono dai range misurati su 60 traiettorie × 1000 step; i
frazionari da uno sweep contro un budget derivato.

**`nfrac = 8`** — il minimo che rispetta il budget. Il budget NON è 0.028 (quello è un errore su `v0 [m/s]`, non
su `accel [m/s²]`): è `E_snn`, quanto la quantizzazione **della rete** — già accettata a monte — sposta l'accel.

| | v0..b interi | E (p99) | E (max) | esito |
|---|---|---|---|---|
| **budget** `E_snn` (footprint della quantizzazione SNN) | — | **0.272** | **1.484** | — |
| IIDM fixed, `nfrac=6` | Q10.6 | 0.325 | 1.785 | **non passa** (scavalca la rete) |
| **IIDM fixed, `nfrac=8`** | Q10.8 | **0.156** | **0.834** | **passa, margine 1.75×** |

Il cancello **discrimina** (a 6 bit fallisce): non è un timbro che approva tutto. ⚠️ Passa **stretto**: un
dry-run su 2 traiettorie dava ~6× di margine, il dataset intero dice 1.75× — le code stanno solo nel campione
completo.

## Numeri OOC — il costo in silicio (xc7z020, @8 MHz, out-of-context)
Stesso flusso per entrambi (`scripts/synth_acc_iidm.tcl`), stesso clock del bitstream Fase B, così sono
confrontabili. La differenza catena − rete = **il costo dell'IIDM**.

| DUT | LUT | (%) | FF | DSP | (%) | BRAM | WNS @8 MHz | Fmax | liv. logici |
|---|---|---|---|---|---|---|---|---|---|
| **SNN sola** (`Donatello_Champion`) | 3 872 | 7,3 | 1 713 | 52 | 23,6 | 1 | **+30,5 ns** ✓ | **10,6 MHz** | 172 |
| **catena** (`Donatello_ACC_IIDM`) | 10 846 | 20,4 | 1 653 | 69 | 31,4 | 1 | **−373,1 ns** ✗ | **2,0 MHz** | **1 077** |
| **costo IIDM** | **+6 974** | +180% | −60 | +17 | | 0 | | **÷5,3** | **6,3×** |

**Verdetto onesto: l'IIDM in fixed è caro.** Risorse ×2,8 (l'IIDM da solo costa 1,8× l'intera rete) e Fmax
÷5,3. E a 8 MHz **il timing NON chiude** (WNS = −373 ns): non è «più lento», è fuori specifica a quel clock.

**Causa misurata, non ipotizzata: 1 077 livelli logici** (contro 172), 498 ns su un solo percorso combinatorio,
path critico dentro l'IIDM (`u_SNN_ACC/acc_3_reg`). HDL Coder ha srotolato le **4 divisioni** in un array
digit-recurrence combinatorio — esattamente ciò che `fpga-expert` ch02 prediceva (*«Division is the slowest
arithmetic — always multi-cycle on FPGA»*) e che la spec §7 aveva messo come rischio **da misurare**.

**Funzionalmente regge lo stesso**: a 2 MHz un control-step (0,1 s) dura 200 000 clock e l'inferenza ne usa 341
(lo 0,17%). Il blocco *funziona* — costringerebbe però l'intero FPGA a 2 MHz invece di 8.

## Fmax: la via d'uscita (SP a sé, non ora)
Decisa con l'utente: un calo di Fmax **non è un problema, ma non è licenza di andarci leggeri** — qui si misura e
si **registra** (baseline per lo sweep a slack minima, previsto ma non ora). Se/quando servirà recuperare Fmax:
**tutti** i divisori (`v0`, `b`, `sqrt(a·b)`, `s_safe`) sono **costanti entro il control-step** → si calcolano 4
**reciproci una volta** e l'IIDM diventa sole moltiplicazioni. È il folding di `fpga-expert` ch09 (*«replace
divisions with reciprocal multiplications»*) con Newton-Raphson (ch02). Con ~800 000 clock liberi, un divisore
iterativo è gratis. **SP a sé**, insieme al pipelining.

## Le tre insidie superate (per non ripagarle)
1. **La fimath è parte del TIPO, non una decorazione locale.** `setfimath` sparse nel codice → il codegen
   rifiuta il cambio di fimath come quello di tipo (*«RoundMode is nearest on the left but fix on the right»*),
   e ogni `cast(x,'like',T.acc)` riportava la fimath di default, ri-innescando lo scontro a valle: si
   rincorrevano i sintomi. Messa **nei prototipi di `acc_types`**, l'intera classe sparisce.
2. **Riassegnazione di tipo** (`v0 = cast(v0,'like',T.par)` cambia il tipo di `v0`): risolta con nomi nuovi
   (`v0f`, `Tf_`, …), non `x(:)=` — qui il tipo di destinazione è diverso per progetto. Gotcha HDL_PHASE §9.
3. **Sovra-escape degli apici** nel generatore della chart (`''''fixed''''` → `acc_types(''fixed'')` = stringa
   vuota + `fixed`): errore di sintassi banale, trovato dando lo script a `codegen`.

Diagnosi: Simulink mostra solo «Errors occurred during parsing of …» o l'errore di *propagazione*; il messaggio
vero (riga + colonna) si ottiene estraendo lo script della chart e dandolo a
`codegen('-config:lib', 'SNN_ACC', '-args', {a,a,a,a})` con `a = fi(0,1,32,20)`.

## Verifiche (tutte verdi, 2026-07-16)
| cancello | criterio | esito |
|---|---|---|
| `run_block_hdl_gate('Donatello_ACC_IIDM')` | VHDL dal solo `.slx` + `DualPortRAM` | **passato**, 0 err / 0 warn |
| `run_block_hdl_gate('Donatello_Champion')` | i blocchi HDL-ready non regrediscono | **passato** |
| `run_block_acciidm_test` | catena vs riferimento **fixed**, `dmax = 0` | **0 su 5/5 traiettorie** |
| `run_block_closed_loop_test` | anello chiuso, `dmax = 0` | **0 su 6/6** (3 traj × 2 conv. dv) |
| `run_plant_parity` | il double non si muove di un bit | **`0.00e+00` su 3/3** |
| `run_block_sync_check` | il blocco inlina i sorgenti attuali | **8 blocchi, 0 stale** |
| `run_acc_fixed_sweep` | `E_iidm < E_snn` sul dataset | **passa a `nfrac=8`** (fallisce a 6) |

> I test SP2 (`run_block_acciidm_test`, `run_block_closed_loop_test`) hanno cambiato **riferimento**: col blocco
> in fixed, confrontarlo col double renderebbe `dmax = 0` irraggiungibile, quindi il riferimento è ora il path
> fixed. La distanza fixed↔double è un cancello a sé: `run_acc_fixed_sweep`.

## File
- `matlab/acc_types.m` · `matlab/acc_iidm_open.m` (type-parametrico) · `matlab/run_acc_fixed_sweep.m`
- `matlab/build_hdl_variants.m` (blocco fixed) · `matlab/run_block_hdl_gate.m` (N uscite)
- `matlab/run_block_acciidm_test.m` · `matlab/run_block_closed_loop_test.m` · `matlab/snn_cl_step.m` (riferimento fixed)
- `scripts/synth_acc_iidm.tcl` (sintesi OOC)
