# Studio di trade-off — design

**Obiettivo:** scegliere la configurazione da deployare su PYNQ-Z1 per i **due blocchi HDL-ready** —
`Donatello` (SNN + decode) e `Donatello + IIDM` (il precedente + la legge ACC-IIDM) — con una catena di
ragionamento verificabile da terzi, coprendo Fmax, latenza, risorse e potenza.

**Metodo:** vincoli + un obiettivo dichiarato per **decidere**; frontiera di Pareto per **presentare**.
Nessun punteggio pesato: i pesi sarebbero una scelta dell'autore, non una proprieta' del problema.

> **REVISIONI.** (a) 2026-07-20 mattina: disegno iniziale. (b) 2026-07-20 pomeriggio, dopo l'**audit
> pre-studio**: corretti il protocollo di misura (§2), caduta la struttura a due livelli (§2.4),
> ritrattata la conclusione della calibrazione (§6). (c) 2026-07-20 sera, dopo il **riesame dello
> scopo**: lo studio riguarda **due blocchi**, non i soli round IIDM; il decode e' fissato a LUT-64.
> Registro dell'audit: `matlab/hdl_iidm/RESULTS.txt` §AUDIT. Riesecuzione: `matlab/study_tradeoff/README.md`.

---

## 1. I due blocchi e i loro assi

| blocco | interfaccia | asse di trade-off | ordine |
|---|---|---|---|
| **Donatello** | `s,v,dv,v_l` → 5 parametri car-following | **accoppiamento** SNN ↔ decode (2 sotto-assi) | **primo** |
| **Donatello + IIDM** | `s,v,dv,v_l` → `accel` | round di **pipelining IIDM** (17 punti) | dopo |

## 0. IL PRINCIPIO CHE GOVERNA IL BLOCCO A (revisione 2026-07-21)

**Un blocco composto vale quanto il suo pezzo piu' lento.** Comporre una SNN da 99 MHz con un decode da
31 significa pagare ~1000 FF di pipelining che il blocco non puo' usare; comporre SNN 30 con decode 70
e' altrettanto sbilanciato. Il Blocco A non e' quindi uno sweep 1-D sulla profondita' SNN: e' la scelta
di **coppie bilanciate**, dove i due pezzi hanno Fmax vicina e nessuno dei due spreca.

### Le due curve, entrambe misurate

**SNN (core, probe forward-only)** — gia' esistenti:
R2 29,745 · R3 47,943 · R4 52,151 · R5 62,162 · R6 71,942 · R7 72,913 · R8 91,853 · R9 99,157 MHz

**Decode (probe isolato, `matlab/build_decodedut.m`)** — **misurato per la prima volta il 2026-07-21**:

| variante | Fmax | LUT | FF | livelli |
|---|---|---|---|---|
| `fused` (com'era) | 31,260 | 821 | 206 | 29 |
| `p3` (a \| b \| c) | 56,867 | 1007 | 388 | 14 |
| `p5` (a1 \| a2 \| b1 \| b2 \| c) | **97,828** | 1201 | 702 | 7 |

Il decode era stato **spezzato** 4 volte (round IIDM R4/R10/R12/R17) ma sempre in reazione al collo del
*controllore*, e i tagli vivono nella chart di `Donatello_ACC_IIDM_M`. La sua Fmax propria non era mai
stata misurata: lo sweep LUT registro' solo le RISORSE. **Non era un muro: era non pipelinato.**

### Le tre configurazioni bilanciate

| config | decode | SNN | composto atteso ≈ min |
|---|---|---|---|
| **SLOW** | fused (31,3) | R2 (29,7) | ~30 MHz |
| **BALANCED** | p3 (56,9) | R5 (62,2) | ~57 MHz |
| **FAST** | p5 (97,8) | R9 (99,2) | ~98 MHz |

Ogni coppia e' bilanciata entro ~5%.

⚠️ **Lo stato di partenza era la PEGGIORE combinazione possibile**: decode fuso (31) + SNN R9 (99) →
~30 MHz pagando i 2780 FF di R9. Sulla diagonale bilanciata la stessa area rende **~3,2x**.

I punti storici (`don_r2`…`don_r9`) restano nello studio come **narrazione dell'ottimizzazione** e come
prova della saturazione, non come candidati al deploy.

### ⚠️ I punti di Donatello si RICOSTRUISCONO: i probe forward-only non sono deployabili

I probe `snn_fwd_r2..r9` (ingressi `x1..x4`, uscite `o1..o5`) sono la SNN **senza decode**: erano lo
*strumento di misura* dei round SNN — si isola il core apposta per vederne il tetto — **non**
configurazioni. Uno studio che sceglie cosa deployare non puo' misurare cio' che non si deploya.

✅ **Gli 8 round SNN sono committati uno per uno**, quindi ogni stato si ricostruisce completo:

| punto | commit | leva |
|---|---|---|
| `don_r2` | `bb50f9f0` | accumulo reci ad adder-tree |
| `don_r3` | `350f43ce` | split stadio-C in 2 (C1 MAC / C2 soglia) |
| `don_r4` | `98a76657` | split albero reci a meta' |
| `don_r5` | `8b4843dc` | Ii ad albero (4→2→1) |
| `don_r6` | `d03182b0` | stadio MAC (Cm) registrato |
| `don_r7` | `82952c11` | split C2 a nC_V |
| `don_r8` | `014db171` | split C2a a Vi |
| `don_r9` | `c9846f40` | split mux xbuf dal DSP mult |
| `don_now` | working tree | stato attuale (include il decode spezzato dei round IIDM) |

**Procedura per punto:** `git worktree add /d/zbd_snnwt/<tag> <commit>` (path corto e senza spazi, che
risolve anche il problema dei percorsi) → `build_hdl_variants()` + `rtl_gen_dut('Donatello_LUT64', …)`
→ VHDL del **blocco completo** → protocollo di misura. I worktree si rimuovono a fine campagna.
Verificato: `rtl_gen_dut` genera l'RTL di un blocco di libreria avvolgendolo in un subsystem, e
`Donatello_LUT64` esisteva gia' al commit di R2.

`don_now` e' incluso perche' i round IIDM hanno spezzato anche il **decode** (R4/R10/R12/R17). Il
sorgente e' pero' **ricomposto in una chiamata sola** per i chiamanti — `snn_decode_lut` cita
esplicitamente `Donatello_LUT16..512` — quindi per Donatello standalone dovrebbe girare in un clock
come a R9. **Lo si misura invece di dedurlo**: se `don_now` ≡ `don_r9` e' una conferma, se differisce
e' un risultato.

I probe forward-only **restano come riferimento diagnostico**: il confronto core-isolato vs blocco
completo misura quanto pesa davvero il decode — domanda finora senza risposta misurata.

### ⚠️ Dipendenza A → B (motivo dell'ordine)

**Tutti i 17 punti IIDM incorporano la SNN allo stato R9**: la 2d si e' chiusa il 18/07 alle 23:18, i
round IIDM sono del 19-20/07. Quindi: se A raccomanda `don_r9`, B parte con gli artefatti esistenti; se
raccomanda un altro stato, i 17 VHDL vanno **rigenerati su quella base** prima che B abbia senso — costo
grosso. Per questo **A si esegue per primo**.
Indizio, non conclusione: R9 e' il piu' veloce (99,157 OOC) e costa +5,4% di LUT su R2 (3132 vs 2971),
quindi e' probabile che vinca — ma e' cio' che lo studio deve stabilire.

**Il decode NON e' un asse: e' fissato a LUT-64.** La scelta era gia' stata presa con la regola
dell'errore di approssimazione sotto la soglia di quantizzazione fixed accettata (0,028) —
`document/DECODE_LUT_SWEEP.md`. L'accuratezza e' comunque piatta (84,06 → 83,97 % da N=16 a N=512):
non discriminava. Le altre varianti restano documentate dallo sweep.

### 1.1 Le ottimizzazioni sono cumulative, non alternative

```
2b  tanh          4 varianti -> vince A1 (LUT piena): bit-exact, 136 MHz, 545 LUT, 0 DSP
                  integrata -> controllore 9,30 -> 10,58 MHz
2d  SNN->decode   split readout/decode + albero reci -> 10,58 -> 15,84 MHz
SNN forward       pipeline dello stadio-C in 8 stadi -> 29,75 -> 99,16 MHz   <-- asse Donatello
IIDM              R1..R17 -> 15,673 -> 77,936 MHz                             <-- asse Donatello+IIDM
```

Che i round SNN siano integrati nel controllore e' **verificabile**, non assunto: nello spettro dei
path di `iidm_r17` gli endpoint del plateau sono `pCm_recip`/`pCm_Iip`, cioe' lo stadio MAC introdotto
a SNN R6. Quindi i 17 punti IIDM condividono tutti la stessa SNN pienamente ottimizzata, e l'unica cosa
che varia fra loro e' il pipelining dell'IIDM: **e' un asse pulito a variabile singola.**

### 1.2 Integrita' degli ingressi — verificata e messa in sicurezza

- I numeri storici sono stati **riparsati dai report Vivado salvati**: **tutti** e 17 i punti IIDM e
  **tutti** e 8 i punti SNN combaciano con le tabelle in `RESULTS.txt`. Nessun errore di trascrizione.
- I round IIDM sono configurazioni genuinamente diverse: `IIDM_CTRL.vhd` cresce monotono
  1.230.151 → 1.380.427 byte.
- ⚠️ **I sorgenti MATLAB per-round NON esistono** (modifiche in place; HEAD e' a `0d8ee0f9`, era R1; il
  lavoro R2→R17 non e' committato) e `matlab/hdl_pipe/` e' in `.gitignore`. Il VHDL generato e'
  l'**unica copia** di ogni configurazione, e stava solo in `D:/zbd_pipe/` — fuori dal repo. Non e'
  ipotetico: il progetto ha gia' perso una scratch dir (`D:/zbd_pb2`, citato in `gen_saif_b2.sh`).
  → Archiviati con manifest sha256 e **ripristino provato** (non assunto) in
  `matlab/study_tradeoff/{donatello/vhdl_snn_points.tar.gz, donatello_iidm/vhdl_rounds.tar.gz}`.

### 1.2-bis Interventi applicati al blocco standalone (nuovi, 2026-07-21)

**[A1] disaccoppiamento readout↔decode.** `2d R1` (`e7eeb96f`) aveva disaccoppiato i due stadi **solo**
in `acciidm_m_chart_code()` — la chart del controllore. I blocchi `Donatello_LUT*` nascono da
`chart_code()`, dove il decode girava **nello stesso clock** del readout. Applicato li' lo stesso
pattern (`rawl` registro vero, decode del campione latchato al ciclo precedente):

| | Fmax | LUT | FF | path critico | liv |
|---|---|---|---|---|---|
| `don_r9` (fuso) | 25,321 | 4754 | 2773 | `pC_valid_2 → pv_2` | 46 |
| `don_a1` | **30,367** | 4849 | 2891 | `started_not_empty_2 → pv_2` | 30 |

**+19,9%** per +95 LUT, +118 FF, **+1 clock** di latenza (400→401). ✅ Cancello sui dati verde:
`dmax = 0` su traiettorie 1/7/23 (`matlab/gate_donatello_a1.m`).

⚠️ **Il cancello competente per l'ORDINE dei due blocchi e' l'Fmax, non il dmax.** Invertendo latch e
decode i valori sarebbero identici — solo disponibili un clock prima — e il test su traiettoria darebbe
`dmax = 0` lo stesso. A vederlo e' la sintesi: se il path critico torna `pR_idx → pv`, non e' atterrato.

**[A2] decode a fasi nel blocco standalone** — da eseguire: cablare in `chart_code()` le fasi gia'
esistenti e gia' provate bit-exact, con una piccola macchina a fasi (oggi c'e' solo il flag `dodec`).

### 1.3 Limiti dichiarati sull'asse Donatello

- Il VHDL del Champion su disco (17/07) **non si riusa**: precede il pipelining SNN del 18/07. Ogni
  punto si rigenera dal proprio commit.
- **Bit-exactness dei punti ricostruiti**: ad ogni round storico il cancello parity era verde
  0/60000, e la rigenerazione e' deterministica da quel sorgente. Per **tutti** i punti si verifica che
  la generazione HDL chiuda con 0 errori e che l'interfaccia dell'entity combaci; sui **candidati** che
  escono dall'analisi si rifa' il cancello pieno.
- `git worktree` su ciascun commit **non tocca il working tree attuale**: il Blocco A non richiede il
  commit del lavoro IIDM per partire.
- Il core resta **congelato bit-identico**: si ricostruiscono stati storici gia' esistiti e gia'
  validati, non si creano configurazioni nuove.

---

## 2. Protocollo di misura

### 2.1 Il difetto trovato dall'audit

In `scripts/synth_acc_iidm.tcl:24,29` e `scripts/spectrum_iidm.tcl:21,25` `synth_design` gira **prima**
di `create_clock`: **tutta** la sintesi storica — i 77,936 MHz dell'IIDM come i 99,16 della SNN — e'
senza vincolo. E l'implementazione di calibrazione girava a 125 ns, ~6× piu' lasca del raggiungibile.

**Misurato sullo stesso netlist R17, cambiando solo il modo di misurare:**

| flusso | vincolo impl | WNS | Fmax post-route | LUT | FF |
|---|---|---|---|---|---|
| sintesi libera | 125 ns | +103,910 | 47,416 | — | — |
| sintesi libera | 14 ns | +0,269 | 72,828 | 7950 | — |
| sintesi libera | 12,831 ns | −0,055 | 77,604 | 7991 | 4069 |
| sintesi libera | 11 ns | −2,346 | 74,929 | 8189 | — |
| **sintesi vincolata** | **12,831 ns** | +0,380 | **80,315** | **7902** | **3988** |

Tre conseguenze, tutte contro-intuitive e tutte misurate:

1. **Un'Fmax post-route con vincolo lasco non e' una proprieta' del design**: con 103 ns di slack
   placer e router non hanno pressione e si fermano.
2. **Sovra-vincolare PEGGIORA**: 11 ns invece dei ~12,8 raggiungibili costa −3,6% di Fmax e +2,5% di
   LUT. L'euristica «stringi molto e leggi periodo − WNS» e' una trappola.
3. **Vincolare la sintesi conviene**: +3,5% di Fmax con *meno* area. Costa 312 s invece di 109 s.

Anche le **risorse** dipendono dal vincolo (7902 / 7950 / 7991 / 8189 / 8387 LUT sullo stesso netlist):
una frontiera (Fmax, LUT) e' confrontabile solo se tutti i punti usano lo stesso protocollo.

### 2.2 Il protocollo adottato

1. **Sintesi vincolata** al ritardo stimato OOC di quel punto (`period = delay_OOC = 125 − WNS_OOC`),
   via XDC letto **prima** di `synth_design` (le porte non esistono come oggetti prima dell'elaborazione).
2. **Implementazione** allo stesso periodo.
3. **Regola di validita':** `ritardo = periodo − WNS` vale solo se **WNS ≤ 0**. Con WNS > 0 il tool si
   e' fermato al vincolo: il driver **rifa'** l'implementazione al ritardo appena raggiunto (max 3
   tentativi). Non si stringe a caso, per via del punto 2 sopra.
   **Si riporta il migliore dei tentativi, non l'ultimo**: place&route non e' monotono — su R17 il
   raffinamento a 12,451 ns e' atterrato a 12,544, peggio del tentativo che l'aveva generato. Il numero
   di tentativi resta nel CSV (`n_impl`).
4. **WHS ≥ 0** obbligatorio: senza hold positivo il design non e' valido a quel vincolo.
5. Il periodo in vigore si **rilegge** e si assert-a contro quello chiesto.

Script: `matlab/study_tradeoff/common/{synth_point.tcl, impl_point.tcl}`, orchestrati da
`run_campaign.sh` (ripartibile). Tutti validati end-to-end su R17.

### 2.3 Cosa misura davvero

Implementazione OOC senza `HD.PARTPIN_LOCS` → Vivado avverte che il timing **da/verso le porte** non e'
accurato (`WARNING [Route 35-198]`). Il numero e' il **tetto interno registro-registro del blocco**, non
il timing d'integrazione, che dipendera' dal wrapper AXI. ✅ Verificato che i path critici misurati sono
tutti reg→reg interni: la misura e' valida per lo scopo, che e' **confrontare configurazioni**.

### 2.4 La struttura a due livelli e' CADUTA

Il disegno iniziale usava `report_qor_assessment` come ponte per caratterizzare tutti i punti con la
sola sintesi. ⛔ **Non e' utilizzabile**: richiede licenza superiore alla BASIC installata
(`ERROR: [Implflow 47-2944]`). Ed e' l'errore che spariva dentro un `catch` muto.
→ Non serve un surrogato: **si implementa ogni punto davvero**.

### 2.5 Potenza

- **Base del banco**: `matlab/axi/acciidm_m/tb_acciidm_m_open.v` (l'harness del cancello B-1). Gli
  strumenti della Fase B pilotano un altro top (`tb_b2_stream`, design AXI): riusabile e' il **metodo**
  (funcsim + `xelab -L unisims_ver` + `glbl` + `log_saif`/`write_saif`), non il banco.
- ✅ **Fattibilita' verificata**: l'entity `DUT` ha **esattamente** la stessa interfaccia del modulo
  pilotato dal banco (`clk,reset,clk_enable,s,v,dv,v_l → ce_out,accel`). Basta il nome del modulo.
- ⚠️ **DUTY CYCLE**: il banco tiene `HOLD` clock per control-step (~66% di attivita'), il sistema vero
  ne usa ~594 su 800.000 (**0,07%**). Una dinamica presa da quel SAIF sopravvaluta di ~1000×. Si
  riportano **due scenari dichiarati**: *back-to-back* (confronto fra punti) e *duty reale* (consumo).
- **Power Constraints Advisor** obbligatorio: confidenza bassa ⇒ il numero si **scarta**.
  `set_operating_conditions` di **default, dichiarate**, + sensibilita' alla temperatura di giunzione.

---

## 3. Criterio di decisione

**Vincoli** (filtrano l'ammissibile), per entrambi i blocchi:
1. Timing chiuso con **WNS e WHS positivi** post-route.
2. Bit-exactness: cancelli verdi (G2, G3/G4, parity 0/60000, B-1, self-contained).
3. Decode a LUT-64 (gia' deciso).

**Area: NON vincolante.** Si riporta l'occupazione percentuale (la colonna % e' gia' in `util.rpt`). La
soglia si fissera' col dimensionamento del V2I: inventarla ora sarebbe una scelta mascherata da misura.

**Obiettivo** fra le ammissibili: **massimizzare il margine di timing**, coerente col fatto che qui
l'Fmax vale come margine — slack, tolleranza PVT, spazio per la logica futura.

---

## 4. Forma del risultato

Per **ciascuno dei due blocchi**:

1. Tabella completa dei punti con la **provenienza di ogni numero** e il vincolo usato.
2. Grafico della frontiera post-route con i **punti dominati visibili** — mostra perche' sono esclusi.
3. Delta OOC↔post-route punto per punto (su R17 con sintesi vincolata e' **+3,1%**: se non fosse
   uniforme fra i punti, e' un risultato).
4. Tre punti etichettati SLOW / BALANCED / FAST scelti **sulla frontiera vera**.
5. Configurazione raccomandata con la catena esplicita: vincoli → esclusi e perche' → obiettivo →
   vincitore.

E una figura d'insieme: **il contributo di ciascun pezzo ottimizzato** (tanh → SNN → decode → IIDM) e
dove i due blocchi sono arrivati.

### Tre avvertenze che il documento DEVE contenere

- **L'Fmax vale come MARGINE, non come velocita'.** Il blocco usa ~594 clock su 800.000 per
  control-step: e' gia' ~1400× piu' veloce del necessario. Alzare il clock costerebbe potenza dinamica
  senza comprare nulla.
- **La potenza statica e' ~90% del totale**, dipende da dispositivo e temperatura, non dalla
  configurazione: discrimina pochissimo (116 vs 115 mW) e non va usata per scegliere.
- **Ogni frequenza deve dichiarare il vincolo con cui e' stata misurata.** E' la lezione centrale
  dell'audit: gli stessi bit danno 47,4 o 80,3 MHz a seconda di cosa si e' chiesto al tool.

---

## 5. Cosa NON copre

- Donatello completo a profondita' di pipeline ridotte (il core e' congelato bit-identico): l'asse e'
  misurato sui probe forward-only, dichiarati come tali.
- Il dimensionamento del V2I, da cui dipendera' la soglia d'area.
- Il timing d'integrazione col wrapper AXI (§2.3).
- Il difetto preesistente su traiettoria 1 in anello chiuso (dmax=0,039, verificato IDENTICO a HEAD:
  non e' una regressione dei 17 round, ma resta da spiegare).

---

## 6. Costi misurati e ritrattazione

| passo | misurato |
|---|---|
| sintesi **libera** + `write_checkpoint` | 109 s + 9 s |
| sintesi **vincolata** | 312 s |
| implementazione (vincolo di protocollo) | 208–295 s |
| **totale per punto** | **~9 min** |

⚠️ **Costo dimenticato nel preventivo iniziale: mancavano 14 DCP.** Esistono solo `spec_r1/r2/r17`;
`synth_acc_iidm.tcl` non salva il checkpoint. E il commento in `spectrum_iidm.tcl:27` («sintesi da 15
minuti») e' **stale**: sono 1 min 49 s.

**Preventivo per blocco** (i punti di Donatello costano di piu': va aggiunta la generazione HDL da
worktree, ~3-6 min a punto):

| blocco | punti | costo a punto | totale |
|---|---|---|---|
| **A — Donatello** | 9 | ~12-15 min (worktree + HDL + sintesi + impl) | **~2 h** |
| **B — Donatello + IIDM** | 17 | ~9 min (sintesi + impl) | ~2 h 40 min |
| | | **totale** | **~4 h 40 min** |

piu' la potenza e l'eventuale sweep di strategie. Il preventivo iniziale di «70 minuti» era ottimista
di ~4×: non contava le sintesi mancanti, usava il tempo di un'implementazione senza pressione di timing,
e misurava probe invece di blocchi deployabili.

### ⛔ La conclusione della calibrazione precedente era un ARTEFATTO

Diceva: *«il post-route e' piu' lento del 39%, i 77,9 MHz e l'intera scala dei tetti sono
ottimistici»*. **Falso.** Quei 47,416 MHz venivano da un'implementazione senza pressione di timing. Col
protocollo lo stesso netlist da' **80,315 MHz**, cioe' **piu'** della stima OOC. La mappa dei tetti
regge.

🔎 **Nota di metodo:** un numero *peggiore* del previsto non e' automaticamente il numero vero. Il
risultato "brutto" sembrava credibile — «il routing reale costa» e' un fatto noto — e per questo non era
stato messo in discussione. Smentirlo e' costato una singola esecuzione da 3 minuti.

---

## 7. Tracciato del dato — cosa si registra a OGNI esecuzione

- **Identita'**: blocco, punto, **periodo imposto**, n. di tentativi, versione Vivado (2026.1, build
  6511674), part (`xc7z020clg400-1`), data.
- **Timing**: WNS, WHS, TNS, THS; ritardo raggiungibile; Fmax; **flag di validita' (WNS ≤ 0)**; path
  critico setup **e** hold (start/end/livelli/ritardo).
- **Risorse**: LUT, LUTRAM, FF, DSP, BRAM — assoluti **e** % (gia' in `util.rpt`).
- **Potenza**: totale/dinamica/statica + **confidenza** + condizioni operative + **quale scenario di
  duty**. *Un numero di potenza senza confidenza e scenario NON e' riportabile.*
- **Costo**: tempo di sintesi e di implementazione.

*(Il campo "punteggio QoR" e' RIMOSSO: non ottenibile con licenza BASIC — §2.4.)*

**Artefatti conservati**: DCP post-route + report integrali per ogni esecuzione. E' lo stesso motivo per
cui il DCP salvato da `spectrum_iidm.tcl` ha permesso scala dei tetti, calibrazione **e** l'intero audit
senza risintetizzare.

### Difetti risolti durante l'audit
- ✅ **Regex risorse**: la causa non era il formato del report post-route ma il **backslash in Tcl** —
  dentro `"..."` la sequenza `\s` collassa in `s`. Verificato: con `\\s` tutte le risorse si agganciano.
- ✅ **`catch` muto**: catturando l'errore e' emersa la causa vera (licenza BASIC).
- ✅ **`remove_clock` non esiste in Vivado**: `create_clock` con lo stesso nome ridefinisce.

### Difetti di processo ancora APERTI (fuori dallo studio)
- `hold` di default sotto la latenza reale nei cancelli SP2; il commento che lo giustifica cita 341,
  che e' la latenza della sola SNN.
- `snn_cl_step_mex` non versionato: il «dmax=0 su 10/10» documentato non e' riproducibile da un
  checkout pulito.
- Traiettoria 1 in anello chiuso: dmax=0,039, preesistente, non spiegato.
