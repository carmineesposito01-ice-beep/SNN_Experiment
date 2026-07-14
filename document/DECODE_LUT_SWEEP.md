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

## 4. Risultati — risorse (dimensionamento)
La LUT memorizza N valori σ a Q1.14 (**16 bit/entry**) → **N × 16 bit**; il datapath d'interpolazione (5 canali:
sottrazione offset, scala, indice, interp lineare, riscalamento affine) è **costante** con N.

| N | tabella LUT | contesto Zynq-7020 |
|---|---|---|
| 16  | 256 bit  | LUTRAM distribuita, trascurabile |
| 32  | 512 bit  | LUTRAM distribuita |
| 64  | 1 024 bit | LUTRAM distribuita |
| 128 | 2 048 bit | LUTRAM / frazione di BRAM |
| 256 | 4 096 bit | < ¼ di un BRAM18 (18 Kbit) |
| 512 | 8 192 bit | < ½ di un BRAM18 |

Il costo **N-dipendente è trascurabile** in tutto il range: anche N=512 sta in **< 1 BRAM18**, e N≤64 comodamente
in LUTRAM distribuita. *(Cifre da dimensionamento del formato; una sintesi Vivado OOC del decode-LUT-N confermerebbe
gli assoluti col datapath — vedi §6.)*

## 5. Finding
- **Accuratezza end-to-end piatta (~84%)** su N∈{16..512}: è dominata dalla rete, non dal decode. La sigmoide è
  **liscia** e quindi facile da approssimare anche con poche coppie.
- **Errore d'interpolazione** (dmax vs 512) piccolo e a convergenza rapida: **N=32 → 0.034**, **N=64 → 0.011**.
- **Risorse trascurabili** in tutto il range (< 1 BRAM anche a 512).
- **Compromesso soft**: entrambi gli assi (accuratezza, risorse) sono piatti/economici. Scelta pratica:
  **32-64 punti** (errore d'interpolazione ≤ 0.03, minima logica) oppure **128** con margine a costo ~nullo. La
  **256 attuale è sovradimensionata** per l'accuratezza, ma costa poco. Non c'è un vero vincolo che imponga una LUT
  grande: la si può ridurre con serenità.

## 6. Stato / onestà
- **Fatto**: `snn_decode_lut(raw,N)` (Task 1, bit-verified a N=256); `run_lut_sweep` (Task 2, curva 60-traj).
- **Da fare (sessione HDL/Vivado)**: sintesi Vivado OOC del decode-LUT-N per N rappresentativi (conferma risorse
  assolute col datapath); i 6 blocchi `Donatello_LUT{N}` in `snn_champions_lib.slx` (`build_hdl_variants.m`);
  verifica HDL Coder (VHDL con LUT sintetizzata "nel modo previsto"). Piano: `docs/superpowers/plans/2026-07-14-sp1-decode-variants.md`.
- **Onestà**: lo sweep di accuratezza è in double (isola l'effetto della dimensione); il fixed-point è
  bit-verificato a parte (N=256 == `snn_decode_hdl`). Le risorse sono da **dimensionamento del formato**, non da
  sintesi (la sintesi confermerà gli assoluti). Tutto pre-silicio.
