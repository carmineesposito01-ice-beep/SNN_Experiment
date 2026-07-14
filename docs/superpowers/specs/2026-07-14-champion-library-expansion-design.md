# Espansione libreria champion (decode-variants + ACC-IIDM open-loop) — design

> **Data:** 2026-07-14 · **Branch:** `Simulink_Importer` · **Worktree:** `.worktrees/Simulink_Importer`
> **Stato:** design **approvato** (brainstorming 2026-07-14). Decomposto in due sotto-progetti indipendenti,
> ognuno con il proprio spec di dettaglio → plan → esecuzione. Questo documento fissa il master + SP1 in
> dettaglio; SP2 è in outline (avrà il suo spec, con eventuali domande aperte).

---

## 1. Obiettivo
Espandere `matlab/snn_champions_lib.slx` con più versioni dei champion, per:
- confrontare il decode **sigmoide esatta (exp)** contro il decode **LUT** al variare della **dimensione della
  LUT**, così da trovare il compromesso accuratezza-vs-dimensione (e, a valle, accuratezza-vs-risorse HW);
- disporre di un blocco **Donatello + ACC-IIDM** open-loop, plug&play e HDL-ready, per il test controllore→plant.

## 2. Decomposizione (due sotto-progetti indipendenti)
- **SP1 — Libreria champion con varianti di decode** (parti 1+2): le varianti **exp** (riferimento) + **Donatello ×
  6 LUT fixed-point** (HDL-ready) + harness di confronto. *(Dettaglio §4.)*
- **SP2 — Blocco Donatello + ACC-IIDM open-loop** (parte 3): **Donatello con LUT-256** → **ACC-IIDM-accel
  open-loop**, plug&play HDL-ready. *(Outline §5; spec di dettaglio a parte.)*

Ognuno produce software funzionante e testabile per conto suo. Si implementa **SP1 per primo**.

## 3. Contesto e vincoli (condivisi)
- **Libreria attuale**: `build_library.m` genera `snn_champions_lib.slx` = **4 blocchi champion self-contained in
  `double`**, forward ALIF parallelo (10 tick srotolati) **+ decode con sigmoide `exp`** (riga 96). Sono già la
  variante **exp / riferimento comportamentale**: la parte 1 esiste nella sostanza.
- **Forward HDL-ready**: **B2 time-multiplexed** (`snn_b2_fsm`, 1 neurone/clock, `hdl.RAM`), reso **rango-parametrico**
  in B1.5-a (ROM per champion via `gen_b2_rom(name)` → `b2_rom_active`). Bit-exact vs core (gate parità 0/4).
- **Decode HDL**: `snn_decode_hdl.m` = sigmoide via **LUT 256 punti** su [-8,8) + interp lineare, fixed-point,
  `%#codegen`; costanti Donatello baked. Indice via shift (scala = N/16).
- **Plant**: `build_plant_lib.m` → `cf_plant_lib.slx`, blocco `ACC_IIDM` oggi **closed-loop** (integra `v`/`s`
  internamente; in=[v_l,v0,T,s0,a,b], out=[s,v,accel]).
- **HDL-ready** = avviando HDL Coder si ottiene VHDL corretto e **nel modo previsto** (non un flusso qualsiasi).
- **Onestà**: l'errore della LUT sigmoide è **champion-independent** (stessa curva; cambiano solo le costanti di
  decode) → il ventaglio LUT si caratterizza su **Donatello**. Le risorse HW sono **stime Vivado**, non silicio.

---

## PARTE SP1 — Libreria champion con varianti di decode

### 4.1 Scope
Aggiungere a `snn_champions_lib.slx`:
- le **4 varianti exp** (Donatello, Michelangelo, Raffaello, Leonardo) — riferimento comportamentale (già presenti;
  al più formalizzate/etichettate);
- **6 blocchi `Donatello_LUT{N}`** per **N ∈ {16, 32, 64, 128, 256, 512}** — forward B2 fixed-point + decode LUT-N,
  **HDL-ready**;
- un **harness di confronto** che produce la curva accuratezza-vs-dimensione (+ stima risorse HW).
Totale libreria: **10 blocchi** (4 exp + 6 Donatello-LUT).

### 4.2 Componenti (nuovi / modificati)
- **`matlab/snn_decode_lut.m`** — generalizza `snn_decode_hdl`: firma `p = snn_decode_lut(raw, N)` con **`N`
  `coder.const`**; tabella `sgtab` a `N` punti su [-8,8), scala indice `N/16` (potenza di 2 → shift), tipi Qm.n
  invariati. Costanti di decode (offset/invtau/lo/hilo) **per-champion** (baked da `champions_export`, come la ROM).
  `snn_decode_hdl` resta come alias N=256 (retro-compatibile) oppure viene sostituito da `snn_decode_lut(raw,256)`.
- **Builder libreria** — estendere `build_library.m` (o un nuovo `build_hdl_variants.m`) per aggiungere i 6
  sottosistemi `Donatello_LUT{N}`. Ogni blocco = **sottosistema streaming**: interfaccia `xn[4], start → params[5],
  done` (il B2 è multi-ciclo, ~341 clock). La MATLAB Function del blocco esegue il **forward B2** (`snn_b2_fsm`, ROM
  Donatello) **+ `snn_decode_lut(raw, N)`**. *Packaging (self-contained inline vs referenziato) = decisione di
  piano; default: coerente con la portabilità della libreria.*
- **`matlab/run_lut_sweep.m`** — harness di confronto: per ogni N, gira la variante sul **dataset held-out** (60
  traiettorie, `test_dataset.mat`) e raccoglie le metriche; scrive `axi/build/lut_sweep/results_lut.csv`.

### 4.3 Confronto — due baseline onesti
Per isolare ciò che si misura:
- **baseline comportamentale** = variante **double-exp** (verità di riferimento, accuratezza end-to-end assoluta);
- **baseline fixed** = forward B2 fixed + **decode esatto** (o LUT-512, quasi-esatta) → isola l'effetto della **sola
  dimensione LUT**, a quantizzazione del forward costante.
Metriche per N: **NRMSE/accuratezza** dei 5 parametri vs baseline (riuso del dataset e dell'accelerazione **MEX**
di B1.5-a per la velocità) **+ stima risorse HW** (LUT/BRAM) per N — via sintesi Vivado del decode LUT-N (o
modello di dimensionamento). Output: **curva del ginocchio** accuratezza-vs-dimensione, per scegliere il compromesso.

### 4.4 Verifica HDL-ready
Per ogni `Donatello_LUT{N}`: avviare **HDL Coder** sul blocco/entry-point e confermare che il VHDL sia generato
**senza errori e nel modo previsto** (decode = LUT sintetizzata, non `exp`/CORDIC automatico). Almeno un `N`
rappresentativo passa fino a **sintesi Vivado** per confermare le risorse.

### 4.5 Criteri di successo
1. `snn_decode_lut(raw, N)` genera la LUT corretta per ogni `N∈{16..512}` ed è **bit-identico** a `snn_decode_hdl`
   per `N=256` (regressione; `test_decode`).
2. I 6 blocchi `Donatello_LUT{N}` sono in `snn_champions_lib.slx`, trascinabili, e ognuno **genera VHDL** via HDL
   Coder senza errori.
3. `run_lut_sweep` produce la **curva accuratezza-vs-N** (+ stima risorse) su tutto il dataset, coi due baseline;
   ogni salto anomalo → **si indaga la causa**, non si aggiusta il numero.
4. Dati/figure pronti per la sezione "decode LUT sweep" di un report.

### 4.6 Fuori scope (SP1)
SP2 (ACC-IIDM), il ventaglio LUT sugli altri 3 champion (solo exp per loro), la sintesi HW di TUTTI i N (basta 1
rappresentativo end-to-end; gli altri via stima o on-demand).

---

## PARTE SP2 — Donatello + ACC-IIDM open-loop (outline)

Spec di dettaglio a parte (avrà domande aperte). Requisiti fissati ora:
- **Blocco** `Donatello_ACC_IIDM_ol` plug&play, HDL-ready: **Donatello con decode LUT-256** (la variante usata in
  Fase B) → 5 parametri → **ACC-IIDM-accel open-loop** → uscita `accel` (+ opz. i 5 params e intermedi `a_iidm`/`a_cah`).
- **Ingressi** = stato car-following dall'esterno: `s, v, dv, v_l`.
- **Open-loop (vincolo forte)**: **NON** integrare `v`/`s` internamente (niente `v = v + accel·DT`): la velocità
  effettiva sarà alterata a valle dal sistema di test, che **chiude il loop esternamente**. Il blocco è puro
  feedforward: stato → accelerazione.
- **Da decidere in SP2**: il filtro OU per la stima di `a_l` (ha stato persistente ma **non** è il loop velocità) —
  tenerlo interno al blocco o esternalizzarlo come ingresso; e la firma esatta delle uscite.

## Onestà / limiti
- Le varianti exp restano **comportamentali (double)**; le LUT sono **fixed-point sintetizzabili**.
- Ventaglio LUT su **Donatello** perché l'errore della sigmoide-LUT è champion-independent; il ginocchio scelto
  vale per gli altri.
- Risorse HW = **stime Vivado post-sintesi**, non silicio (Fase C).
