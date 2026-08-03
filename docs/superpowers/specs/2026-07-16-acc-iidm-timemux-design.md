# SP4-M — ACC-IIDM time-mux (divisore condiviso): recuperare l'Fmax — Design

**Data:** 2026-07-16 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Recuperare l'Fmax dell'ACC-IIDM in fixed **sequenziando le divisioni** e **condividendo un solo divisore**
(time-mux), riusandolo per le 5 divisioni invece di 5 divisori combinatori incatenati. Recupera l'Fmax **e**
taglia le risorse (la visione dell'utente).

**Bersaglio: Fmax ≥ 11,65 MHz** (pari alla SNN dopo la correzione Fase B). **Bit-identico a SP3: `dmax = 0`**
(nessuna approssimazione — è la differenza chiave rispetto a L, che è stata scartata proprio perché approssimava).

## 2. Contesto — perché M (e non L)
`document/SP4_ACC_IIDM_FAST.md`: la variante **L (reciproci a LUT) è stata scartata sui dati** (nessuna N sotto il
budget, errore non convergente ~4 m/s²). Insegnamento: **le divisioni vanno sequenziate, non approssimate.** M usa
la divisione **esatta** (la stessa `divide()` di SP3), solo distribuita nel tempo → zero errore d'approssimazione.

## 3. Il problema, misurato (SP3)
IIDM fixed a **2,0 MHz** (WNS −373 ns @8 MHz, timing non chiude). Path `pR_idx_reg → acc_3_reg`, **1077 livelli**,
**CARRY4 = 820 (76%)** dai 5 divisori digit-recurrence combinatori **incatenati**. Le 5 divisioni (nel path
`recipN=0` = `divide()` di `acc_iidm_open`):

| # | divisione | divisore |
|---|---|---|
| 1 | `v/v0` | `v0` |
| 2 | `s_star/s_safe` | `s_safe` |
| 3 | `dv²/(2·s_safe)` | `2·s_safe` |
| 4 | `(a_iidm−a_cah)/b` | `b` |
| 5 | `v·dv/(2·sab)` | `2·sab` |

## 4. Approccio — meccanismo deciso da una VERIFICA (non assunto)
Vincolo che rende il time-mux quasi gratis in latenza: l'IIDM gira **una volta per control-step** (sul `valid`
della SNN), con **~341 clock** prima del prossimo. Un divisore riusato su 5..N cicli entra larghissimo nel budget.

### 4.1 Meccanismo: resource sharing di HDL Coder PRIMA, FSM esplicita in fallback
**Primo passo del piano = VERIFICA empirica** (la lezione del progetto: misurare, non assumere). HDL Coder ha il
**resource sharing**: date più `divide()` uguali, con un `SharingFactor` le condivide in **una** unità, inserendo
il controller/MUX + i registri che le sequenziano su clock diversi. Con l'enorme oversampling (1 inferenza / ~341
clock) il tool ha spazio per schedularle.

- **Se il resource sharing condivide *e* sequenzia i 5 `divide()`** (Fmax ≥ 11,65 · 1 solo divisore · **`dmax=0`
  dalla sorgente unica `acc_iidm_open`, bit-identico per costruzione**) → **M è config-based**, cambiamento minimo
  sul blocco esistente, niente FSM a mano.
- **Se non basta** (non condivide i divisori, o non sequenzia, o non centra l'Fmax) → **FSM esplicita**: divisore
  sequenziale costruito a mano + macchina a stati che lo riusa per le 5 divisioni, con la bit-identità **da
  garantire e verificare** (il divisore sequenziale deve dare gli stessi bit di `divide()`).

> Non si costruisce la FSM finché la verifica non dice che serve. È il modo per non rifare a mano ciò che il tool
> potrebbe fare da solo — e per non *assumere* che il tool lo faccia.

### 4.2 Granularità v1: solo le 5 divisioni
Si condividono/sequenziano **solo le 5 divisioni** (il 76% del problema, la catena di carry). Il resto (mul/add
via DSP, `sqrt`, `tanh`, confronti) resta **combinatorio fra gli stadi**: registrando l'uscita del divisore
condiviso, la catena si spezza in segmenti shallow. Mirato alla causa misurata, minimo indispensabile per l'Fmax.

### 4.3 v2 (dopo v1): sequenziare TUTTO — solo se migliora
Una **seconda prova**, dopo aver misurato v1: sequenziare l'intero datapath (1-op/clock come la SNN, ALU
condivisa) e misurare se Fmax/area migliorano rispetto a v1. È un confronto, non un obbligo: se v1 già centra il
bersaglio con buon margine, v2 è opzionale. Deciso sui numeri.

## 5. Verifica (sul DATASET)
Riferimento: l'IIDM fixed di SP3 (`acc_iidm_open` con `acc_types('fixed')`, `recipN=0` = `divide()`), interpretato.

| cancello | criterio |
|---|---|
| **`dmax = 0`** vs SP3 su N traiettorie (`run_block_acciidm_test` sul blocco M) | M fa la **stessa** matematica, solo sequenziata → bit-identica. Un `dmax > 0` = il sequenziamento ha cambiato l'aritmetica → **fermarsi** |
| **`run_block_closed_loop_test`** verde | l'ottimizzazione non cambia il comportamento |
| **`run_block_hdl_gate`** passa (VHDL + `DualPortRAM`) | resta HDL-ready |
| **OOC** (`scripts/synth_acc_iidm.tcl`) | **Fmax ≥ 11,65 MHz** · conteggio divisori **ridotto** (idealmente 1) · path critico non più nelle divisioni incatenate |

## 6. Fuori scope (esplicito)
- **Overlap SNN(k+1)‖IIDM(k)** (throughput): secondo giro, dopo la v1.
- **Sweep a slack minima** (max Fmax assoluto): studio separato.
- **Bitstream / deploy**: HDL-ready + OOC, niente `.bit`.
- Chiudere il loop nel blocco; altri champion/plant.

## 7. File (previsti)
- `matlab/build_hdl_variants.m` (modifica) → blocco `Donatello_ACC_IIDM_M`: config di resource sharing sul blocco
  (via `hdlset_param`/coder settings) e/o, in fallback, l'IIDM sequenziato via FSM.
- `matlab/acc_iidm_open.m` — **la sorgente NON cambia** nel path resource-sharing (M è config sul blocco);
  cambia solo in fallback FSM (e comunque `run_plant_parity` deve restare **invariato**, il double non si muove).
- `matlab/run_block_acciidm_test.m` (riuso, riferimento SP3) · `scripts/synth_acc_iidm.tcl` (riuso, OOC).
- `document/SP4_ACC_IIDM_FAST.md` (aggiornare con l'esito M) o `document/SP4M_ACC_IIDM_TIMEMUX.md` (nuovo).
