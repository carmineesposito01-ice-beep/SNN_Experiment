# SP4 — ACC-IIDM fast: recuperare l'Fmax (studio A/B su dati) — Design

**Data:** 2026-07-16 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Recuperare l'Fmax dell'ACC-IIDM in fixed. Oggi (SP3) `Donatello_ACC_IIDM` è HDL-ready ma sintetizza a **2,0 MHz**
(WNS −373 ns @8 MHz, **timing non chiude**): la catena completa sarebbe rallentata dall'IIDM rispetto alla rete.

**Bersaglio: ≥ 11,65 MHz** — l'Fmax della sola SNN dopo la correzione Fase B (`FPGA_PHASE_B_REPORT`), così l'IIDM
non è il collo di bottiglia della catena. **Non** è lo sweep del punto a slack minima (max Fmax assoluto), che
resta uno studio separato (vincolo utente: «un calo di Fmax non è un problema, ma non licenza di andarci
leggeri»).

## 2. Il problema, misurato (SP3, non ipotizzato)
Path critico della catena: `u_SNN_ACC/pR_idx_reg → u_SNN_ACC/acc_3_reg`, **1077 livelli logici**. Breakdown:

```
CARRY4 = 820 (76%)   DSP48E1 = 10   LUT1..6 = 247
segnali sul path: p1542reci_mul_temp...   <- il reciproco-per-moltiplica di divide()
```

**Il 76% della profondità sono catene di carry, dai divisori.** Il `divide(numerictype,…)` di SP3 genera già un
reciproco-per-moltiplica, ma il calcolo del reciproco è una catena digit-recurrence lunghissima, **tutta in un
clock**. E le divisioni sono **incatenate** (`s_star` usa una divisione → `z = s_star/s_safe` un'altra → `a_iidm`
usa `z` → `dd` un'altra…), quindi la profondità si somma. Non è «una volta per control-step»: è il divisore
combinatorio che va **spezzato**.

## 3. Le 5 divisioni e i range dei divisori (misurati SP3)
| divisione | divisore | range misurato | note |
|---|---|---|---|
| `v/v0` | `v0` | [8, 45] | parametro |
| `s_star/s_safe` | `s_safe = max(s,2)` | [2, 150] | |
| `dv²/(2·s_safe)` | `2·s_safe` | [4, 300] | riusa `s_safe` |
| `(a_iidm−a_cah)/b` | `b` | [0.5, 3] | parametro |
| `v·dv/(2·sab)` | `sab = sqrt(a·b)` | [0.87, 1.32] | `sab` calcolato |

**Tutti i divisori sono limitati lontano da zero** → i reciproci sono limitati (niente esplosione di dinamica).

## 4. Due varianti (studio A/B — si decide sui DATI)
L'utente vuole entrambe avanti, preferisce **M**, ma valuta sui numeri. Ordine: **L prima, poi M**.

### Variante L — reciproci a LUT
Ogni `1/x` → reciproco tabellato (lookup shallow, ~1–2 livelli) + moltiplica. L'IIDM resta **combinatorio in un
clock**. Riusa la metodologia provata del decode (`DECODE_LUT_SWEEP`): sweep dimensione LUT vs budget, si sceglie
la più piccola sotto il budget.

> ⚠️ **Applicabilità con `sqrt(a·b)` — verificata.** La LUT **non** tabella `1/sqrt(a·b)` sui due ingressi `a,b`.
> Si calcola prima `sab = sqrt(a·b)` con la `sqrt` **nativa** di HDL Coder (uno scalare), poi `1/sab` è una LUT a
> **un solo ingresso** sul range misurato [0.87, 1.32]. Tutti i 4 reciproci distinti (`1/v0`, `1/s_safe`, `1/b`,
> `1/sab`) sono quindi **1-D**.
> ⚠️ **Rischio residuo, da misurare:** resta la `sqrt` combinatoria. Se è profonda, L sposta il collo di
> bottiglia sulla radice invece di toglierlo. È il motivo per cui L si costruisce **per prima**: la sintesi OOC
> dirà subito se basta o se serve M.

### Variante M — time-mux dell'IIDM
L'IIDM diventa **multi-ciclo** (FSM, come la SNN): un'unità aritmetica sequenziale riusata, valutata su più clock
(ne abbiamo ~341 per control-step). Spezza qualunque catena combinatoria → massimo Fmax, e **taglia le risorse**
(una unità riusata invece di 5 divisori). **La preferita dell'utente.**

> **v1 = solo spezzare la catena (Fmax).** L'overlap SNN(k+1)‖IIDM(k) — mentre l'IIDM elabora lo step k, la SNN
> macina k+1, throughput dettato dallo stadio più lento — è un **secondo giro** (fuori scope v1): prima si misura
> il guadagno del solo sequenziamento.

## 5. Verifica (condivisa, sul DATASET)
Riferimento comune: l'IIDM fixed attuale di SP3 (`acc_iidm_open` con `acc_types('fixed')`, `nfrac=8`).

| variante | criterio | perché |
|---|---|---|
| **M** (time-mux) | **`dmax = 0`** vs riferimento SP3 | fa la **stessa** matematica fixed, solo sequenziale → bit-identica |
| **L** (LUT reciproci) | **sweep**: errore in `accel` < budget `E_snn` (p99 0.272 / max 1.484 [m/s²]) | il reciproco-LUT **approssima** `1/x` → come il decode, si sceglie la LUT più piccola sotto il budget già accettato |
| entrambe | anello chiuso `run_block_closed_loop_test` resta verde | l'ottimizzazione non cambia il comportamento |
| entrambe | `run_block_hdl_gate` passa (VHDL + `DualPortRAM`) | restano HDL-ready |

Poi **sintesi OOC di entrambe** (`scripts/synth_acc_iidm.tcl`, già esistente) → tabella **Fmax · LUT · DSP · WNS
· livelli logici**, e **si decide sui dati** quale diventa il campione. Target di accettazione: **≥ 11,65 MHz**.

## 6. Fuori scope (esplicito)
- **Overlap SNN(k+1)‖IIDM(k)** (throughput): secondo giro del time-mux, dopo aver misurato la v1.
- **Sweep a slack minima** (max Fmax assoluto): studio separato, come da vincolo utente.
- **Bitstream / deploy**: HDL-ready + OOC, niente `.bit` (coerente con SP3).
- Chiudere il loop dentro il blocco; altri champion; altri plant.

## 7. File (previsti)
- `matlab/acc_recip_lut.m` (nuovo, variante L) → reciproco tabellato 1-D, parametrico in dimensione
- `matlab/acc_iidm_open.m` (modifica) → le divisioni via reciproco (LUT per L / sequenziale per M), dietro i tipi
- `matlab/acc_types.m` (modifica se serve) → tipi dei reciproci
- `matlab/run_acc_recip_sweep.m` (nuovo, variante L) → sweep dimensione LUT reciproco vs budget
- `matlab/build_hdl_variants.m` (modifica) → blocco/i con l'IIDM veloce
- `matlab/run_block_acciidm_test.m`, `run_block_closed_loop_test.m` (verifica, riferimento SP3)
- `scripts/synth_acc_iidm.tcl` (riuso) → OOC delle due varianti
- `document/SP4_ACC_IIDM_FAST.md` (nuovo) → doc di processo, tabella A/B coi numeri OOC, decisione
