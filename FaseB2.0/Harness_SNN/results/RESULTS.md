# Harness_SNN — risultati (Fase B2.0 · T6a)

Generato da `run_harness_snn('full')` il 2026-07-29 12:52:55 — runtime 74.6 min.
Rigenerabile con **un comando** (vedi README).

## Configurazione misurata

| parametro | valore |
|---|---|
| blocco | `Donatello_Tier` @ TIER=BALANCED, NFRAC=13 |
| ingressi | `fixdt(1,32,20)` · hold 500 clock |
| dataset | `test_dataset.mat` — 60 traiettorie × 1000 control-step |
| latenza blocco (misurata) | 364 clock |
| golden | dal BLOCCO stesso (oracolo), calcolato una volta e condiviso da RTL e metriche |

## Cancelli

| cancello | esito | numeri |
|---|---|---|
| **T6-EXACT** — RTL 5 param == blocco | **PASS** | nMismatch **0 / 300000** (60 traj × 1000 step × 5 param) |
| **LAT** — latenza misurata < HOLD | **PASS** | 364 clock (HOLD 500) |
| **Sensibilità** — 1 LSB corrotto | **PASS** | nMismatch 1 (atteso ≥1) |
| **PORT-TYPE** | **PASS** | coperto da T6-EXACT (tipo errato ⇒ mismatch sistematico) |

## Accuratezza di stima (versione FPGA == blocco)

| param | max | p99 |
|---|---|---|
| `v0` | 15.01 | 13.8 |
| `T` | 1.125 | 0.9127 |
| `s0` | 0.9368 | 0.8435 |
| `a` | 0.9908 | 0.892 |
| `b` | 1.003 | 0.867 |

`v0` alto = **identificabilità** (osservabile solo a flusso libero), non difetto RTL.
La qualità car-following è il closed-loop (T7).
