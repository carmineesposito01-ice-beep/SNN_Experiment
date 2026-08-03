# Donatello — separare SNN e decode in due entita' di sintesi

**Goal:** rompere il muro a 41 MHz del blocco Donatello, che NON e' in nessuno dei due sotto-blocchi ma
nella loro compilazione condivisa, separandoli in due MATLAB Function distinte.

**Stato:** ✅ **ESEGUITO e RIUSCITO** (2026-07-22). p3+R5: 41,1 → 56,4 MHz; p5+R9: → **92,9 MHz** (×3
sul punto di partenza). Matrice split completa e verdetti in `RESULTS.md` §6–§7.
**Contesto e prove:** `matlab/study_tradeoff/donatello/RESULTS.md` §3, §5, §6, §7.

## ESITO — tutte le fasi superate

| fase | esito |
|---|---|
| 0 make-or-break | ✅ `probe_two_mf.m`: due MF con persistent → due entity, no dataflow, no re-inline |
| 1 split chart | ✅ `decode_phase_code` = fonte unica; `chart` non-regressione (dmax=0, lat 363), `split` dmax=0 lat 363 |
| 2 cancelli | ✅ dmax + hdl_gate + struct + SPLIT-OK (2 entity SNN/DEC nel VHDL) |
| 3 misura | ✅ p3+R5 = 56,440 (2 entity confermate) |
| 4 verdetto | ✅ matrice split completa; FAST = p5+R9 = **92,920 MHz** |

### Previsioni vs realta'
1. Fmax ~57 (p3) / ~92 (p5): ✅ **56,4 / 92,9** — azzeccate.
2. path non piu' da `started_not_empty`: ✅ ora `pv_not_empty` in **u_DEC**.
3. DSP ~38: ❌ **52** — la previsione era un errore di contabilita' (mancava il normalize, 14 DSP):
   nessuna duplicazione da fusione. Dichiarato e chiuso in RESULTS.md §6.

### File prodotti (tutti versionati)
- `matlab/probe_two_mf.m` — probe Fase 0.
- `matlab/build_hdl_variants.m` — `archStyle` chart|split, `mount_chart`/`mount_split`,
  `snn_chart_code`/`dec_chart_code`, `decode_phase_code` (fonte unica dello switch).
- `matlab/study_tradeoff/common/run_block_a_split.sh` — driver campagna split.
- `matlab/study_tradeoff/donatello/points_split.tsv` — punti misurati.
- artefatti in `D:/zbd_tradeoff/donatello_split/<tag>/` (VHDL + sintesi; non versionati, rigenerabili).

--- piano originale sotto (per storia) ---

---

## Perche' questa leva e non altre

Quattro ipotesi sono state **eliminate con esperimenti dedicati** (RESULTS.md §5): `decode_c`, la
macchina a fasi, la catena di init, il mux di init su `pv`. Resta una sola spiegazione, sostenuta da
**tre prove indipendenti**:

| prova | isolato | nel blocco |
|---|---|---|
| Fmax decode (stessa architettura a fasi) | **57,7** | **41,1** |
| DSP del decode | **16** | **~30** (55 totali − 22 SNN) |
| path critico | parte da `q1f`/`s1` (ingresso) | parte da `started_not_empty` (**controllo SNN**) e finisce su `pv` (uscita) |

Il probe dimostra che **separati** i due pezzi fanno 57,7 e 99,2 MHz.

---

## La modifica

```
OGGI:   [s,v,dv,v_l] --> MF "SNN" --> [v0,T,s0,a,b]
                         (normalize + snn_b2_fsm + decode a fasi, tutto inlinato in UNA chart)

DOPO:   [s,v,dv,v_l] --> MF "SNN" --> raw[5], valid --> MF "DEC" --> [v0,T,s0,a,b]
                         (normalize+fsm)                (latch rawl + fasi decode)
```

Il latch di `rawl` ([A1]) si sposta oltre il confine: stessa logica, altra collocazione.
Punto di intervento: `build_hdl_variants.m`, funzione `chart_code` (riga ~267) e il montaggio del
subsystem (riga ~119).

---

## ⚠️ Rischio principale — da provare PER PRIMO

`document/HDL_PHASE.md` §9: la **conversione MATLAB-to-dataflow** scatta quando una MATLAB Function
**convive con altri blocchi** nello stesso subsystem (chart sola → flusso normale, gia' provato).
Quando scatta vieta: struct empty-typed, `persistent` fuori dall'entry point, `divide()` variabile,
`tanh` in fixed-point.

**Il decode usa `persistent` per ogni fase.** Se la conversione scatta, l'approccio e' morto.

---

## Fasi

- [ ] **Fase 0 — probe make-or-break (~20 min).** Due MATLAB Function minimali, con un `persistent`
      ciascuna, nello stesso subsystem. Si guarda solo se genera VHDL.
      **Se fallisce si chiude qui**, avendo speso 20 minuti invece di 2 ore.

- [ ] **Fase 1 — split della chart (~40 min).** Dividere `chart_code` in `snn_chart_code`
      (normalize + `snn_b2_fsm` → `raw`, `valid`) e `dec_chart_code` (latch + macchina a fasi → i 5
      parametri). Cablare i segnali. I sorgenti restano **inlinati in entrambe** (autoconsistenza).

- [ ] **Fase 2 — cancelli (~20 min).**
      `run_block_traj_test` → `dmax = 0` (copre l'equivalenza attraverso il nuovo confine);
      `run_block_hdl_gate` → autoconsistenza con due chart;
      `struct_gate` → cerca gia' in tutti i `.vhd`, ma va verificato che regga il nuovo insieme di file.

- [ ] **Fase 3 — misura (~20 min).** Sintesi libera, confronto con 41,129 / 4706 LUT / 2165 FF / 55 DSP.

- [ ] **Fase 4 — verdetto (~20 min).** Se funziona: rimisurare le coppie bilanciate con l'architettura
      separata. Altrimenti: documentare e chiudere su `a_balanced`.

---

## Previsioni — scritte PRIMA della misura

Dopo quattro ipotesi sbagliate, si fissano in anticipo per non poterle riscrivere a posteriori.

1. **Fmax** → verso `min(SNN, decode)`: con `p3+R5` ~**57 MHz** (da 41,1).
2. **DSP** → da 55 verso ~**38** (22 SNN + 16 decode). *E' la previsione piu' discriminante*: il
   raddoppio dei DSP e' l'osservazione meno spiegabile altrimenti.
3. **Path critico** → non deve piu' partire da `started_not_empty` (controllo della SNN).

⚠️ Se l'Fmax sale ma i DSP restano 55: risultato giusto, meccanismo sbagliato. **Va detto.**

---

## Rischio secondario

HDL Coder potrebbe **re-inlinare** le due entita', annullando la separazione. Si verifica contando le
`ENTITY` nel VHDL: se ne resta una sola, la separazione non e' atterrata e il numero non significa nulla.

---

## Prerequisito

**Il commit.** Il refactor tocca `build_hdl_variants.m`, da cui dipende tutto il Blocco A. Su un albero
non versionato non si torna indietro — e le premesse dicono che va male in almeno un caso su due.
