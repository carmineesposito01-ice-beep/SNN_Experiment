# Blocco A — Donatello (SNN + decode, LUT-64). Risultati

Asse: accoppiamento SNN ↔ decode. Ogni punto e' il **blocco completo e deployabile**, generato da uno
snapshot congelato della SNN (`matlab/snn_variants/`) + una variante di decode, e passato dal cancello
strutturale che verifica **entrambe** le meta' sull'artefatto (`run_block_a_matrix.sh` → `struct_gate`).
Protocollo di misura: `README.md` §protocollo.

---

## 1. La matrice misurata

| esperimento | decode | SNN | Fmax | LUT | FF | DSP | path critico |
|---|---|---|---|---|---|---|---|
| `a_slow` | fused | R2 | 29,237 | 4053 | 1708 | 52 | `pR_idx → pC_fat` 55 liv — **dentro la SNN** |
| `a_ctrl_dec` | p5 | R2 | 29,237 | 4893 | 2220 | 55 | `pR_idx → pC_fat` 55 liv — **dentro la SNN** |
| **`a_balanced`** | **p3** | **R5** | **41,129** | **4706** | **2165** | 55 | `→ pv_2` 23 liv |
| `a_fast` | p5 | R9 | 41,095 | 5766 | 3288 | 55 | `→ pv_2` 23 liv |
| `a_fast6` | p6 | R9 | 38,145 | 6178 | 3425 | 57 | `→ pv_2` 24 liv |
| *(rif.)* `don_a1` | fused | R9 | 30,367 | 4849 | 2891 | — | `→ pv_2` 30 liv |
| *(rif.)* `don_r2` | fused pre-[A1] | R2 | 16,120 | 3890 | 1705 | 52 | `pR_idx → pv_2` 88 liv |

✅ **Raccomandato: `a_balanced`.** Domina `a_fast` (stessa Fmax, −1060 LUT / −1123 FF) e `a_fast6`
(+7,8% di Fmax, −1472 LUT). Il Donatello deployabile passa da **25,3 → 41,1 MHz** con area **inferiore**
a quella di partenza.

### I due controlli, entrambi netti

- **SNN sovradimensionata** (`don_a1` vs `a_slow`): fused+R9 = 30,4 contro fused+R2 = 29,2. I 2780 FF
  di R9 comprano +4%.
- **decode sovradimensionato** (`a_ctrl_dec` vs `a_slow`): p5+R2 = **29,237, identico all'ultima cifra**
  a fused+R2, con lo stesso path dentro la SNN. Cinque fasi di decode costano +840 LUT e +512 FF e
  comprano **zero**.

→ Conta l'**accoppiamento**, non la profondita' di uno dei due pezzi. Dimostrato su misure, nei due versi.

---

## 2. Le due curve dei sotto-blocchi (probe isolati)

**SNN core** (forward-only): R2 29,745 · R3 47,943 · R4 52,151 · R5 62,162 · R6 71,942 · R7 72,913 ·
R8 91,853 · R9 99,157 MHz — 22 DSP.

**Decode** (`matlab/build_decodedut.m`), misurato in **due architetture**:

| variante | architettura | Fmax | LUT | FF | DSP | liv |
|---|---|---|---|---|---|---|
| `fused` | 1 stadio | 31,260 | 821 | 206 | 16 | 29 |
| `p3` | pipeline 3 stadi | 56,867 | 1007 | 388 | 16 | 14 |
| `p5` | pipeline 5 stadi | 97,828 | 1201 | 702 | 16 | 7 |
| `ph3` | **macchina a fasi** 3 | **57,680** | 1200 | 408 | 16 | 14 |
| `ph5` | **macchina a fasi** 5 | **92,876** | 1747 | 739 | 16 | 5 |

---

## 3. ⛔ IL MURO A 41 MHz — DUE IPOTESI SMENTITE, UNA LOCALIZZAZIONE

Tre configurazioni molto diverse convergono a ~41 MHz (`p3+R5`, `p5+R9`) o peggiorano (`p6+R9`).
Le due spiegazioni che ho proposto sono state **smentite da esperimenti dedicati**.

### ❌ Ipotesi 1: il collo e' `decode_c` (`lo + hilo*sv`)

Motivata dal path critico: 2 DSP48E1 + 15 CARRY4, e `decode_c` e' una fase UNICA sia in `p3` sia in
`p5` — il che spiegava perche' davano lo stesso numero.
**Esperimento**: variante `p6`, con `decode_c` spezzata in `decode_c1` (prodotti) / `decode_c2`
(somma+cast), bit-exact (`dmax=0`, latenza 406 = +1 su p5).
**Esito: SMENTITA.** `a_fast6` da' **38,145 MHz** — *peggio* di `p3`/`p5`, con un livello in piu' e
+412 LUT. Spezzare `decode_c` non aiuta.

### ❌ Ipotesi 2: il collo e' la macchina a fasi (mux di selezione davanti all'aritmetica)

Motivata dal fatto che il path parte da un registro di **controllo** (`started_not_empty_2`) e che
aggiungere fasi peggiorava (3→24,314 · 5→24,334 · 6→26,216 ns).
**Esperimento**: probe del decode isolato **riprodotto a macchina di fasi** (`ph3`/`ph5`) invece che a
pipeline.
**Esito: SMENTITA.** `ph3` = 57,680 (vs 56,867 della pipeline) e `ph5` = 92,876 (vs 97,828). La
macchina a fasi **non e' piu' lenta** della pipeline: stessi livelli, stessi 16 DSP.

### ✅ Dove il collo E' localizzato: nell'INTEGRAZIONE

Il decode, **con la stessa architettura del blocco**, fa 57,7 MHz da solo e 41 dentro il blocco.
Tre prove indipendenti che la causa e' la convivenza SNN+decode nella stessa chart:

1. **Il path critico e' DIVERSO, non lo stesso rallentato.** Nel probe finisce su `q1f`/`s1`
   (l'*ingresso* della catena); nel blocco finisce su `pv_2` (l'*uscita*).
2. **I DSP raddoppiano**: 16 nel probe isolato, ~30 nel blocco (52 totali − 22 della SNN). HDL Coder
   genera hardware diverso per la stessa aritmetica quando la compila insieme alla SNN.
3. **Il path parte dal controllo della SNN**: `started_not_empty_2_reg_rep__N` — registro REPLICATO da
   Vivado per il fanout — con nodi a fo=117 e fo=71 che costano 1,8 ns di solo instradamento. Quel
   segnale nel probe del decode **non esiste**: e' il controllo della FSM della SNN che entra nel
   datapath del decode.

Ripartizione del ritardo (`a_balanced`): 24,307 ns = **logica 15,490 (64%) + routing 8,817 (36%)**.

### ✅ La misura della SNN e' invece CONFERMATA dal composto

Con R2 il composto da' 29,237 e il path e' **dentro la SNN**, contro 29,745 della SNN isolata: i due
numeri coincidono. Quando e' la SNN a limitare, probe e blocco concordano. E' solo quando il limite
passa al decode che il composto scende sotto **entrambi** i pezzi — la firma di un costo d'integrazione.

---

## 4. Interventi applicati al blocco (nuovi in questo studio)

**[A1] disaccoppiamento readout↔decode.** `2d R1` (`e7eeb96f`) l'aveva fatto **solo** in
`acciidm_m_chart_code()` (la chart del controllore); i blocchi `Donatello_LUT*` nascono da
`chart_code()`, dove il decode girava nello stesso clock del readout. Applicato li' lo stesso pattern:
**25,321 → 30,367 MHz (+19,9%)** per +95 LUT, +118 FF, +1 clock di latenza (400→401). `dmax=0` su
traiettorie 1/7/23.

**[A2] decode a fasi in `chart_code`.** Varianti `p3`/`p5` cablando le fasi gia' esistenti e provate
bit-exact (round IIDM R4/R10/R12/R17). Latenze 401/403/405 per 1/3/5 fasi — conferma **strutturale** che
le fasi girano, che il solo `dmax` non darebbe.

**[A3] `decode_c` spezzata** in `decode_c1`/`decode_c2` (variante `p6`). Bit-exact ma **controproducente**
sul timing: resta nel codice come single-source (`decode_c` e' la loro composizione), la variante `p6`
resta disponibile ma **non e' raccomandata**.

⚠️ **Il cancello competente per l'ORDINE delle fasi e' l'Fmax, non il `dmax`.** Invertendo latch e
decode i valori sarebbero identici, solo disponibili un clock prima: il test su traiettoria darebbe
`dmax=0` lo stesso. Lo vede solo la sintesi.

---

## 5. LA CACCIA AL FAST — quattro cause ELIMINATE, una LOCALIZZATA

Ogni ipotesi e' stata chiusa da un esperimento dedicato, non da un'argomentazione.

| # | ipotesi | esperimento | esito |
|---|---|---|---|
| 1 | il collo e' `decode_c` (`lo + hilo*sv`) | variante `p6` (c1/c2 separate) | ❌ **38,145** — *peggiora* |
| 2 | il collo e' la macchina a fasi (mux di selezione) | probe `ph3`/`ph5` a fasi | ❌ **57,680 / 92,876** — non e' lei |
| 3 | il collo e' la catena di init dei persistent | `perVar-v1` (ogni var il suo isempty) | ❌ **29,678** — *peggiora* |
| 4 | il collo e' il mux di init sull'uscita `pv` | `perVar-v2` (isola solo `pv`) | ❌ **41,125** — nessun effetto |

Dettagli utili a non ripercorrerli:

- **[1]** `decode_c` era fase UNICA in `p3` e `p5`, il che spiegava perche' dessero lo stesso numero.
  Spezzarla aggiunge un livello (23→24) e 412 LUT: `a_fast6` = 38,145 MHz. `decode_c1`/`decode_c2`
  restano nel codice come single-source (`decode_c` e' la loro composizione) ma **`p6` non e' raccomandata**.
- **[2]** Il probe originale era una **pipeline**, il blocco e' una **macchina a fasi**: architetture
  diverse. Ricostruito il probe a fasi (`ph3`/`ph5`), da' 57,7 / 92,9 — cioe' **quanto la pipeline**.
  La macchina a fasi non costa nulla di per se'.
- **[3]** ⚠️ **Esperimento MAL DISEGNATO**: separare ogni `isempty` rendeva VIVA la catena degli
  inizializzatori (`rawl → decode_a → decode_b`), che serve solo a fissare i tipi. Path `rawl→pv` di
  **32 livelli**. Cambiava DUE cose insieme, quindi non isolava nulla. Lezione: un esperimento che
  modifica due variabili non smentisce ne' conferma.
- **[4]** Isolare il solo `pv` (endpoint del path) lascia tutto invariato: 41,125 vs 41,129, stessi 23
  livelli, stesso startpoint. Il flag di init **non e' la causa**.

### ✅ L'unica ipotesi rimasta: il costo e' nell'INTEGRAZIONE

Il decode, **con la stessa architettura del blocco**, fa 57,7 MHz da solo e 41 dentro il blocco.
Tre prove indipendenti che la causa e' la convivenza SNN+decode nella stessa unita' di compilazione —
vedi §3. La leva conseguente e' **separare il decode in una propria entita' di sintesi** invece di
inlinarlo nella chart della SNN: e' l'unica che il probe dimostra funzionare (separati: 57,7 e 99,2).
Costo stimato ~2 h, con l'incognita che HDL Coder potrebbe re-inlinare comunque.

## 6. ✅ IL FAST TROVATO — separazione SNN | decode in due entita' di sintesi

L'unica ipotesi rimasta (§5) era che il muro fosse un costo d'INTEGRAZIONE. Provata separando SNN e
decode in **due MATLAB Function distinte** nel subsystem (`archStyle='split'` in `build_hdl_variants`),
cosi' HDL Coder le sintetizza come entita' separate (`SNN.vhd` + `DEC.vhd`, wrapper con `u_SNN`/`u_DEC`).

| | Fmax | LUT | FF | DSP | path critico | liv |
|---|---|---|---|---|---|---|
| `chart` (a_balanced, p3+R5) | 41,129 | 4706 | 2165 | 55 | `started_not_empty → pv_2` | 23 |
| **`split` (p3+R5)** | **56,440** | **4282** | 2173 | 52 | `pv_not_empty → q1f` (in **u_DEC**) | **14** |

**+37% di Fmax, con MENO LUT.** Il muro d'integrazione e' caduto: il blocco separato raggiunge quasi
l'Fmax del decode isolato (57,7).

### Cancelli superati
- **Fase 0 make-or-break**: due MF con `persistent` nello stesso subsystem → due entity, NO conversione
  a dataflow (`probe_two_mf`). Il rischio principale era questo, ed e' escluso.
- **Non-regressione** `chart`: estrarre `decode_phase_code` (fonte unica dello switch) non cambia il
  comportamento della chart unica — `dmax=0`, latenza 363 invariata.
- **Split bit-exact**: `dmax=0`, **stessa latenza 363** → il segnale al confine e' combinatorio, nessun
  ciclo di ritardo introdotto.
- **Rischio re-inline**: 2 entity distinte nel VHDL, non fuse.

### Le previsioni (scritte PRIMA), oneste
1. **Fmax → ~57**: ✅ **56,440**, sul `min(SNN 62, decode 57)`.
2. **path non piu' da `started_not_empty`**: ✅ ora `pv_not_empty` **dentro u_DEC** → il controllo SNN
   non attraversa piu' il confine. Prova diretta che la causa era l'integrazione.
3. **DSP → ~38**: ❌ scesi solo a **52** (da 55). *Meccanismo in parte sbagliato, dichiarato*: i ~30 DSP
   del decode nel blocco NON erano una duplicazione da fusione — ci sono anche separati. Il costo
   d'integrazione caduto era il **routing del controllo**, non i moltiplicatori. Le evidenze [1] e [2]
   di §3 erano giuste e bastavano; la [3] (raddoppio DSP) era una lettura errata.

### ✅ Domanda dei DSP: CHIUSA (era un mio errore di contabilita', non un artefatto)

Il "raddoppio DSP" della previsione [3] non e' mai esistito. Il conto onesto del blocco split:

| pezzo | DSP | fonte |
|---|---|---|
| SNN core | 22 | `hdl_snn/RESULTS.txt` SNNFWD R5 |
| decode p3 | 16 | probe `decode_synth_p3` |
| **normalize** | ~14 | i 4 reciproci `invS/invV/inv2DV/invVL` su tipi a 34 bit — **4 moltiplicazioni larghe** |
| **totale** | **~52** | = misurato |

La mia previsione di 38 sommava DUE probe (SNN forward-only + decode) che **insieme NON coprono
l'intero blocco**: il probe SNN parte da `xn` GIA' normalizzato (HDL_PHASE §3.1), quindi il normalize —
sempre presente nel blocco reale — mancava dal conto. Nessun DSP e' duplicato dalla fusione: i 52 sono
la somma dei tre pezzi. Conferma a posteriori che la previsione [3] era sbagliata per un errore di
contabilita' sui probe, non per un fenomeno d'integrazione.

## 7. MATRICE SPLIT COMPLETA — il FAST vero a 92,9 MHz

Rimisurata l'intera matrice con `archStyle='split'` (`run_block_a_split.sh`, driver verificato su
`sp_balanced` = riproduce la misura a mano all'ultima cifra). Snapshot SNN congelati, cache azzerata,
cancello strutturale (decode + SNN + SPLIT-OK: due entity distinte), `snn_b2_fsm.m` mai toccato.

| tier | config | chart Fmax | **split Fmax** | LUT split | FF | DSP | path critico (split) |
|---|---|---|---|---|---|---|---|
| SLOW | fused+R2 | 29,2 | **30,5** | 4053 | — | — | — |
| BALANCED | p3+R5 | 41,1 | **56,4** | 4282 | 2173 | 52 | `pv_not_empty → q1f` (u_DEC) 14 liv |
| **FAST** | **p5+R9** | 41,1 | **92,9** | 4883 | 3288 | 52 | `pv_not_empty → s1_9` (u_DEC) **4 liv** |
| ctrl | p3+R9 | — | **56,4** | — | — | — | = BALANCED |

**Il Donatello deployabile passa da 41 a 92,9 MHz — piu' del doppio — con soli +601 LUT su BALANCED.**
Rispetto al punto di partenza vero dello studio (`don_a1` = 30,4 MHz), e' **×3,05**.

### ✅ L'accoppiamento, confermato in modo netto
`sp_p3r9` (p3+R9) = **56,4**, IDENTICO a `sp_balanced` (p3+R5): con decode a 57, mettere la SNN a 99 non
compra nulla — limita il decode. E' `sp_fast` (p5+R9) a salire, perche' lì ENTRAMBI i pezzi sono >90.
Il principio (comporre pezzi con Fmax vicina) governa i risultati.

### Le previsioni della campagna split (scritte PRIMA)
- `sp_slow` ~30 → ✅ 30,5 · `sp_balanced` ~57 → ✅ 56,4 · `sp_p3r9` ~57 → ✅ 56,4 ·
  **`sp_fast` ~92** (`min(SNN 99, decode ph5 92,9)`) → ✅ **92,920**. Tutte azzeccate.

### ⚠️ Difetto del cancello trovato e corretto in diretta (split)
Il discriminante p5/p6 contava il nome `pr` (registro di `decode_c1`). Nell'architettura split,
`decode_c1`/`decode_c2` sono inlinate come funzioni locali anche in p5 (dove NON sono chiamate) → `pr`
compare nella dichiarazione → falso positivo, bocciava `sp_fast` (p5 corretto). Sostituito con la
**transizione di fase `dph→6`** (in VHDL `16#06#`), che esiste solo se la fase 6 e' nella FSM — provato
in entrambe le direzioni (p5→0, p6→2). Vedi `run_block_a_matrix.sh` → `struct_gate`.

### Perche' 92,9 e' il tetto pratico di questa architettura
Il collo di `sp_fast` e' a **4 livelli logici** dentro `u_DEC` → la SNN (R9=99) non e' piu' il limite.
Per salire oltre servirebbe un decode piu' veloce di `ph5` (92,9 a fasi / 97,8 a pipeline vera): il
margine residuo e' ~5% e richiederebbe la pipeline vera invece della macchina a fasi (§8, studio aperto).

## 8. Studio/ricerca — leve residue (per uso futuro, non per il deploy)

Il muro non e' in nessuno dei due blocchi ma nella loro integrazione, quindi le leve sono di natura
diversa da tutte quelle usate finora:

- **separare le due entita' di sintesi** invece di una chart sola (il probe dimostra che separati vanno
  a 57,7 e 99,2);
- **disaccoppiare il controllo**: registrare il segnale della FSM SNN prima che entri nel datapath del
  decode, cosi' il fanout non attraversa il confine;
- **ridurre il fanout** dei nodi di controllo (Vivado gia' replica i registri da solo — margine ridotto).

⚠️ **Due diagnosi sbagliate di fila su questo muro**, entrambe con una spiegazione tecnica plausibile.
La regola per la terza: nessuna leva si applica prima di un **esperimento che isoli la causa**, e la
previsione va scritta *prima* della misura.

## 9. Leva 2 (decode pipeline / pv-split) — ⛔ NESSUN GUADAGNO, tetto dell'architettura a fasi

Il collo di `sp_fast` (92,9 MHz, 4 liv) non e' aritmetica ne' `decode_c`: e' il **flag di init** che entra
nel datapath del registro d'uscita del primo stadio del decode (`s1_9` = uscita di `decode_a1`).
- **`decInit='pvSplit'`** (isola il flag di `pv`): 92,945 MHz — **invariato**. `pv_not_empty` sparisce
  dal path, ma lo startpoint diventa `started_dec_not_empty` (il flag che protegge gli altri init):
  ho solo SPOSTATO il nome del flag, non tolto il flag dal path. dmax=0.
- **Diagnosi**: qualunque persistente inizializzato con `isempty` genera un flag di init, e HDL Coder ne
  mette uno nel datapath del registro d'uscita di ogni stadio. Il collo e' STRUTTURALE:
  "un registro inizializzato per stadio, col suo flag di init". Non e' *quale* flag.
- **Per superarlo** servirebbe far partire i registri da reset HARDWARE invece che da `isempty` — un
  cambiamento di come HDL Coder emette lo stato, non di codice MATLAB. Fuori portata per ora.

→ **92,9 MHz e' il tetto pratico dell'architettura a fasi.** La pipeline vera (probe `p5`=97,8) darebbe
~5% in piu' ma costa registri di stadio e gira a vuoto 355 clock su 360 (il time-mux alimenta il decode
1 volta ogni ~360 cicli): area sprecata per un margine marginale. Non conviene.

## 10. Leva 3 (normalize come 3a entita', archStyle='split3') — neutro su Fmax, −LUT

NORM | SNN | DEC come tre entita' distinte (probe Fase 0: tre MF con persistent → OK, no dataflow).
Il normalize (4 moltiplicazioni per reciproci a 34 bit = ~14 DSP) esce dalla MF SNN.

| punto | split (2 ent.) | **split3 (3 ent.)** | LUT split→split3 | path critico split3 |
|---|---|---|---|---|
| FAST (p5+R9) | 92,920 | **92,920** | 4883 → 4910 (+27) | `pv_not_empty→s1_9` in u_DEC, 4 liv |
| SLOW (fused+R2) | 30,5 | **30,545** | 4053 → **3705 (−348)** | `pR_idx→pC_fat` in u_SNN, **51 liv** |

**Verdetto: il normalize NON rallentava ne' la SNN ne' il decode.**
- Su FAST il collo e' in u_DEC (invariato): il normalize non era mai nel path critico. +27 LUT (wrapper 3a entita').
- Su SLOW il collo e' **dentro u_SNN** (`pR_idx→pC_fat`, 51 liv = la profondita' aritmetica dello
  stadio-C, non il normalize). La SNN R2 resta a 30,5 anche senza normalize nel datapath: il suo collo
  e' interno. Il normalize era 14 DSP di AREA, non di RITARDO.
- ✅ **Guadagno collaterale reale**: split3 SLOW usa **−348 LUT** (3705 vs 4053). HDL Coder ottimizza
  meglio tre entita' piccole che due; il normalize isolato non trascina piu' area nella SNN.

→ La leva 3 non alza il tetto (92,9 resta), ma e' **gratis o meglio in area** e piu' pulita
architetturalmente (NORM riusabile). Vale come default per l'architettura split.

⚠️ NORM isolata NON ha Fmax registro-registro: e' logica PURAMENTE COMBINATORIA (4 moltiplicazioni +
clamp, zero registri) -> non ha clock ne' path sequenziale proprio. Conferma che il normalize e'
AREA (14 DSP), non un collo temporale.

## 11. Leva 1 (vincolo di sintesi + post-route) — i numeri DEPLOYABILI veri

Tutti i numeri sopra sono sintesi **libera OOC** (ottimistici). Qui: sintesi VINCOLATA al ritardo OOC
del punto + post-route (`synth_point.tcl` con periodo + `impl_point.tcl`, regola WNS<=0). Sono i numeri
su cui si sceglie DAVVERO la configurazione da mettere su silicio.

| tier | config | OOC libera | **post-route** | delta | hold (WHS) | validita' |
|---|---|---|---|---|---|---|
| SLOW | fused+R2 | 30,545 | **29,619** | −3,0% | +0,121 | VALIDA (WNS −1,023) |
| BALANCED | p3+R5 | 56,440 | **56,246** | −0,3% | +0,098 | VALIDA (WNS −0,061) |
| **FAST** | **p5+R9** | 92,920 | **91,291** | −1,8% | +0,098 | VALIDA (WNS −0,192) |

**Il FAST e' ~91 MHz DEPLOYABILI veri** su xc7z020, timing chiuso, hold positivo — non un numero OOC.
Divario OOC→post-route fra −0,3% e −3,0%: i numeri OOC erano onesti. La sintesi VINCOLATA mantiene la
promessa (contrasto col −39% della prima calibrazione IIDM a vincolo LASCO, che era un artefatto).

---

## RIEPILOGO — le tre leve di ricerca (2026-07-22)

| leva | cosa | esito |
|---|---|---|
| **2** decode pipeline / pv-split | isolare il flag di init dal path | ⛔ 92,9 invariato: il collo e' STRUTTURALE (un flag di init per stadio), non aggredibile da codice MATLAB |
| **3** normalize 3a entita' (split3) | NORM \| SNN \| DEC | ➖ Fmax invariata MA −348 LUT su SLOW: il normalize e' AREA (14 DSP combinatori), non ritardo. Piu' pulito, gratis o meglio |
| **1** vincolo + post-route | numeri deployabili | ✅ FAST 91,3 · BALANCED 56,2 · SLOW 29,6 MHz reali, hold positivo. Divario OOC minimo |

**Il tetto pratico del Donatello e' ~91 MHz deployabili** (architettura split, p5+R9). La caccia al FAST
ha portato il blocco da 25,3 (don_a1) a 91,3 MHz reali = **×3,6**, con area confrontabile.

## 12. TABELLA DEFINITIVA — Blocco A split, dataset completo (2026-07-22)

Ogni metrica verificata sull'artefatto, non ereditata. Snapshot SNN congelati, cache azzerata.

| tier | config | dmax | Fmax OOC | Fmax post-route | LUT OOC→route | FF | DSP | BRAM(tile/RAMB18) | WHS | entity |
|---|---|---|---|---|---|---|---|---|---|---|
| SLOW | fused+R2 | **0** | 30,545 | **29,619** | 3681→3645 | 1817 | 52 | 1 / 2 | +0,121 | 2 (SNN,DEC) |
| BALANCED | p3+R5 | **0** | 56,440 | **56,246** | 4282→3891 | 2173 | 52 | 1 / 2 | +0,098 | 2 (SNN,DEC) |
| **FAST** | **p5+R9** | **0** | 92,920 | **91,291** | 4883→4548 | 3288 | 52 | 1 / 2 | +0,098 | 2 (SNN,DEC) |

Note: `dmax=0` su traiettoria reale per la coppia SPECIFICA di ogni tier (gate_split_tiers, non ereditato
dal preflight). Il vincolo di sintesi riduce ANCHE l'area (LUT OOC→route in calo su tutti). BRAM 1 tile /
2 RAMB18 invariata OOC→post-route. Latenze: SLOW 341 (fused, no fasi decode), FAST 405 (p5, 5 fasi).
split3 (leva 3) su SLOW: -348 LUT ulteriori a Fmax invariata.

### ✅ Blocco A: COMPLETO. Deployabile raccomandato = FAST (p5+R9 split) a ~91 MHz reali.
Da 25,3 (don_a1 fused+R9 chart) a 91,3 post-route = **×3,6**, area confrontabile, hold positivo.

---

## NOTA METODOLOGICA per il Blocco B / confronto MPC (fpga-expert ch30)
Le Fmax qui sono timing STATICO (deterministico): la "regola della distribuzione" (mediana/p99/max su
N≥1000) NON si applica. Si applichera' invece al confronto **SNN-FPGA vs MPC-software** del Blocco B:
- **same-window rule**: finestre identiche sui due lati (prep buffer, cache flush, kernel, read-back).
- **baseline difendibile**: MPC-SW compilato -O3 + flag target dichiarati, NON -O0 (errore metodologico noto).
- **jitter del control-loop**: e' l'argomento piu' forte per l'HW dedicato — va MISURATO (p99−mediana) e
  confrontato col jitter-margin del loop, non asserito.
