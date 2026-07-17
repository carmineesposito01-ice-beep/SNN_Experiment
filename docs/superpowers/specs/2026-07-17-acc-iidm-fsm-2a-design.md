# SP4-M-FSM #2a — ACC-IIDM: la FSM riusa UNA `divide()` (1 divisore condiviso) — Design

**Data:** 2026-07-17 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Ridurre l'area dell'ACC-IIDM fixed **sequenziando le 5 divisioni su UN solo divisore**, con una FSM interna alla
chart, e **MISURARE in OOC che Fmax e area ne escono** — il numero che non è mai stato ottenuto.
Vincolo invalicabile invariato: **bit-identico a SP3, `dmax = 0`** (mai approssimare).

**Non è un tentativo di centrare gli 11,65 MHz.** Il path critico resterà **una divisione combinatoria**
(~172 livelli in SP3 → stima ~9,5 MHz, mai misurata su questa architettura). #2a serve a portare a casa
**area ridotta + `dmax=0` a rischio zero** e soprattutto a **produrre il dato** che dirà se serve #2b
(divisore sequenziale a mano) e quanto margine deve recuperare.

## 2. Contesto — perché #2a, e perché adesso
`document/SP4_ACC_IIDM_FAST.md`: tre strade chiuse.
- **L** (reciproci a LUT): **approssima** → scartata sui dati (errore non convergente ~4 m/s²).
- **M-v1** (resource sharing config): 9,5 MHz **e area esplosa** (LUT ×2,36, FF ×13,9) → il config non taglia
  le risorse, le gonfia.
- **M-FSM #1** (FSM + blocco `HDLMathLib/Divide` pipelinato): **bit-identità PROVATA** (G1 `dmax=0` su 300k
  coppie · G2 `0/60000` · G3/G4 5/5 traj, latenza 509 clk) **ma non genera VHDL**: il blocco accanto alla chart
  impone la conversione MATLAB-to-dataflow, che **vieta `tanh` in fixed-point** — e `tanh` è nel cuore
  dell'IIDM. Aggirarla = LUT/float = approssimare = `dmax≠0`. Dettaglio: `document/HDL_PHASE.md` §9.

**Cosa insegna #1 a #2a:** un blocco Simulink accanto alla chart è **vietato** se la chart deve restare
bit-exact. Quindi il divisore condiviso deve stare **dentro** la chart. E se dentro la chart c'è **una sola
chiamata** a `divide()`, HDL Coder genera **un solo divisore** — che la FSM riusa nei cicli. È il time-mux
fatto dalla FSM, lo stesso principio con cui `snn_b2_fsm` riusa un datapath per 32 neuroni.

## 3. Architettura
Il blocco `Donatello_ACC_IIDM_M` viene **semplificato**: torna a essere **la sola chart** nel subsystem, come
SP3 (l'attuale versione con blocco `Divide` + Unit Delay + feedback è superata da #1).

```
 s,v,dv,v_l ──►┌───────────────────────────────────┐──► accel
               │  MATLAB Function  IIDM_CTRL       │
               │   • SNN time-mux (snn_b2_fsm)     │   4 ingressi, 1 uscita: identico a SP3
               │   • decode LUT-64                 │   NESSUN blocco accanto alla chart
               │   • FSM: 5 divisioni su 1 divide()│   -> niente conversione dataflow
               │   • funzioni-fase (iidm_*)        │   -> tanh fixed nativa (come SP3)
               └───────────────────────────────────┘
```

Spariscono rispetto a #1: blocco `Divide`, Unit Delay, handshake `num/den/vin`→`quot/vout`, feedback, loop
algebrico. **La chart ha di nuovo 4 ingressi e 1 uscita**, e l'interfaccia esterna del blocco è identica a SP3
(fisica `s,v,dv,v_l → accel`, edge-triggered, niente `start`/`done` esposti — §3.1.2/§3.1.4).

**Il meccanismo che fa il lavoro:** nel codice della chart c'è **UNA SOLA** chiamata a `fsm_div` (dentro lo
stato della FSM). Una chiamata nel sorgente = **una unità hardware**; le 5 divisioni la riusano in 5 cicli
diversi. Nessuna direttiva al tool, nessuna ottimizzazione da negoziare: è la struttura del codice a imporlo.

> ⚠️ **"1 chiamata = 1 divisore" è l'ASSUNTO su cui poggia tutto #2a — ed è un'assunzione su HDL Coder, non un
> fatto.** Va **misurata**, non creduta: **G6 conta i divisori nel VHDL generato**. Se ne uscissero 5, #2a
> sarebbe inutile (nessun taglio d'area) e lo si saprebbe lì.
> Il punto delicato è **come si scrive la FSM**: `kdiv` deve essere una **variabile di stato** (`persistent`),
> non l'indice di un loop. Il *model* `acc_iidm_fsm` usa `for k = 1:5`, che il codegen **srotola** (trip-count
> costante) → in HDL darebbe **5** divisori: è corretto per il model (che deve solo calcolare il risultato e
> gira MEXato), **sbagliato** per la chart. La chart NON deve contenere quel loop.

## 4. Data flow e FSM
```
IDLE ─(edge-trigger sul cambio di xn)─► SNN: snn_b2_fsm(xn, go)   (~341 clk, time-mux 1 neurone/clk)
  ─(valid)─► pv = snn_decode_lut(raw, 64)
             [st, alf, vlp] = iidm_prep(s,v,dv,v_l, pv(:), false, alf, vlp)     % 1 volta per control-step (§5)
             kdiv = 1 ; phase = RUN
  RUN, un ciclo per divisione (k = 1..5, ordine = dipendenze: q3 dopo q1; q5 dopo q3/q4):
             [num, den] = iidm_nd(kdiv, st)          % operandi dallo stato
             q          = fsm_div(num, den)          % UNICA chiamata nel codice -> UN divisore in HDL
             st         = iidm_use(kdiv, q, st)      % consuma il quoziente
             kdiv >= 5 ?  accel = iidm_final(st) ; phase = IDLE   :   kdiv = kdiv + 1
```
- **Le funzioni-fase non si toccano**: `iidm_prep`/`iidm_nd`/`iidm_use`/`iidm_final`/`fsm_div` sono le stesse
  già validate da **G2 su 60.000/60.000 control-step** (single-source col model `acc_iidm_fsm`).
- **Latenza attesa ~346 clk** (341 SNN + 5 divisioni), **meglio dei 509 di #1** perché sparisce l'attesa
  dell'handshake. **Da MISURARE** (G4), non da assumere: il vincolo di rate del blocco va dal contratto.
- **Divisione per `DT`** (costante, filtro OU): resta come oggi in `iidm_prep` (`x*(1/DT)`, **provato
  bit-identico da G2**), non è tra le 5 sequenziate.

## 5. Bit-identità — garantita per costruzione
`fsm_div` **è** `divide(numerictype(T.acc), num, den)`: la stessa identica funzione del path fixed di SP3
(`acc_div` con `recipN=0`). Non c'è nessuna aritmetica nuova da guadagnare, a differenza di #2b. La FSM cambia
**quando** le divisioni avvengono, non **cosa** calcolano.

Resta comunque tutto da verificare sul dataset (una garanzia "by construction" è una claim finché un cancello
non la prova — modo di lavoro del progetto):
- **G2** model == `acc_iidm_open` sul dataset intero (già verde, si ri-esegue);
- **G3** blocco reale == model **e** == SP3;
- il rischio §2.1 (due implementazioni della stessa matematica) resta chiuso: la chart **inlina** le funzioni-fase,
  non le riscrive.

## 6. Verifica — cancelli riusati, invariati
| # | cancello | criterio | stato |
|---|---|---|---|
| **G2** | `run_acciidm_m_dataset` | `dmax=0` su 60.000 control-step | esiste, verde, sensibile (q2↔q3 → 1990/2000) |
| **G3/G4** | `run_block_acciidm_m_test` | `dmax=0` vs model **e** vs SP3 su 5 traj; **latenza misurata**; edge-triggered (1 inferenza su ingresso costante) | esiste; la latenza attesa cambia (~346) |
| **G5** | `run_block_hdl_gate('Donatello_ACC_IIDM_M')` | VHDL dal solo `.slx` + `DualPortRAM` (time-mux SNN) | esiste; **è il cancello che #1 non superava** |
| **G6** | OOC (`scripts/synth_acc_iidm.tcl`) | **il punto di #2a**: Fmax e area **misurate**; **1 solo divisore** nel VHDL; path critico atteso = 1 divisione | mai eseguito su questa architettura |
| **G7** | `run_plant_parity` | double invariato | esiste, verde |

**Criterio di successo di #2a** (esplicito, per non spostare i pali a posteriori):
1. **`dmax = 0`** (G2/G3) — invalicabile;
2. **G5 passa** (genera VHDL) — è ciò che #1 non riusciva a fare;
3. **G6 dà i numeri**: area **sensibilmente < SP3** (10846 LUT, 5 divisori) e **≪ M-v1** (25557 LUT); Fmax
   **misurata**, attesa ~9,5 MHz.
   **Fmax < 11,65 NON è un fallimento di #2a**: è il dato che qualifica #2b.

## 7. File
| file | ruolo |
|---|---|
| `matlab/build_hdl_variants.m` | **MODIFICA**: `Donatello_ACC_IIDM_M` torna **sola chart** (via il blocco `Divide`, gli Unit Delay, il feedback, i tipi delle porte di ritorno); chart con la FSM che chiama `fsm_div` una volta per ciclo |
| `matlab/iidm_prep.m` · `iidm_nd.m` · `iidm_use.m` · `iidm_final.m` · `fsm_div.m` | **INVARIATI** (single-source, già validati da G2) |
| `matlab/acc_iidm_fsm.m` · `fsm_step.m` · `run_acciidm_m_dataset.m` | **INVARIATI** (il model non cambia) |
| `matlab/run_block_acciidm_m_test.m` | **MODIFICA minima**: `hold` di default coerente con la latenza ~346 (resta comunque **misurata**, non assunta) |
| `matlab/run_block_hdl_gate.m` · `scripts/synth_acc_iidm.tcl` | **RIUSO** (G5 · G6) |
| `document/SP4_ACC_IIDM_FAST.md` · `document/SESSION_RESUME.md` | **MODIFICA**: esito e stato |

## 8. Fuori scope (esplicito, YAGNI)
- **#2b — divisore sequenziale a mano**: si decide **dopo**, sui numeri di G6. È il solo modo di puntare a
  11,65, e ha il suo rischio (bit-identità da guadagnare) — non si mescola con #2a.
- **Overlap SNN(k+1)‖IIDM(k)**, **sweep a slack minima**, **bitstream/deploy**, **promozione di M a deploy o
  sostituzione di SP3**: tutti fuori, come in #1.
- **`acc_types`/`snn_types`**: non si toccano. `snn_types` è stato ripristinato; `acc_types` resta a `fi(0)`
  (provato neutro: plant parity, SP3 `dmax=0`, G5 su SP3 e Champion).
