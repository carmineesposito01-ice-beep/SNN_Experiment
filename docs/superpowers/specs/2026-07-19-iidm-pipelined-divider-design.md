# Studio IIDM — divisore SEQUENZIALE digit-recurrence in-chart (SP4 #2) + pipelining della legge di controllo (design)

**Data:** 2026-07-19
**Branch/worktree:** `Simulink_Importer`
**Stato:** design REVISIONATO 2026-07-19 dopo la smentita di #1 (box sotto) — strada = **#2**
**Contesto:** chiuso lo Studio 2d (SNN forward pipelinata a **99,16 MHz** bit-exact, *bancata*), il controllore
`Donatello_ACC_IIDM_M` resta a **15,67 MHz** perché cappato dalla **LEGGE IIDM**, non più dalla rete.

---

## 1. Obiettivo

Alzare l'`Fmax` OOC del controllore **il più in alto possibile**, **bit-exact** (`dmax = 0`), pipelinando la
legge IIDM. Nessun target fisso: si scopre il tetto, con lo stesso ciclo **probe-first iterativo** che ha
funzionato in 2d (attacca il collo → ri-misura → ripeti).

## 2. Da dove si parte (misurato)

Spettro dei path del controllore (top-40 per endpoint, sintesi OOC xc7z020 @8 MHz):

| tier | endpoint | Fmax | struttura |
|---|---|---|---|
| 1 | `ql_7` | **15,67–15,84** | **divisore IIDM** (combinatorio) ← collo |
| 2 | `st_sab` | 17,30 → 24,58 | **s_star / sqrt(a·b)** ← 2ª struttura IIDM |
| 3 | `pC_fat` / `pC_V` | ~29 → oggi **99** | SNN (pipelinata in 2d, non più il collo) |

Il divisore è **UNO solo** e già condiviso: SP4 (M-FSM #2a) ha serializzato le 5 divisioni su una sola
`divide()` **dentro** la chart. Ma quella `divide()` è **combinatoria** (~170 CARRY4, tutti i ~26 bit di
quoziente in un ciclo): è lei il collo. Manca la pipeline **interna** al divisore.

## 3. La leva, e perché ORA è disponibile

**Il divisore pipelinato in HDL Coder esiste SOLO come blocco** (`HDLMathLib/Divide`), non come funzione
chiamabile dalla chart. SP4 lo aveva integrato (**#1**, handshake chart↔blocco) e **G1 aveva PROVATO la
bit-identità** a `divide()`-SP3 su **300.000 coppie reali**. Ma #1 **morì**: il blocco accanto alla chart
impone la conversione **MATLAB-to-dataflow**, che **vietava `tanh` fixed** — e il `tanh` era nel cuore
dell'IIDM; aggirarlo significava approssimare (`dmax ≠ 0`), cioè rinunciare alla ragione stessa di M.

**Cosa è cambiato:** lo Studio 2b (**A1**) ha sostituito quel `tanh` con una **LUT bit-exact** (memoizza i
valori esatti, `dmax = 0`). Il divieto del dataflow non ha più oggetto.

> ## ⛔ SMENTITO DAI FATTI (2026-07-19) — #1 RESTA MORTA. Leggere questo prima del resto.
>
> Il probe `probe_iidm_divblock` diede **VERDE, ma era un FALSO VERDE**, e l'integrazione reale l'ha
> smentito. Cronaca onesta, perché l'errore è metodologico e vale oltre questo studio:
>
> **Il probe misurava la cosa sbagliata.** Ci avevo cablato il blocco `Divide` su *inport separati*
> (per semplicità): chart e blocco **coesistevano** ma non si scambiavano dati. La conversione
> MATLAB-to-dataflow scatta sulla **RELAZIONE DI DATO**, non sulla presenza del blocco → nel probe non
> scattava affatto, e il VHDL usciva pulito. Il probe era **strutturalmente incapace** di riprodurre il
> fallimento di SP4: la sua luce verde non conteneva informazione.
>
> **Cosa dice l'integrazione VERA** (handshake reale, `rtl_gen_dut`): **24 errori** di HDL check, sia in
> **Verilog sia in VHDL** (isolato apposta → la causa è la CONNESSIONE, non il linguaggio):
> ```
> Struct in expression 'Tt' / 'T' has an empty-typed field   [snn_types / acc_types]
> The persistent variable 'st' has the type 'struct'          [stato IIDM]
> Persistent 'xprev' / 'vlp' initialized with non-constant value
> ```
> **A1 aveva rimosso UNO dei blocchi (il `tanh`); gli altri quattro sono ARCHITETTURALI** — i prototipi
> `fi([],…)` di `snn_types`/`acc_types` (usati da ~37 file, **incluso il deployato**) e lo struct di stato
> persistente. Rimuoverli = toccare il sistema di tipi del progetto per compiacere un vincolo del tool.
>
> **Nota importante:** i cancelli funzionali erano VERDI (G3/G4 `dmax=0`, parity 0/60000): la matematica
> dell'handshake è corretta. Fallisce **solo** la generazione HDL. Nessun cancello *funzionale* poteva
> vederlo: l'unico gate competente è la generazione stessa.
>
> **Stato del repo:** integrazione #1 **revertita** e ripristino **verificato** (HDL check 0 errori,
> Verilog 3 file, latenza 419, G3/G4 `dmax=0`).
>
> **→ Vale la conclusione ORIGINALE di SP4: l'unica strada è #2**, il divisore digit-recurrence scritto
> **a mano dentro la chart** (niente blocco esterno ⇒ niente dataflow). Il beneficio è identico (un
> divisore sequenziale ha path combinatorio corto); cambia che la **bit-identità va GUADAGNATA** invece
> che comprata da G1 — con l'infrastruttura che però esiste già (`collect_div_pairs` + probe su 300k coppie).

~~**Verificato, non assunto** (probe `probe_iidm_divblock`, 2026-07-18/19):~~ *(sezione superata dal box sopra)*

| domanda | esito del probe (FALSO VERDE) | realtà misurata |
|---|---|---|
| il dataflow genera VHDL con blocco `Divide` accanto alla chart? | ✅ sì (0 errori, 6 VHDL) | ❌ **24 errori** con handshake reale |
| …col blocco **PIPELINATO** (`latencyMode='Max'`)? | ✅ sì | ❌ idem (e anche in VHDL) |
| i `persistent` della SNN 8-stadi bloccano il dataflow? | ✅ no | ⚠️ non erano loro: sono `st`/`xprev`/`vlp` + gli struct empty-typed |

> **Perché NON la strada approssimata.** La Variante L (reciproco-LUT) è già stata **scartata sui dati**:
> l'errore non converge con N (p99 ~0,59 al minimo, max **piatto a ~4 m/s²**) → errore *strutturale*, non di
> risoluzione: un reciproco approssimato che alimenta l'amplificazione `z²` è fragile per costruzione.
> Confermato dalla teoria (fpga-expert ch02): **digit-recurrence** (restoring/non-restoring/SRT) rende 1 bit
> di quoziente per ciclo **con resto esatto** → bit-exact; i metodi *moltiplicativi* (Newton-Raphson,
> Goldschmidt) convergono con moltiplicazioni ma **non danno resto** → approssimati. Solo digit-recurrence.

## 4. Approccio — #2, con i DUE RISCHI SEPARATI

Il divisore sequenziale porta due rischi indipendenti. Affrontarli insieme è ciò che ha reso costoso
l'errore di #1, quindi si separano e ognuno ha il suo cancello:

**Round 1a — l'ALGORITMO (make-or-break, ZERO chirurgia sulla chart).** Scrivere la ricorrenza come
**funzione MATLAB pura** (`div_seq.m`) e provarla **bit-identica** a `divide(numerictype(T.acc),num,den)`
su **300.000 coppie reali** (`collect_div_pairs`) + prova di **sensibilità**. Se l'algoritmo non è
bit-exact, la strada muore qui — senza aver toccato una riga della chart.

**Round 1b — lo STAGING (solo se 1a è verde).** Trasformare la funzione in **stato della FSM**: lo stadio
DIV diventa multi-ciclo (1 bit di quoziente per ciclo), esattamente la forma di lavoro dei round 2d
(R3-R9). Cancelli: G3/G4 + parity + B-1. La latenza cresce (~1 ciclo/bit × 5 divisioni) ed è **gratis**
(800.000 clock/control-step), ma va **misurata** e propagata nell'`hold`.

**Round 2+ — probe-first iterativo (identico a 2d).** Ri-sintesi → si legge il **nuovo** collo dal
`critpath.rpt` → leva che calza → ri-misura. Atteso che salti su **`st_sab`** (s_star/sqrt, 17,30); leve
candidate lì: sqrt sequenziale digit-recurrence, **CORDIC iperbolico** (shift-add, ~1 bit/iterazione,
fpga-expert ch09), o staging FSM. **Non si decide a tavolino: si misura.**

## 5. Il divisore — semantica da replicare e algoritmo

**Il bersaglio, esatto.** `fsm_div` è `divide(numerictype(T.acc), num, den)` con la fimath di `acc_types`:
`T.acc` = **`fixdt(1,19,8)`** (Q10.8: 1 segno + 10 interi + 8 frazionari), **`RoundingMethod = 'Zero'`**
(troncamento **verso lo zero**, l'unica che HDL Coder genera per signed — SP3 §2).

**Scalatura.** Con `num = N·2⁻⁸` e `den = D·2⁻⁸` (N, D = interi memorizzati a 19 bit), il quoziente in
Q10.8 vale `q_stored = trunc₀((N ≪ 8) / D)`: i `2⁻⁸` si elidono e restano 8 bit di scalatura sul
dividendo → **dividendo a 27 bit**, divisore a 19.

**Algoritmo: restoring digit-recurrence sulle MAGNITUDINI, segno applicato alla fine.**
```
sq = sign(N) XOR sign(D)
A  = |N| << 8        (27 bit)      B = |D|      (19 bit)
R  = 0 ; Q = 0
per i = MSB..0:                    # 1 bit di quoziente per ciclo
    R = (R << 1) | bit_i(A)
    se R >= B:  R = R - B ;  Q |= (1 << i)
q = sq ? -Q : +Q                   # poi saturazione al range di T.acc
```
Perché è **esattamente** `RoundingMethod='Zero'`: dividere le magnitudini e applicare il segno alla fine
**tronca verso lo zero per costruzione** — non è un'approssimazione della semantica, è la semantica.

**⚠️ Dove i divisori scritti a mano rompono la bit-exactness: i SEGNI** (e i casi limite: `den` negativo,
`num` = minimo rappresentabile, overflow del quoziente → saturazione). Non i positivi. Il cancello è
costruito apposta per vederlo: le 300k coppie sono **reali**, prese dal dataset, quindi contengono i segni
e i valori estremi che il controllore produce davvero.

**Staging.** `kdiv` è già STATO nella FSM (non indice di loop: un `for` verrebbe srotolato → 5 divisori).
Si aggiunge un **contatore di bit**: lo stadio DIV itera la ricorrenza un bit per ciclo e avanza a USE
quando il contatore è esaurito. Nessun blocco esterno ⇒ **nessuna conversione dataflow** ⇒ `snn_types`,
`acc_types` e lo struct `st` restano **intatti** (è il punto per cui #2 esiste).

## 6. Cancelli (bit-exact, ad ogni round) — tutti già esistenti

| cancello | cosa prova | costo |
|---|---|---|
| **G1** `probe_divide_bitexact` | blocco `Divide` ≡ `divide()`-SP3, 300k coppie, per **quella** config | 44 s |
| **G2** `run_acciidm_m_dataset` | model FSM ≡ `acc_iidm_open`, `dmax=0` su **60.000** control-step | ~12 min |
| **G3/G4** `run_block_acciidm_m_test` | blocco ≡ model ≡ SP3 (`dmax=0`) + **latenza misurata** | rapido |
| **parity** `run_b2_parity_dataset` | SNN forward invariata (0/60000) | ~5 min |
| **B-1** `run_rtl_validate_b` | **RTL** ≡ blocco (xsim, 0/3000) | ~5 min |
| **OOC** `synth_acc_iidm.tcl` | `Fmax` + `critpath` + **area** (LUT/FF/DSP/BRAM) | ~7 min |

⚠️ **Ambiente:** gli harness xsim vanno lanciati con **Git Bash in testa al PATH** (`bash` risolve su WSL,
rotto dopo sospensione) — vedi `SP4 §Studio 2b`.

## 7. Rischi

1. **Handshake e latenza.** La FSM deve attendere *davvero* `vout`: uno slittamento consuma un quoziente
   sbagliato → `dmax ≠ 0`. Lo prendono **G2/G3/B-1**. La latenza cumulativa va **misurata** (G4) e propagata:
   SP4 misurò **509 clk** per #2a (341 SNN + 5 divisioni), ma è un dato **pre-2d** — la SNN 8-stadi ha aggiunto
   stadi e **la latenza attuale NON è stata ri-misurata**. Gli harness usano `HOLD = 500`: va **misurata con G4
   e l'HOLD alzato se serve** (il divisore pipelinato ne aggiunge altra). Da verificare, non da assumere.
2. **Area.** La Variante M *config-based* (resource sharing) fece esplodere l'area (**LUT ×2,36, FF ×13,9**):
   qui l'handshake è **governato a mano**, quindi l'area dovrebbe restare modesta — ma si **misura**, non si
   assume. Se esplode, è un dato che pesa sulla decisione (xc7z020: 53k LUT, 106k FF).
3. **Altri vincoli dataflow (§9).** Il `tanh` è risolto e i `persistent` 8-stadi sono provati innocui, ma la
   ristrutturazione della FSM può toccarne altri (struct empty-typed, `persistent` in non-entry-point,
   `divide()` ad argomenti variabili). Si legge l'errore e si adatta.
4. **Il collo può NON spostarsi dove atteso.** In 2d è saltato due volte in posti non previsti (Ii, poi il
   sub `nC_V`). Perciò: **ri-leggere il `critpath.rpt` ogni round**, mai dedurre.

## 8. Criteri di successo

- `Fmax` del controllore **misurata in salita** da 15,67, con **tutti i cancelli verdi** (`dmax=0`).
- Curva `Fmax`(round) + collo identificato ad ogni giro (come `matlab/hdl_snn/RESULTS.txt` per 2d).
- Verdetto di convergenza: dove si ferma l'IIDM, **perché**, e a che costo in area/latenza.
- Doc allineati (`SP4 §Studio IIDM`, `SESSION_RESUME`, memoria) + tutto committato.

### Fuori scope

- **Approssimare** la divisione (Variante L: già scartata sui dati) o qualunque leva che rompa `dmax=0`.
- La **SNN** (bancata a 99 MHz in 2d; si riapre solo se tornasse ad essere il collo).
- Il gate esaustivo **2c** full-dataset e il deploy (restano a valle, prima del bitstream).
- La **Fase C** su FPGA fisica.
