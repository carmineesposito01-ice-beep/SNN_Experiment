# Eval v3 — TURTLE POWER!!! (esaustivo)

## Champion
| alias | tag | colore | carattere |
|---|---|---|---|
| Master Splinter | `__oracle__` | #7f7f7f | oracolo (param veri) |
| Raffaello | `R33_C2_A1_T12_fix` | #d62728 | Prodigy baseline, aggressivo |
| Leonardo | `LS3_PEAK_R0_launch_d03` | #1f9ed1 | champion BPTT, conservativo |
| Donatello | `PE_t05_gp0002` | #9467bd | best-NRMSE |
| Michelangelo | `A_lr1e2_t06_r16` | #ff7f0e | best-Adam, equilibrato |

## Cartelle (per dimensione)
- `00_Scorecard` confronto cross-champion (radar + tabella master, incl. oracolo dove sensato)
- `01_Accuracy` NRMSE per-canale / accuracy (heatmap + bar, oracolo=0 di riferimento)
- `02_Safety_ClosedLoop` SSM estese (TTC/TET/TIT/DRAC/TED/TID/cpi/headway), comfort ISO, tracking, Δ-vs-oracolo
- `03_StringStability` 3 nozioni: head-to-tail, peak |Γ(ω)|, frac_strict; profilo amplificazione lungo il plotone
- `04_Identifiability` FIM (cond, spettro autovalori), equifinality, PE, causal, NRMSE strat, naturalisticity KS, calibration
- `05_Quantization` fixed+po2, 2-12 bit, degrado per-parametro, ablazione pesi PO2 on/off
- `06_V2X_Robustness` PDR/latenza/jitter/Gilbert/blackout + 3 hold_mode + AoI-vs-safety (oracolo sotto canale)
- `07_VehicleDynamics` plant reale (ideale/bagnato/ghiaccio), oracolo di riferimento
- `08_Energy_Spiking` energia SNN (nJ, ×vs ANN) + diagnostica rete (dead/sat/eff_rank/raggio spettrale) + raster reale
- `09_Trajectories` traiettorie per scenario (champion + oracolo)
- `10_Reachability` frontiera worst-case: gap minimo sicuro vs Δv (oracolo vs SNN)
- `11_Breakdown` curva di rottura: collisione vs decel leader e vs gap cut-in (oracolo vs SNN)
- `12_Mesoscopic` plotone 12 veicoli: string stability (gain per veicolo) + heatmap spazio-tempo + scorecard
- `13_Macroscopic` anello: diagramma fondamentale Q(ρ)/V(ρ) + capacità + onde stop&go
- `14_Showcase` VETRINA "come spara la rete": raster sincronizzato + phase-plane + energia + GIF in diretta

`ERROR_<sez>.txt` (se presente) = quella sezione ha fallito; le altre proseguono.
