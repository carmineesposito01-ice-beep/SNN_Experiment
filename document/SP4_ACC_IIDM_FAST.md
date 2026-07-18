# SP4 — ACC-IIDM fast (recuperare l'Fmax)

> ## ✅ SP4 CHIUSO (2026-07-17) — 2,0 → **9,30 MHz**, area **−21%**, **`dmax = 0`**, timing **chiuso** @8 MHz
> Il blocco **`Donatello_ACC_IIDM_M`** (`snn_champions_lib`) è la variante veloce del controllore completo:
> **8614 LUT · 2134 FF · 71 DSP · Fmax 9,30 · WNS +17,4 ns · latenza 358 clk**, bit-identica a SP3.
> *(BRAM non catturato nel run OOC G6 — il numero completo, post-route, si misura in **Fase B2.0**.)*
> `Donatello_ACC_IIDM` (SP3) resta il **riferimento** e non è stato toccato; il **deployato** nemmeno.
> **Il bersaglio 11,65 MHz NON è raggiunto ed è stato dimostrato irraggiungibile** per questa strada
> (probe: tetto 10,58 anche con `tanh` gratis, e il collo esce dall'IIDM → SNN/decode = il deployato).
> Era comunque un criterio di **simmetria con la SNN, non un requisito**: il blocco consuma **358 clock su
> 800.000** per control-step (margine ~2200×).
> Cancelli finali tutti verdi: G7 plant parity · SP3 `dmax=0` · **G2 0/60000** · G3/G4 5/5 traj ·
> G5 su M **e** su SP3 **e** su Champion.
>
> **Ri-verificato 2026-07-17 sulla libreria committata** (non a memoria): il blocco è **aggiornato** (FSM #2a
> a 7 stadi, 1 sola `divide()`), **self-contained** (13 funzioni-fase inlinate come funzioni locali, zero `.m`
> esterni) e **HDL-ready su PC vergine** — `run_block_hdl_gate('Donatello_ACC_IIDM_M')` PASSA con `matlab/` fuori
> dal path: 4 VHDL generati (incl. `DualPortRAM_generic.vhd` = time-mux vero), 0 errori. Il gate è stato reso
> **sensibile anche alle dipendenze di M** (`iidm_*`/`fsm_div`/`acc_types`, commit `ab232fc8`).
>
> ⚠️ **Questi numeri sono OOC + livello Simulink.** SP4 chiude l'**ottimizzazione**; la **prova RTL** — il VHDL
> simulato in xsim vs riferimento sul **dataset intero**, con metriche vere, + utilizzo post-route completo — è la
> **Fase B2.0** (validazione della versione FPGA + report). Vedi `SESSION_RESUME.md` §AZIONE PENDENTE e
> `HDL_PHASE.md` §8.

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

## Studio 2b — timing oltre 9,30: F1 (probe pipelining AUTOMATICO) = FAIL provato (2026-07-18)

> Deciso dall'utente in B2.0: spingere l'Fmax oltre 9,30 **bit-exact**, verso il tetto (fronte `tanh` **10,58**;
> con *anche* SNN→decode **~11,65** = limite SNN — 10,58 è il tetto del solo tanh, non l'assoluto). Approccio
> **probe-first**: prima misurare se HDL Coder pipelina il `tanh` *automaticamente* (bit-exact per costruzione,
> senza toccare il sorgente), poi decidere. Spec/plan: `docs/superpowers/specs/2026-07-18-b2.0-2b-timing-design.md`
> · `docs/superpowers/plans/2026-07-18-b2.0-2b-timing-optimization.md`.

**Esito F1: il `tanh` nativo fixed NON è pipelinabile da alcuno strumento automatico, bit-exact.** Misurato OOC
(xc7z020, clk 8 MHz) sul blocco `Donatello_ACC_IIDM_M`. Il collo è il path `st_dd_12 → thl_7` (**201-207 livelli**),
la nuvola combinatoria del `tanh` (`IIDM_CTRL.vhd` = 984 KB, tutto combinatorio fra quei due registri;
`st_dd_12` sfix19_En8 → `thl_7` sfix19_**En17**, i bit frazionari in più = il "non castare" nativo).

| leva | meccanismo (misurato) | Fmax |
|---|---|---|
| baseline (nessuna pipeline) | collo = tanh, 207 liv | **9,30** |
| HDL Coder `OutputPipeline`+`DistributedPipelining` (N=2,4,8) | i registri finiscono **all'uscita** (`out_0_pipe_reg`, shift-reg *dopo* `IIDM_CTRL`); la barriera **"delays not moved across due to non-zero/unknown initial value"** blocca l'ingresso nella chart-FSM | **9,30** (0%) |
| HDL Coder `ClockRatePipelining` (op4_crp) | idem | **9,30** |
| **Vivado** retiming (`synth_design -retiming`, op4 / 80 ns) | rialloca il *solo* registro `thl` di 6 liv nel bordo del tanh (`thl_7_reg_bret`, 207→201 liv) | **9,52** (+2,4%) |
| **Vivado** retiming (op8 / 40 ns, max pressione) | **identico** a op4: gli 8 registri d'uscita sono bloccati dietro il registro di stato `acc`, irraggiungibili | **9,52** (+2,4%) |

**Perché:** il retiming *sposta* registri, non ne *inserisce*; sul path del tanh c'è un solo registro (`thl`), e la
logica di stato attorno (`acc`, FSM, init non-zero) impedisce di portarne altri dentro — op4 e op8 danno il medesimo
risultato, prova che i registri d'uscita non raggiungono mai il tanh. **Non è un problema di periodo di clock:** il
ritardo del path (~107 ns) è logica reale (201-207 livelli di porte), il periodo decide solo se il timing *passa*.

**Infrastruttura (riusabile):** `matlab/probe_pipe_tanh.m` (genera le varianti VHDL in modelli scratch, commit
`983c4c33`); sintesi OOC via `scripts/synth_acc_iidm.tcl` **da work-dir senza spazi** `D:/zbd_pipe` (⚠️ la tcl con
`glob` su path contenente spazi fallisce — Tcl mangia i separatori backslash; copiare il VHDL in `D:/zbd_pipe/<tag>`
e sintetizzare da lì); `D:/zbd_pipe/retime_test.tcl` per il retiming; numeri grezzi in `matlab/hdl_pipe/RESULTS.txt`
(gitignored). Il baseline attraverso questo flusso riproduce **esatto** il numero SP4 (8614 LUT · 9,297 MHz ·
critpath `st_dd→thl` 207 liv) → flusso fedele.

**→ Esperimenti MANUALI queued (2026-07-19, decisi dall'utente):**
1. **Reimplementare il `tanh` a mano** (§2.1: CORDIC/polinomio/LUT staged in FSM). Rischio §2.1 (cast prematuro,
   costò 82,4% dei control-step su snn_b2_fsm); tetto **fronte-tanh 10,58**; per **11,65** serve *anche* pipelinare
   SNN→decode (secondo fronte, nel core).
2. **Inserire registri a mano nel netlist HDL generato** (pipeline manuale della nuvola `tanh` ai cut-point,
   verificata **bit-exact** con B-1 — è ciò che gli automatismi non riescono a fare ma un umano sì). **Sfumatura di
   regola concordata:** "VHDL mai a mano" protegge il *flusso di generazione*; sui **blocchi generati DEFINITIVI**
   (forma finale del progetto) l'editing manuale è **ammesso se il comportamento è preservato** (dmax=0).

Non-regressione pronta per entrambi: A-1/B-1/PLANT-PAR/B-LOOP (assorbono latenza < HOLD=500, il TB campiona a fine
finestra) + `run_b2_parity_dataset` per il fronte core.

## Studio 2b — Esp. A: reimplementazione del `tanh` (✅ A1 LUT INTEGRATA, 2026-07-18)

> Dopo F1 (pipelining automatico = FAIL), l'utente ha scelto di **reimplementare il `tanh` nel sorgente**.
> Studio comparativo a **5 vie** (spec `docs/…/2026-07-18-b2.0-2b-tanh-reimpl-study-design.md`, piano
> `…-tanh-reimpl-study.md`), a due livelli: **L1** = `tanh` da solo (Fmax intrinseco), **L2** = controllore intero.

**Mappa (L1, xc7z020 @8MHz):**

| variante | dmax_accel | Fmax L1 | liv. | LUT | DSP | note |
|---|---|---|---|---|---|---|
| native (baseline) | 0 | 9,42 | 198 | 2190 | 2 | `tanh` HDL Coder nativo |
| **A1 — LUT piena** | **0** | **136,4** | **8** | **545** | **0** | **bit-exact → DEPLOYATA** |
| A2a — LUT256+interp | 0,0039 | 54,7 | 16 | 187 | 1 | approx; area minima |
| A2b — polinomio g9 | 0,0625 | 10,1 | 88 | 473 | 17 | approx; 17 DSP, lento |
| A2c — CORDIC | 0,0117 | — | — | — | — | approx; HDL non isolabile* |

*CORDIC: richiede una **divisione** (sinh/cosh); il RoundingMethod `'Zero'` obbligatorio per l'HDL rompe il
parse della chart Stateflow → non isolabile come tanh standalone. Architetturalmente il tool sbagliato qui
(reintroduce la divisione che SP4 aveva eliminato). Accuratezza tanh-level misurata (0,0018). (dmax approssimate
su campione 1:3.)

**Verdetto:** **A1 (LUT piena) vince su ogni asse** — unica **bit-exact** (`dmax=0` su 20000 control-step,
`probe_tanh_dmax`), la più veloce (136 MHz, ~14× il nativo → 198→8 livelli), **0 DSP**, e **~4× più piccola**
del nativo (545 vs 2190 LUT). La LUT memoizza il `tanh` fixed nativo su `dd∈[-8,8)` (4096 entry) + 2 costanti di
saturazione; indirizzo = `storedInteger(dd)`, `reinterpretcast` (niente arrotondamento) → bit-identica per
costruzione. Le approssimate non offrono vantaggi. Generatore: `gen_tanh_lut()`.

**✅ A1 integrata** in `Donatello_ACC_IIDM_M` (`iidm_tanh` chiama `tanh_lut_full`, inlinata nel chart da
`build_hdl_variants`; commit `2398d5d6`). **L2 realizzato:**

> **Controllore: 9,30 → 10,58 MHz (+14%), bit-exact, area 8614 → 7249 LUT (−16%), DSP 71 → 69.**
> `RESULT l2final Fmax=10,58 · CRITPATH pR_idx→pv_3, 172 liv = **SNN→decode**` — il `tanh` **non è più il collo**.

Cioè: **il muro del `tanh` è rotto bit-exact, e con meno area.** Il nuovo collo è **SNN→decode** (172 liv), che è
esattamente il tetto ~10,58 previsto dal probe #2c. **→ il prossimo fronte verso 11,65 è la rete (SNN→decode),
nel core.**

**Validazione:** `dmax=0` (20000 accel) + **B-1 ridotto 0/3000** (RTL bit-exact) + HDL gen 0 errori + L2 misurato.
Il **gate esaustivo** (B-1 full 0/60000 · A-1 · PLANT-PAR · B-LOOP · `run_b2_parity_dataset` 0/240000) è
**rinviato** (da eseguire prima del deploy finale / dopo il fronte SNN→decode) — deciso dall'utente perché
l'ottimizzazione non è finita. ⚠️ **Gotcha ambiente:** `bash` risolveva su **WSL** (rotto dopo sospensione) →
gli harness xsim vanno lanciati con **Git Bash in testa al PATH** (`C:\Program Files\Git\bin`); lo script `.sh`
usa già path assoluti ai tool Vivado.

## Studio 2d — timing SNN→decode e pipelining del core SNN (✅ CHIUSO, 2026-07-18)

> **Contesto.** Dopo 2b (A1 tanh-LUT integrata) il controllore era a **10,58 MHz**, collo `pR_idx→pv`
> (readout SNN + decode FUSI, 172 liv). 2d attacca prima il path SNN→decode a livello controllore
> (R1-R2), poi — con margine enorme scoperto dal probe — **pipeline il core SNN** (R3-R9). Tutto
> **bit-exact** (`run_b2_parity_dataset` = **0/60000** ad ogni round; core = mirror di `snn_core`).

**R1-R2 (controllore).** R1 = disaccoppia readout↔decode (il latch `rawl` messo DOPO la catena fasi →
`rawl` diventa un vero registro, decode al ciclo dopo): 10,58 → **14,99 MHz** (+42%). R2 = `reci` (16
prodotti `W.U·t_lr`) da ripple ad **adder-tree** (16→4 profondità): 14,99 → **15,84 MHz**. Bit-exact
(parity 0/60000 · B-1 0/3000). **Il collo LASCIA la SNN** → diventa il **divisore IIDM** (`ql_7`, 170
CARRY4).

**Probe «tetto SNN».** Sintesi standalone `Donatello_Champion` (SNN+decode, NIENTE legge IIDM) +
spettro path del controllore R2 (top-40 per endpoint): il **tetto SNN vero ≈ 29 MHz** (stage-C
`pC_fat/pC_V`), il decode è veloce (fuori dai 40 peggiori), il controllore è cappato **dalla LEGGE
IIDM** — divisore (15,84) + `s_star`/sqrt `st_sab` (17,30). *Headroom 15,84→~29 = tutto nell'IIDM.*
Decisione utente: **esaurire prima la SNN** (verso i 136 MHz provati dal tanh-L1 in 2b), poi l'IIDM.

**R3-R9 (pipelining del core SNN, misurato con un meter forward-only `probe_snn_fwd` = `snn_b2_fsm`→raw
standalone, il cui WNS È il tetto SNN).** Ogni round pipeline un pezzo del compute per-neurone (latenza
+1 ciclo/stadio, **GRATIS nel time-mux**; bit-exact per costruzione = stessa aritmetica, solo
registrata):

| round | leva | Fmax forward | Δ |
|---|---|---|---|
| R2 | (stadio-C in 1 ciclo) | 29,75 | — |
| R3 | split C1(MAC/accumuli) ‖ C2(soglia/update) | 47,94 | +61% |
| R4 | reci-tree a metà (Ca L1-L2 / C1 L3-L4) | 52,15 | +8,8% |
| R5 | `Ii` ad albero (4→2→1) | 62,16 | +19% |
| R6 | stadio MAC (Cm): prodotti reci+Ii registrati | 71,94 | +16% |
| R7 | split C2 (mis-target, staccato il pezzo corto) | 72,91 | +1,3% |
| R8 | split C2a a `Vi` (registro tipo-largo via prototipo) | 91,85 | +26% |
| R9 | split mux `xbuf` ↔ DSP mult (Cx/Cm) | **99,16** | +8% |

Pipeline finale **8 stadi**: `R→Cx→Cm→Ca→C1→C2i→C2a→C2b`. **SNN forward 29,75 → 99,16 MHz (3,33×)**,
tutti bit-exact 0/60000, +1068 FF, DSP/BRAM piatti.

**Il pavimento.** A R9 ogni stadio è **una singola op larga** (add/sub 28-bit o DSP mult, ~7-10ns): il
collo è il sub `nC_V = Vi − sib·eth` (28-bit). Il tanh-L1 fece **136** perché era **1 sola LUT** (niente
aritmetica larga); la SNN è cappata più in basso dai suoi add/mult larghi. **~130 sarebbe raggiungibile**
con 2-3 round di split di singole op (carry-select / precompute-and-register), **ma senza payoff
pratico**: la SNN è già **6,3× il cap IIDM** del controllore, e ogni tetto IIDM futuro (~50-80) sta ben
sotto 99. Decisione utente: **convergere a 99**.

**Chiusura / validazione controllore.** L'SNN 8-stadi è validato NEL blocco deployato
`Donatello_ACC_IIDM_M`: **parity 0/60000** + **B-1 0/3000** (RTL fresco == blocco). Fmax controllore
**15,67 MHz** (INVARIATA: cappata dal divisore IIDM `ql_7`, 63,8ns; −1% vs 15,84 R2 da congestione dei
+1069 FF). Risorse controllore: LUT 7384→8230, FF 2114→3183, DSP 69, BRAM 1 — sta comodo su xc7z020.

**Verdetto 2d.** Il forward SNN è pipelinato a **99 MHz bit-exact e BANCATO**: quando si ottimizzerà
l'IIDM (divisore+sqrt), la rete non sarà più il collo. Curva/dettaglio round in
`matlab/hdl_snn/RESULTS.txt`. Harness: `matlab/run_2d_round.m` (controllore), `matlab/probe_snn_fwd.m`
(meter forward), `matlab/probe_snn_ceiling.m` (Champion). Core: `matlab/snn_b2_fsm.m` (8 stadi).

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
