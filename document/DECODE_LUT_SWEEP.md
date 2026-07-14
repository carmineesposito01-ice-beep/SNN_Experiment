# Studio decode LUT-sweep (Donatello) — documento sorgente per il report

> **Ruolo**: documento di lavoro che accumula metodo, dati e risultati dello studio sulla dimensione della LUT
> del decode (la "piccola digressione" di SP1). È la **sorgente** del futuro report (come `FPGA_PHASE_B_POWER.md`
> lo è stato per il report Fase B). Track `Simulink_Importer`. Aggiornato a mano man mano; ogni numero è grounded
> su `matlab/axi/build/lut_sweep/results_lut.csv` (accuratezza) e sul formato della LUT (risorse).

## 1. Scopo
Per il candidato al deploy **Donatello**, caratterizzare il compromesso tra **dimensione della LUT** della sigmoide
di decode e (a) **accuratezza** dei 5 parametri IDM, (b) **risorse hardware**. Il decode a LUT è la versione
**HDL-ready** (fixed-point, sintetizzabile) che sostituisce la sigmoide `exp`, non sintetizzabile in modo controllato.
Obiettivo: trovare il giusto compromesso accuratezza/precisione-nella-conversione vs grandezza della LUT.

## 2. Metodo
- **Forward**: B2 time-multiplexed fixed-point (`snn_b2_fsm` rango-parametrico + ROM Donatello), accelerato via
  **MEX** (`snn_traj_fixed_r16_mex`, da B1.5-a) → `raw` (uscita LI) per step, calcolato **una volta** per traiettoria.
- **Decode**: `snn_decode_lut(raw, N)` — sigmoide via **LUT a N punti** su [-8,8) + interpolazione lineare,
  N ∈ {16, 32, 64, 128, 256, 512}. Tabella σ in **Q1.14** (16 bit). **Verificato bit-identico** a `snn_decode_hdl`
  per N=256 (0 mismatch su 200 punti casuali).
- **Sweep di accuratezza**: la curva usa il decode-LUT-N in **double** (l'errore d'interpolazione della sigmoide =
  effetto **puro** della dimensione). Il fixed-point aggiunge un offset ~costante (bit-verificato a parte), non
  sposta il ginocchio.
- **Dataset**: 60 traiettorie held-out (`test_dataset.mat`). Aggregazione params = media della 2ª metà (come il
  riferimento Python). Metriche: **NRMSE → accuratezza** vs `gt_params` (veri); **dmax vs LUT-512** (near-exact) =
  effetto della sola dimensione.
- Harness: `matlab/run_lut_sweep.m`. Decode parametrico: `matlab/snn_decode_lut.m`.

## 3. Risultati — accuratezza (60 traiettorie)

| N (punti LUT) | accuratezza % | dmax vs LUT-512 (effetto pura dimensione) |
|---|---|---|
| 16  | 84.06 | 0.252 |
| 32  | 84.00 | 0.0345 |
| 64  | 83.98 | 0.0114 |
| 128 | 83.97 | 0.0025 |
| 256 | 83.97 | 0.0005 |
| 512 | 83.97 | 0 |

L'accuratezza satura a **83.97%** già da N=64; N=16 (84.06%) è entro il rumore (l'errore LUT è scorrelato dall'errore
di identificazione). Il **dmax vs 512** converge **quadraticamente** (÷~4-8 a ogni raddoppio di N): coerente con
l'interpolazione lineare di una funzione liscia.

## 4. Risultati — risorse
**(a) Dimensionamento del formato (naïve).** La σ-LUT contiene N valori a Q1.14 (16 bit) → **N × 16 bit** (256 bit a
N=16, 8 192 bit a N=512). Come pura memoria sarebbe < 1 BRAM18 (18 Kbit) anche a N=512.

**(b) Realizzazione HDL Coder — *come viene resa davvero* (VHDL, Task 5).** HDL Coder mappa la tabella come **array
costante indicizzato → logica combinatoria (mux tree), NON BRAM** (questo corregge l'ipotesi "BRAM" di (a)). Stima RTL
del solo decode (`snn_decode_lut`, combinatorio, 0 errori/warning, conformance OK):

| N | Multipliers | Adders/Sub | Registers | Multiplexers | RAMs |
|---|---|---|---|---|---|
| 16  | 15 | 35 | 0 | 45 | 0 |
| 32  | 15 | 35 | 0 | 50 | 0 |
| 64  | 15 | 35 | 0 | 50 | 0 |
| 128 | 15 | 35 | 0 | 50 | 0 |
| 256 | 15 | 35 | 0 | 50 | 0 |
| 512 | 15 | 35 | 0 | 50 | 0 |

La stima RTL è **quasi N-indipendente** (15 mult / 35 add / ~50 mux, **0 RAM, 0 registri**): la dimensione della tabella
è ripiegata nella costante e viene mappata a LUT dalla **sintesi**, non conteggiata dallo stimatore ad alto livello. La
**curva risorse-vs-N reale** (conteggio LUT) richiede una **sintesi Vivado OOC** — *non eseguita in questa sessione
(Vivado non installato qui); rinviata all'ambiente Vivado, come in Fase B.* In ogni caso il decode è **cheap**:
combinatorio, poche decine di celle, **nessuna BRAM**. Tool: `matlab/make_hdl_decode_lut.m`.

## 5. Finding
- **Accuratezza end-to-end piatta (~84%)** su N∈{16..512}: è dominata dalla rete, non dal decode. La sigmoide è
  **liscia** e quindi facile da approssimare anche con poche coppie.
- **Errore d'interpolazione** (dmax vs 512) piccolo e a convergenza rapida: **N=32 → 0.034**, **N=64 → 0.011**.
- **Risorse trascurabili** in tutto il range (< 1 BRAM anche a 512).
- **Compromesso soft**: entrambi gli assi (accuratezza, risorse) sono piatti/economici. Scelta pratica:
  **32-64 punti** (errore d'interpolazione ≤ 0.03, minima logica) oppure **128** con margine a costo ~nullo. La
  **256 attuale è sovradimensionata** per l'accuratezza, ma costa poco. Non c'è un vero vincolo che imponga una LUT
  grande: la si può ridurre con serenità.

## 6. Blocchi di libreria `Donatello_LUT{N}` (HDL-ready, Task 4)
Aggiunti a `snn_champions_lib.slx` 6 sottosistemi streaming **`Donatello_LUT{N}`** (N∈{16,32,64,128,256,512}),
accanto ai 4 blocchi champion base (Donatello/Leonardo/Michelangelo/Raffaello, **invariati**). Ogni blocco:
- **Interfaccia**: `xn`(4, normalizzato) + `start` → `params`(5: v0,T,s0,a,b) + `done`. Streaming: `start=1` avvia una
  control-step; `done=1` quando i `params` sono pronti (**≈341 clock/inferenza**, forward B2 time-multiplexato).
- **Interni**: `snn_b2_fsm` (ROM Donatello, `hdl.RAM`) + `snn_decode_lut(raw, N)`. I 6 differiscono **solo per N**.
- **Stile referenziato** (come il B2 deployato): la MATLAB Function chiama `snn_b2_fsm`/`snn_decode_lut` → questi
  (+`snn_types`, `b2_rom_active`) devono stare sul path all'uso/sim/HDL. La ROM Donatello si (ri)genera con
  `gen_b2_rom('Donatello')` (lo fa `build_hdl_variants.m`). *(I 4 blocchi base restano self-contained; i 6 LUT no — tradeoff scelto.)*

**Validazione (Simulink)**: tutti e 6 i blocchi **simulano** (l'`hdl.RAM` gira dentro la MATLAB Function) e al primo
`done` riproducono **bit-exact** (`dmax=0`) il riferimento `snn_core`+`snn_decode_lut(raw,N)`. I `params` al blocco
(single control-step da reset, stesso `raw`) mostrano la convergenza con N:

| N | params @ done (dal blocco Simulink) |
|---|---|
| 16  | [25.782, 1.6222, 2.7910, 0.83728, 1.7156] |
| 32  | [25.739, 1.6295, 2.7786, 0.82886, 1.7135] |
| 64  | [25.725, 1.6313, 2.7751, 0.82458, 1.7129] |
| 128 | [25.723, 1.6315, 2.7749, 0.82349, 1.7128] |
| 256 | [25.723, 1.6315, 2.7749, 0.82324, 1.7128] |
| 512 | [25.723, 1.6315, 2.7749, 0.82300, 1.7128] |

Le differenze fra N (es. param 4: 0.837 → 0.823) sono l'errore d'interpolazione LUT, coerente con §3 (piccolo, a
convergenza rapida). Builder: `matlab/build_hdl_variants.m`.

## 7. Stato / onestà
- **Fatto**: `snn_decode_lut(raw,N)` (Task 1, bit-verified a N=256); `run_lut_sweep` (Task 2, curva 60-traj);
  **6 blocchi `Donatello_LUT{N}` in libreria (Task 4), simulazione bit-exact**; **verifica HDL Coder dei 6 decode
  LUT-N (Task 5): 6/6 VHDL, 0 errori/warning, conformance OK, sigmoide = tabella costante (niente `exp`), decode
  combinatorio ~N-flat (§4b)**.
- **Da fare**: **sintesi Vivado OOC** del decode-LUT-N per N rappresentativi (risorse assolute LUT/FF, N-scaling reale) —
  **rinviata: Vivado non disponibile in questa sessione** (come Fase B, va eseguita nell'ambiente Vivado); figura
  accuratezza/risorse-vs-N. Piano: `docs/superpowers/plans/2026-07-14-sp1-decode-variants.md`.
- **Onestà**: lo sweep di accuratezza è in double (isola l'effetto della dimensione); il fixed-point è bit-verificato a
  parte (N=256 == `snn_decode_hdl`; i blocchi Simulink girano il fixed e sono bit-exact al riferimento). Le risorse RTL
  sono **stime HDL Coder** (§4b); gli **assoluti Vivado sono rinviati**. Tutto pre-silicio.
