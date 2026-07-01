# Eval v3 — TURTLE POWER!!!

## Champion
| alias | tag | colore | carattere |
|---|---|---|---|
| Master Splinter | `__oracle__` | #7f7f7f | oracolo (param veri) |
| Raffaello | `R33_C2_A1_T12_fix` | #d62728 | Prodigy baseline, aggressivo |
| Leonardo | `LS3_PEAK_R0_launch_d03` | #1f9ed1 | champion BPTT, conservativo |
| Donatello | `PE_t05_gp0002` | #9467bd | best-NRMSE |
| Michelangelo | `A_lr1e2_t06_r16` | #ff7f0e | best-Adam, equilibrato |

## Cartelle (per dimensione)
- `00_Scorecard` confronto cross-champion (radar + tabella master)
- `01_Accuracy` NRMSE per-canale / accuracy (↓ meglio)
- `02_Safety_ClosedLoop` min-gap ↑, brake_margin_min ↑ (margine continuo, <0=inevitabile), TTC ↑, decel ↓, jerk ↓
- `03_StringStability` head-to-tail ↓ (≤1=stabile), peak |Γ(ω)| ↓
- `04_Identifiability` FIM (cond, sensibilità), causal, NRMSE stratificato
- `05_Quantization` degrado float→fixed-point (deploy FPGA)
- `06_V2X_Robustness` degrado vs PDR/latenza
- `07_VehicleDynamics` plant reale (μ bagnato + lag attuatore)
- `08_Energy_Spiking` energia SNN (nJ, ×vs ANN) + raster
- `09_Trajectories` traiettorie per scenario

`ERROR_<sez>.txt` (se presente) = quella sezione ha fallito; le altre proseguono.
