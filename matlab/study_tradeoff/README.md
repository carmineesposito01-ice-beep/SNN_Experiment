# Studio di trade-off — Donatello e Donatello+IIDM

Scegliere la configurazione da deployare su PYNQ-Z1 per i **due blocchi HDL-ready**, con una catena di
ragionamento verificabile da terzi.

| blocco | cos'e' | asse di trade-off | ordine |
|---|---|---|---|
| **Donatello** | SNN + decode → i 5 parametri car-following | **accoppiamento SNN ↔ decode** (5 esperimenti) | **primo** |
| **Donatello + IIDM** | il precedente + la legge ACC-IIDM → accel | round di pipelining IIDM (17 punti) | dopo |

## Il principio del Blocco A

**Un blocco composto vale quanto il suo pezzo piu' lento.** SNN a 99 MHz + decode a 31 spreca ~1000 FF
di pipelining che il blocco non puo' usare; SNN a 30 + decode a 70 e' sbilanciato all'opposto. Gli
esperimenti sono quindi la **diagonale bilanciata** piu' due **controlli** che mostrano lo spreco nei
due versi.

| # | esperimento | decode | SNN | attesa | ruolo |
|---|---|---|---|---|---|
| 1 | **SLOW** | `fused` (31,3) | R2 (29,7) | ~30 | candidato area minima |
| 2 | **BALANCED** | `p3` (56,9) | R5 (62,2) | ~57 | candidato compromesso |
| 3 | **FAST** | `p5` (97,8) | R9 (99,2) | ~98 | candidato margine massimo |
| 4 | ctrl SNN sovradim. | `fused` | R9 | 31,3 | **misurato 30,367**: +1068 FF inutili |
| 5 | ctrl decode sovradim. | `p5` | R2 | ~30 | +496 FF inutili dall'altro lato |

⚠️ **Lo stato di partenza era la PEGGIORE combinazione**: decode fuso (31) + SNN R9 (99) → ~30 MHz
pagando i 2780 FF di R9. Sulla diagonale la stessa area rende **~3,2x**.

⚠️ **A prima di B**: i 17 punti IIDM incorporano la SNN a **R9** *e* il decode **FUSO**. Qualunque
scelta di A che tocchi il decode li invalida → vanno rigenerati.

I probe `snn_fwd_r*` su disco sono la SNN **senza decode**: erano lo *strumento di misura* dei round,
non configurazioni deployabili. Restano come riferimento diagnostico.

**Il decode e' fissato a LUT-64**: la scelta era gia' stata presa (errore di approssimazione sotto la
soglia di 0,028 — vedi `document/DECODE_LUT_SWEEP.md`). Non e' un asse di questo studio.

---

## Da dove vengono i punti

Le ottimizzazioni del progetto sono **cumulative e tutte gia' integrate**, non alternative:

```
2b  tanh          4 varianti -> vince A1 (LUT piena): bit-exact, 136 MHz, 545 LUT, 0 DSP
                  integrata -> controllore 9,30 -> 10,58 MHz
2d  SNN->decode   split readout/decode + albero reci -> 10,58 -> 15,84 MHz
SNN forward       pipeline dello stadio-C in 8 stadi -> 29,75 -> 99,16 MHz   <-- asse Donatello
IIDM              R1..R17, divisore e radice sequenziali + fasi -> 15,673 -> 77,936 MHz  <-- asse D+IIDM
```

Che i round SNN siano davvero integrati e' verificabile: nello spettro dei path di `iidm_r17` gli
endpoint del plateau sono `pCm_recip` / `pCm_Iip`, cioe' lo stadio MAC introdotto a SNN R6.

⚠️ **I sorgenti MATLAB per-round NON esistono** (le modifiche erano in place). Il VHDL generato e'
l'**unica copia** di ogni configurazione → archiviato e verificato con sha256 in questo albero:

- `donatello/vhdl_snn_points.tar.gz` (156 KB, 56 file)
- `donatello_iidm/vhdl_rounds.tar.gz` (1,9 MB, 119 file)

Per ripristinare: `tar -xzf <archivio>` poi `grep -v '^#' MANIFEST.txt | sha256sum -c`.

⚠️ **I punti di Donatello sono probe FORWARD-ONLY**: ingressi `x1..x4`, uscite `o1..o5` (i raw della
SNN), **senza decode**. Misurano il core SNN, che e' cio' che determina l'Fmax del blocco (il decode non
compare nei 40 path peggiori). Il blocco Donatello completo va **rigenerato** — il VHDL del Champion su
disco e' del 17/07 e precede il pipelining SNN del 18/07.

---

## Il protocollo di misura (e perche' non e' negoziabile)

Tutto misurato il 2026-07-20 sullo **stesso** netlist R17, cambiando solo il modo di misurare:

| flusso | vincolo impl | WNS | Fmax post-route | LUT |
|---|---|---|---|---|
| sintesi libera | 125 ns | +103,910 | 47,416 | — |
| sintesi libera | 14 ns | +0,269 | 72,828 | 7950 |
| sintesi libera | 12,831 ns | −0,055 | 77,604 | 7991 |
| sintesi libera | 11 ns | −2,346 | 74,929 | 8189 |
| **sintesi vincolata** | **12,831 ns** | +0,380 | **80,315** | **7902** |

Tre conseguenze, tutte contro-intuitive e tutte misurate:

1. **Un'Fmax post-route con vincolo lasco non e' una proprieta' del design.** Con 103 ns di slack
   placer e router non hanno pressione e si fermano: 47 MHz invece di 78.
2. **Sovra-vincolare PEGGIORA.** Chiedere 11 ns invece dei ~12,8 raggiungibili costa −3,6% di Fmax e
   +2,5% di LUT. L'euristica «stringi tanto e leggi periodo − WNS» e' una trappola.
3. **Vincolare la SINTESI conviene**: +3,5% di Fmax con meno area (7902 vs 7991 LUT, 3988 vs 4069 FF).
   Costa 312 s invece di 109 s.

**Regola di validita':** `ritardo = periodo − WNS` vale solo se **WNS ≤ 0** (il tool ha spinto al
massimo). Con WNS > 0 e' un **limite inferiore** e il driver rifa' la misura al ritardo raggiunto.

**Si riporta il MIGLIORE dei tentativi, non l'ultimo.** Ogni tentativo e' un'implementazione vera a un
vincolo dichiarato, e place&route non e' monotono: su R17 il raffinamento a 12,451 ns e' atterrato a
12,544, cioe' *peggio* del tentativo che l'aveva prodotto. Il CSV riporta `n_impl` cosi' il numero di
tentativi resta visibile.

**I tre verdetti** (campo `valid`):

| verdetto | significato |
|---|---|
| `VALIDA` | il migliore ha WNS ≤ 0: il tool ha spinto al massimo |
| `CONFERMATA` | il migliore ha WNS > 0, **ma** un tentativo piu' stretto e' stato fatto e non ha migliorato: sondata, non e' piu' un limite inferiore |
| `LIMITE-INFERIORE` | WNS > 0 e nulla di piu' stretto e' stato sondato — **da indagare a mano** |

⚠️ **Cosa misura**: implementazione OOC senza `HD.PARTPIN_LOCS` → Vivado avverte che il timing da/verso
le porte non e' accurato. Il numero e' il **tetto interno registro-registro** del blocco, buono per
confrontare configurazioni; il timing d'integrazione si misurera' col wrapper AXI.

⚠️ **`report_qor_assessment` non e' disponibile**: richiede licenza > BASIC (`ERROR Implflow 47-2944`).
Non serve: si implementa ogni punto davvero invece di stimarlo.

---

## Come si riesegue

```bash
S=matlab/study_tradeoff

# un blocco intero (ripartibile: un rilancio salta i punti gia' fatti)
bash $S/common/run_campaign.sh $S/donatello/points.tsv       /d/zbd_tradeoff/donatello
bash $S/common/run_campaign.sh $S/donatello_iidm/points.tsv  /d/zbd_tradeoff/donatello_iidm

# un singolo punto (per rifare o indagare)
bash $S/common/run_campaign.sh $S/donatello_iidm/points.tsv /d/zbd_tradeoff/donatello_iidm iidm_r17

# il Blocco A si ricostruisce dai commit dei round SNN (matrice di accoppiamento):
bash $S/common/run_block_a_matrix.sh              # architettura CHART (una MF, muro a 41 MHz)
bash $S/common/run_block_a_split.sh               # architettura SPLIT (due entita', FAST a 92,9 MHz)

# i due passi a mano, se serve entrare nel dettaglio
VIV=C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat
$VIV -mode batch -source $S/common/synth_point.tcl -tclargs <srcdir> <outdir> <label> [periodo] [top]
$VIV -mode batch -source $S/common/impl_point.tcl  -tclargs <dcp> <periodo> <outdir>
```

### Il Blocco A: accoppiamento SNN ↔ decode, e le due architetture

Un blocco composto vale quanto il pezzo piu' lento → si accoppiano pezzi con Fmax vicina (SLOW=fused+R2,
BALANCED=p3+R5, FAST=p5+R9). Ma il modo in cui SNN e decode sono **assemblati** conta quanto la scelta
dei pezzi:

- **chart** (`archStyle='chart'`): una MATLAB Function fa tutto. SNN e decode compilati insieme → costo
  d'INTEGRAZIONE (il controllo SNN entra nel datapath del decode) → muro a **41 MHz** per ogni tier.
- **split** (`archStyle='split'`): SNN e decode come DUE entita' di sintesi (`SNN.vhd` + `DEC.vhd`). Il
  muro cade: BALANCED 41→56,4, **FAST 41→92,9 MHz** (×3 sul punto di partenza).

Generazione di un singolo punto (usato dai driver):
```matlab
gen_donatello_point('D:\zbd_tradeoff\...\gen', 'p5', 'snn_variants/snn_b2_fsm_R9.m', 'split')
%                    outdir                     decode  snapshot SNN congelato        arch
```
⚠️ `gen_donatello_point` azzera la cache `slprj` a ogni chiamata: HDL Coder riusa la SNN gia' compilata
e IGNORA il sorgente inlinato cambiato (provato: con cache un p3+R5 usciva con la SNN di R9).
⚠️ Gli snapshot in `snn_variants/` sono stati storici CONGELATI: cosi' non si muta il file condiviso
`snn_b2_fsm.m` (lo scambio in-place produceva artefatti con meta' configurazione sbagliata).

### Perche' la directory di lavoro e' fuori dal repository

`/d/zbd_tradeoff` e' corta **e senza spazi**. Il repository sta sotto `1.Reti Neurali`, e lo spazio nel
percorso rompe `$readmemh`, le liste file di `xvlog` e altri strumenti — non e' solo il limite dei 260
caratteri di Windows. Chiudere il worktree non risolverebbe: comprerebbe 29 caratteri e lo spazio
resterebbe. La difesa giusta e' quella adottata qui: **gli output tornano nel repo archiviati e
verificati**, la scratch dir resta usa-e-getta.

---

## File

| file | cosa fa |
|---|---|
| `common/synth_point.tcl` | VHDL → post-sintesi + **DCP**; vincolo di clock e top opzionali |
| `common/impl_point.tcl` | DCP → post-route + tutte le metriche + flag di validita' |
| `common/run_campaign.sh` | driver ripartibile IIDM: sintesi + impl + raffinamento → riga CSV per punto |
| `common/gen_donatello_point.m` | genera il VHDL di UN punto Donatello (decode, snapshot SNN, arch); azzera slprj |
| `common/run_block_a_matrix.sh` | driver Blocco A architettura **chart** + `struct_gate` (cancello decode+SNN) |
| `common/run_block_a_split.sh` | driver Blocco A architettura **split** (due entita') |
| `../build_hdl_variants.m` | costruisce i blocchi; `archStyle` chart\|split, `decode_phase_code` fonte unica |
| `../build_decodedut.m` | probe del decode ISOLATO: pipeline (p3/p5) e macchina a fasi (ph3/ph5) |
| `../snn_variants/*.m` | snapshot CONGELATI di `snn_b2_fsm` per R2/R5/R9 (+ `MANIFEST`/`README`) |
| `../probe_two_mf.m` | probe make-or-break Fase 0 dello split |
| `donatello/points_split.tsv` | punti misurati con l'architettura split |
| `<blocco>/points.tsv` · `<blocco>/vhdl_*.tar.gz` | tabella punti · ingressi archiviati con sha256 |

**Regola trasversale**: ogni estrazione che fallisce scrive `NA` o `NON AGGANCIATO`, mai una cella
vuota, e nessun `catch` e' senza messaggio. Un `catch` muto ha gia' nascosto una volta l'unica
informazione che serviva (la licenza mancante).

---

## Documenti

- Design: `docs/superpowers/specs/2026-07-20-tradeoff-study-design.md`
- Piano di esecuzione: `docs/superpowers/plans/2026-07-20-tradeoff-campaign.md`
- Registro dell'ottimizzazione IIDM + audit: `matlab/hdl_iidm/RESULTS.txt` (§AUDIT)
- Registro SNN: `matlab/hdl_snn/RESULTS.txt` · tanh: `matlab/hdl_tanh/RESULTS.txt`
