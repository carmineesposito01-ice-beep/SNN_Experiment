# SP4 — ACC-IIDM fast (recuperare l'Fmax)

> Doc di processo. Spec: `docs/superpowers/specs/2026-07-16-acc-iidm-fast-design.md` · piano
> `docs/superpowers/plans/2026-07-16-acc-iidm-fast.md`.
>
> **Stato (2026-07-17): tre strade chiuse, una rimasta.**
> | strada | esito | perché |
> |---|---|---|
> | **L** — reciproci a LUT | chiusa | errore non convergente ~4 m/s²: **approssima** |
> | **M-v1** — resource sharing (config) | chiusa | 9,5 MHz < 11,65 **e** area esplosa (LUT ×2,4, FF ×14) |
> | **M-FSM #1** — FSM + blocco `Divide` HDL | **chiusa: strada MORTA** | bit-identità **provata** (G1/G2/G3/G4 verdi) ma **non genera VHDL**: il blocco accanto alla chart impone la conversione dataflow, che **vieta `tanh` fixed** → §Variante M-FSM |
> | **#2a** — FSM che riusa **una `divide()`** (chart sola) + stadi | ✅ **FATTA, FUNZIONA, CHIUDE** | **8614 LUT · 2134 FF · Fmax 9,30 · WNS +17,4 · `dmax=0` · G5 verde**: eguaglia M-v1 (9,51) con **1/3 delle LUT e 1/10 dei FF**; vs SP3 Fmax ×4,6 e LUT −21% → §Variante M-FSM #2a |
> | **#2b** — divisore **sequenziale a mano** | ❌ **esclusa dai dati** | la divisione **non compare in nessuno dei due path critici misurati**: né oggi (collo = `tanh`, 207 liv) né col tanh azzerato (collo = **SNN→decode**, 172 liv). Inutile in entrambi gli scenari |
> | **#2c** — `tanh` sequenziale (CORDIC) a mano | ❌ **non perseguita (probe misurato)** | probe con tanh a **costo zero**: tetto **10,58 MHz**, collo che si sposta **fuori dall'IIDM** (SNN→decode = il deployato). #2c varrebbe **≤ +14%** (9,30→10,58) riscrivendo a mano l'aritmetica del tanh (rischio §2.1), **senza arrivare a 11,65** |
>
> Bersaglio invariato: **Fmax ≥ 11,65 MHz** con area ridotta, **`dmax = 0`** (mai approssimare).
> **Stato: 9,30 MHz misurati a `dmax=0`, timing CHIUSO @8 MHz, area in discesa.** Collo finale: **il `tanh`
> fixed** (207 liv) — non la divisione. ~9,3 è il **tetto** di questa architettura a bit-identità intatta; gli
> 11,65 richiederebbero di approssimare il tanh (LUT) o un CORDIC sequenziale a mano (#2c). Nota: 11,65 era
> simmetria con la SNN, non un requisito: il blocco usa **358 clock** su **800.000** per control-step.

## Problema (SP3, misurato)
`Donatello_ACC_IIDM` in fixed sintetizza a **2,0 MHz** (WNS −373 ns @8 MHz, timing non chiude). Path critico
`pR_idx_reg → acc_3_reg`, **1077 livelli logici**, di cui **CARRY4 = 820 (76%)** dai divisori digit-recurrence
combinatori, **incatenati** (`s_star` → `z=s_star/s_safe` → `a_iidm` → `dd`…). Bersaglio: **≥ 11,65 MHz** (pari
alla SNN). Studio A/B: **L (reciproci a LUT) prima, poi M (time-mux)**; si decide sui dati.

## Variante L — reciproci a LUT: COSTRUITA e SCARTATA sui dati
Idea: ogni `1/x` → `sqrt` nativa dove serve + **reciproco a LUT 1-D** (`acc_recip_lut`) + moltiplica; i divisori
sono limitati lontano da zero. Infrastruttura (tutta committata, corretta, riusabile):
- `acc_recip_lut.m` — reciproco 1/x via LUT 1-D + interp (modello `snn_decode_lut`). Provato: costruzione
  corretta (v0/b mostrano la firma 1/N² dell'interpolazione lineare).
- `acc_types.recipN` (0 = `divide()` SP3, >0 = reciproco-LUT) + `acc_div` che sceglie la strategia. **SP3
  invariato** (`run_plant_parity` 0.00e+00, `acciidm_test` dmax=0). Review-catch: il divisore **costante** `DT`
  resta `divide()` (guardia `nargin>=6`).
- `acc_sweep_kernel` + `build_acc_sweep_mex` — kernel MEXato (1 MEX per `recipN`): lo sweep passa da **~6 h a
  12 s**, bit-identico all'interpretato (max|diff|=0).

### Il verdetto (sweep sul dataset intero, 60 traj)
| N | E_L p99 | E_L max | passa (budget p99<0.272, max<1.484) |
|---|---|---|---|
| 16 | 1.51 | 3.77 | no |
| 32 | 0.79 | 4.09 | no |
| 64 | 0.59 | 4.09 | no |
| 128 | 0.61 | 4.14 | no |
| 256 | 0.64 | 4.14 | no |

**Nessuna N rispetta il budget.** E — più importante — **l'errore NON converge con N**: il p99 tocca il fondo a
~0.59 (N=64) e poi *peggiora*, il max resta **piatto a ~4 m/s²**. Un errore di sola risoluzione LUT scenderebbe
~16× da N=32 a N=256; qui è piatto → errore **strutturale, N-indipendente**.

### Causa: saturazione ESCLUSA, root-cause non stabilita
Sospetto iniziale = saturazione di range (firma tipica del max piatto). **Verificato e smentito** (range reali sul
dataset):

| divisore | LUT [lo,hi] | reale [min,max] | satura |
|---|---|---|---|
| 2·sab | [1.74, 2.64] | [1.740, **2.646**] | sì, **0.006** (0.2%, baco reale ma innocuo) |
| v0 | [8, 45] | [24.4, 32.0] | no |
| b | [0.5, 3] | [1.19, 2.05] | no |
| s_safe | [2, 150] | [2, 150] | no |

La micro-saturazione di `2·sab` (allargare la LUT a `[1.74, 2.65]`) **non spiega** 4 m/s². Root-cause non
stabilita: o un baco fixed-point nel reciproco-per-moltiplica, o l'**amplificazione intrinseca** — l'errore di
`1/s_safe` vicino a `s_safe=2` (dove `1/x` è più curvo) moltiplicato per `s_star` (fino a 465) → `z` → `z²` →
`a_z`. Non è stata inseguita oltre: la decisione non ne dipende (vedi sotto).

## Decisione: → M (time-mux dell'IIDM)
Presa sui dati (era il piano: «se nessuna N passa → è il dato che motiva M»). Argomento che va **oltre**
bug-vs-fondamentale: un **reciproco approssimato che alimenta un'amplificazione `z²` è fragile per costruzione**.
**M — divisione sequenziale ESATTA — è bit-identica** all'IIDM fixed di SP3 (`dmax=0`, zero errore
d'approssimazione) e **scavalca l'intera classe di problema** (niente LUT, niente amplificazione, niente range).
È anche la variante preferita dall'utente.

**Cosa L insegna a M:** le 5 divisioni vanno **sequenziate**, non approssimate. Il time-mux dell'IIDM
(~341 clock/control-step disponibili) spezza la catena combinatoria mantenendo la matematica esatta.

## Variante M — time-mux (divisore condiviso): ESEGUITA (make-or-break) → config non basta → FSM
Spec `docs/superpowers/specs/2026-07-16-acc-iidm-timemux-design.md` · piano
`docs/superpowers/plans/2026-07-16-acc-iidm-timemux.md`. Meccanismo deciso **da verifica** (non assunto):
**resource sharing di HDL Coder PRIMA**, FSM esplicita in fallback. **Task 1 (make-or-break) eseguito il
2026-07-16** (`probe_acciidm_sharing.m`, commit `6db20b0a`; 3 config generate + sintesi OOC su xc7z020 @8 MHz).

### Struttura reale (verificata)
Le 5 `divide()` stanno **dentro** la MATLAB Function `SNN_ACC` (`acc_iidm_open` inlinato). Il resource sharing va
quindi sul **blocco MATLAB Function interno** (non sul subsystem esterno) e il blocco copiato va **slinkato** dalla
libreria (`LinkStatus=none`), o `hdlset_param` fallisce per un artefatto → **falso "config non basta"**. (Il
codice-esempio del piano, sul subsystem esterno + link intatto, avrebbe dato un falso negativo — corretto nel probe.)

### Verdetto OOC (xc7z020 @8 MHz)
| config | LUT | FF | DSP | WNS | Fmax | path critico | livelli |
|---|---|---|---|---|---|---|---|
| baseline (=SP3) | 10 846 | 1 653 | 69 | −373 ns | **2,01 MHz** | 5 divisioni incatenate (`acc_3`) | 1077 |
| share5_cp (SF5, CRP on) | 25 557 | 22 922 | 38 | +19,9 ns | **9,51 MHz** | **1 divisione** (`quotient_tmp`) | 172 |
| share5 (SF5, CRP off) | 25 622 | 22 981 | 38 | +17,7 ns | 9,32 MHz | 1 divisione | 176 |

- `baseline` **riproduce SP3 al bit** (10846 LUT, 69 DSP, −373 ns, 1077 liv) → flusso coerente, controllo passato.
- Il resource sharing **si attiva davvero**: clock 5× (`DUT_tc`) + moltiplicatori condivisi + **le 5 divisioni
  incatenate sequenziate in UNA** (`u_multiplier_5/quotient_tmp`). Timing **chiude @8 MHz** (era −373 ns), livelli
  **1077 → 172**, DSP **69 → 38**.
- **MA due verità scomode:** (1) **Fmax 9,5 < 11,65 MHz** — il collo è ora la **singola divisione digit-recurrence**
  (172 liv, non pipelinata internamente); (2) **area ESPLOSA**: LUT **×2,36**, FF **×13,9** (il clock-rate pipelining
  replica registri) → **contro la visione "taglia le risorse"**. Solo i DSP calano.

### Decisione: → FSM esplicita (piano a sé)
Il config-based, anche spinto a 11,65 (pipelinando la divisione), resterebbe **caro in area** → fallisce metà
obiettivo. Scelta utente (2026-07-16): **FSM esplicita** — divisore sequenziale a mano + macchina a stati che lo
riusa sulle 5 divisioni, **bit-identica a SP3** (`dmax=0`), **Fmax alto CON area ridotta**. È un **piano a sé**
(nuovo ciclo brainstorming→spec→piano), non improvvisato qui. Il diagnostico `probe_acciidm_sharing.m` resta
committato e riusabile. Stato corrente sempre in `document/SESSION_RESUME.md` (blocco ▶).

## Variante M-FSM — FSM + blocco Divide HDL: ESEGUITA (2026-07-17) → **strada MORTA** (`tanh` fixed)
Spec `docs/superpowers/specs/2026-07-16-acc-iidm-fsm-design.md` · piano
`docs/superpowers/plans/2026-07-16-acc-iidm-fsm.md`. Approccio **#1** approvato dall'utente: una FSM che riusa
**1 solo blocco `HDLMathLib/Divide`** (ShiftAdd, pipelinato) per le 5 divisioni — invece di un divisore
scritto a mano (#2) — per avere la bit-identità **by construction** anziché doverla guadagnare.

### Cosa è stato PROVATO (tutto verde, tutto sul dataset, tutti i cancelli sensibili)
| gate | esito | note |
|---|---|---|
| **G1** blocco `Divide` == `divide()`-SP3 | **dmax=0 su 300.000 coppie reali** | ShiftAdd + RndMeth 'Zero' + OutType Q10.8. Sensibile: 'Nearest' → dmax 1 LSB |
| **G2** model FSM == `acc_iidm_open` | **dmax=0 su 60.000/60.000 control-step** | Sensibile: q2 al posto di q3 → dmax 3,13 su 1990/2000 |
| **G3/G4** blocco M == model == SP3 | **dmax=0 su 5/5 traiettorie** | latenza **misurata** 509 clk (341 SNN + 5 divisioni); edge-triggered |
| plant parity | ALL PASS | il riferimento double non si è mosso |

`Donatello_ACC_IIDM_M` **esiste, compila e simula bit-identico a SP3 con UN SOLO divisore**. Ma **non genera
VHDL** — e non per un bug da tappare.

### Perché la strada è morta
```
serve un divisore pipelinato riusabile
 -> in HDL Coder esiste SOLO come blocco (HDLMathLib/Divide), non come funzione chiamabile dalla chart
 -> il blocco CONVIVE con la chart nello stesso subsystem
 -> HDL Coder impone la conversione MATLAB-to-dataflow (ottimizza attraverso il confine chart<->blocchi)
 -> quel flusso VIETA tanh in fixed-point ("Provide a floating-point input")
 -> ma tanh e' nel cuore dell'IIDM:  a_blend = (1-COOL)*a_iidm + COOL*(a_cah + bf*tanh(dd))
 -> aggirarla = LUT o float = APPROSSIMARE = dmax != 0
 -> ma "non approssimare" E' la ragione per cui M esiste (ed e' il motivo per cui L fu scartata)
```
Il design #1 è **incompatibile con questa matematica**, punto.

### Le prove (misurate, non inferite)
- **La causa è la CONVIVENZA, non il core:** la STESSA chart, messa **da sola** in un subsystem (soli
  Inport/Outport), genera VHDL con **0 errori**; col `Divide` accanto, fallisce. (Il primo tentativo di questo
  test fallì per un errore del *mio harness* — tipi delle porte — e NON è stato scambiato per un verdetto.)
- **Non è l'architettura del blocco:** `hdlget_param(chart,'Architecture')` = `MATLAB Function` (default del
  fixed-point) **già applicato e verificato**, e la conversione avveniva lo stesso → non si disattiva da lì.
- **`snn_types` non era il problema:** portarlo a `fi(0)` risolve l'errore "empty-typed" — e **subito dopo
  emerge `tanh`**. Il core è stato **ripristinato**: non si tocca senza una ragione viva. (37 file lo usano,
  inclusi i top HDL del **deployato**.)
- I 4 vincoli dataflow incontrati (struct empty-typed · `persistent` in non-entry-point · `divide()` con
  argomenti variabili · **`tanh` fixed**) e la regola generale sono in **`document/HDL_PHASE.md` §9**:
  valgono **oltre** SP4, per qualunque blocco futuro che debba restare bit-exact.

### Cosa RESTA VALIDO (nulla di sostanziale è perso)
- **G1**: il blocco `Divide` **è** bit-esatto a `divide()` (300k coppie). Riusabile il giorno che servisse un
  divisore pipelinato in un contesto **senza** chart bit-exact accanto.
- **Le funzioni-fase** (`iidm_prep`/`iidm_nd`/`iidm_use`/`iidm_final`/`fsm_div`) = single-source della
  matematica in forma FSM, **validate da G2 su 60.000 control-step**. La strada #2 le riusa **identiche**:
  cambia solo *chi* fa la divisione.
- **Model** `acc_iidm_fsm`, **G2**, **G3/G4** (`run_block_acciidm_m_test`), l'architettura FSM q1→q5,
  l'handshake, la latenza misurata: tutto riusabile.
- **L'infrastruttura di verifica**, che prova la bit-identità di **qualunque** divisore (anche quello a mano
  di #2): `collect_div_pairs` + `probe_divide_bitexact` (300k coppie in **44s**) e `run_acciidm_m_dataset`
  (60k control-step in ~12 min).
- **Ottimizzazione dei cancelli** (senza ridurre il campione, regola del progetto): collect da **~47 min a
  ~10 min** (MEX; i wrapper `collect_step`/`fsm_step` costruiscono `acc_types` dentro → il ramo
  reciproco-LUT di L non viene compilato); probe da **~23 min a 44s** (ingresso **vettoriale** + Divide
  combinatorio `latencyMode='Zero'`, bit-identico al pipelinato).
- Modifiche collaterali **provate neutre e tenute**: `acc_types` con prototipi `fi(0)`; stato del filtro OU
  nel top-level; divisione per la costante `DT` come `x*(1/DT)` (**G2 lo prova**: dmax=0).

### Prossimo: approccio #2 (l'unico rimasto)
**Divisore digit-recurrence DENTRO la chart**, sequenziato dalla FSM: niente blocco esterno → niente
convivenza → niente conversione dataflow → `tanh` fixed torna nativa (come in SP3) e il core resta intatto.
Prezzo: la bit-identità del divisore va **guadagnata** (era ciò che #1 comprava) — ma l'infrastruttura per
provarla su 300k coppie reali è già in piedi. Richiede un nuovo ciclo `brainstorming → spec → piano`.

## Variante M-FSM #2a — FSM che riusa UNA `divide()`: FATTA (2026-07-17) — **funziona**
Spec `docs/superpowers/specs/2026-07-17-acc-iidm-fsm-2a-design.md` · piano
`docs/superpowers/plans/2026-07-17-acc-iidm-fsm-2a.md`. Dopo la morte di #1 (blocco `Divide` accanto alla
chart → dataflow → niente `tanh` fixed), il divisore condiviso è stato portato **dentro** la chart: **UNA
sola chiamata a `fsm_div` nel sorgente**, dentro uno stato della FSM → HDL Coder genera **un divisore**,
riusato in 5 cicli. Il blocco è tornato **sola chart** (4 in / 1 out come SP3): niente blocco esterno, niente
handshake, niente Unit Delay, niente loop algebrico → **`tanh` fixed nativa e il VHDL si genera (G5 verde)**.

### I numeri (OOC xc7z020 @8 MHz, tutti misurati)
| | LUT | FF | DSP | **Fmax** | livelli | WNS |
|---|---|---|---|---|---|---|
| SP3 (5 divisori incatenati) | 10846 | 1653 | 69 | 2,01 | 1077 | −373 ns ❌ |
| M-v1 config (resource sharing) | 25557 | 22922 | 38 | 9,51 | 172 | +19,9 ns ✅ |
| #2a **v1** (tutto in un ciclo) | 8564 | 1919 | 71 | 2,85 | 701 | −225 ns ❌ |
| #2a **a stadi** (uno stadio per ciclo) | 8658 | 2158 | 71 | 7,35 | 237 | −11,1 ns ❌ |
| **#2a + stadio TANH** ← **FINALE** | **8614** | **2134** | 71 | **9,30** | **207** | **+17,4 ns ✅** |

**#2a EGUAGLIA M-v1 (9,30 vs 9,51: −2%) con UN TERZO delle LUT e UN DECIMO dei FF, a `dmax = 0`, e il timing
CHIUDE @8 MHz.** Contro SP3: Fmax **×4,6**, LUT **−21%**, e da "non chiude" (−373 ns) a **chiude** (+17,4 ns).
Il time-mux della FSM taglia l'area *davvero*, dove il config-based la gonfiava (LUT ×2,36, FF ×13,9).

### Le due lezioni, misurate
1. **Il time-mux della FSM taglia l'AREA; l'Fmax la dà il REGISTRO fra gli stadi.** La prima versione faceva
   decode+prep in un ciclo e nd+div+use in un altro → **701 livelli, 2,85 MHz**. Spezzata in **uno stadio per
   ciclo** (`DECODE | PREP | ND | DIV | USE | FINAL`, con latch di `raw`) → **237 livelli, 7,35 MHz** a parità
   di area (8564 → 8658 LUT, +239 FF). ⚠️ La stima iniziale "~9,5 MHz perché il path è una divisione" era
   **sbagliata**: quei 172 livelli di M-v1 erano il frutto del clock-rate pipelining (i registri che gli
   costavano FF ×13,9), non della sola condivisione.
2. **L'assunto "1 chiamata nel sorgente = 1 divisore in HDL" regge** (lo dice l'area: −20% vs SP3, −66% vs
   M-v1 a Fmax comparabile), ma **da solo non basta**: senza registri fra gli stadi il path resta lungo.

### Verifica (invariata, tutta verde)
`dmax = 0` vs model **e** vs SP3 su **5/5 traiettorie** (G3) · **G2 `0/60000` control-step** · latenza
**MISURATA 357 clk** (341 SNN + latch + decode + prep + 5×3), edge-triggered · **G5 PASSATO**
(self-contained, `DualPortRAM` presente) · plant parity ALL PASS. Le funzioni-fase non sono state toccate.

### Il tetto, misurato: **11,65 non è raggiungibile per questa strada**
**Probe #2c (2026-07-17)**: sostituito il `tanh` con il solo tipo (valore volutamente sbagliato, ripristinato
subito) per misurare quanto varrebbe toglierlo del tutto:
```
RESULT probe_no_tanh  LUT=6643  FF=2119  WNS=+30.5  Fmax=10.58
CRITPATH pR_idx_reg -> pv_3_reg   172 livelli        <- SNN readout -> decode LUT-64
```
Due conclusioni, entrambe sui dati:
1. **Anche con un `tanh` a costo zero il tetto è 10,58 MHz**, non 11,65. Un CORDIC reale costerebbe di più →
   **#2c vale al massimo +14%** (9,30 → 10,58), al prezzo di riscrivere a mano l'aritmetica del `tanh`
   (rischio §2.1 in prima persona, e senza un blocco `HDLMathLib` da cui copiare: c'è `Sin`/`Cos`/`Sqrt`/
   `Divide`/`Reciprocal`, **non `tanh`**). **Non perseguito.**
2. **Il collo successivo esce dall'IIDM**: è `SNN readout → decode LUT-64`. Andare oltre richiederebbe di
   toccare **la SNN e il decode, cioè il deployato** — fuori discussione in SP4.
⚠️ Corregge anche una **stima sbagliata** fatta prima del probe ("il collo dopo il tanh sarà la divisione,
~11,2 MHz"): i 172 livelli **non sono il divisore**, sono SNN→decode. Per questo **#2b è esclusa in entrambi
gli scenari**, non solo rimandata: la divisione non compare in nessuno dei path critici misurati.

### Il collo di #2a: il `tanh`
```
CRITPATH: st_dd_12_reg -> thl_7_reg   207 livelli      <- e' lo stadio TANH stesso
```
Dopo aver isolato il `tanh` in uno stadio suo, il path critico **è il `tanh` in sé** (207 livelli): non
`iidm_final`, e **non la divisione** (~172). Conseguenza diretta e importante:

> **#2b (divisore sequenziale a mano) non darebbe nulla ADESSO**: serviva ad accorciare la divisione, che
> **oggi non è il collo** (172 < 207). Ma **NON è cassata**: è **rimandata**. Se #2c abbassa il `tanh`, il collo
> diventa **proprio la divisione**, e #2b torna necessaria.
> **Stima della scala** (dal path misurato: 207 liv = 107,5 ns → ~0,52 ns/livello):
> | scenario | collo | delay stimato | Fmax stimata |
> |---|---|---|---|
> | oggi | `tanh` 207 liv | 107,5 ns | **9,30** (misurato) |
> | dopo #2c | divisione ~172 liv | ~89 ns | **~11,2** |
> | dopo #2c + #2b | il prossimo (ignoto) | — | > 11,65? |
> ⚠️ Quindi **#2c da sola non basta** per 11,65: servono **#2c poi #2b**. (Stima grezza: i livelli logici non
> sono omogenei — vale come ordine di grandezza, non come predizione.)

Per superare i **9,30 MHz** bisognerebbe attaccare il `tanh`, e le strade sono tutte chiuse o costose:
| strada per il tanh | esito |
|---|---|
| pipelinarlo con un **blocco HDL esterno** | rimette un blocco accanto alla chart → **conversione dataflow → `tanh` fixed vietata**: è esattamente ciò che ha ucciso #1 |
| **LUT** per il tanh | **approssima** → `dmax ≠ 0` → è il motivo per cui L fu scartata e M esiste |
| **CORDIC sequenziale a mano** dentro la chart (#2c) | l'unica praticabile a `dmax=0`, ma: bit-identità del tanh **da guadagnare** + lavoro, per +25% di Fmax **funzionalmente irrilevante** (vedi sotto) |

**Lettura: ~9,3 MHz è il tetto di questa architettura a bit-identità intatta.** E il bersaglio 11,65 (= Fmax
della SNN sola) era un criterio di *simmetria*, non un requisito funzionale: un control-step dura **0,1 s =
800.000 clock a 8 MHz**, e il blocco M ne consuma **358**. A 9,3 MHz il margine è ~2200×.

## File (variante L, committati — riusabili se L verrà ripresa)
`acc_recip_lut.m` · `acc_sweep_kernel.m` · `build_acc_sweep_mex.m` · `run_acc_recip_sweep.m` · `acc_types.recipN`
+ `acc_div` in `acc_iidm_open.m`. Commit `457aa6c4`…`e2cb8062`.
