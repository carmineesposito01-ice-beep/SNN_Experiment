# scripts/ — Generatori, valutazioni, verifiche, animazioni

Script eseguibili (da lanciare dalla **root** del repo). Si dividono in generatori dei
deliverable, script di studio/valutazione, verifiche e animazioni.

## Generatori dei report (terna v3 → `report/`)

| Script | Produce |
|---|---|
| `build_how_it_works_v3.py` | `report/HOW_IT_WORKS_v3.{md,pdf}` (+ figure) |
| `build_validation_report_v3.py` | `report/VALIDATION_REPORT_v3.{md,pdf}` (legge `results/evaluate/v3_TURTLE_POWER!!!/`) |
| `build_fpga_report.py` | `report/FPGA_REPORT.{md,pdf}` (legge `results/evaluate/FPGA/`) |
| `fpga_figures.py` | Le 45 figure a dati reali della FPGA-evaluate (da tensori/forward reali) |

## Generatori dei report di Fase B / B2.0 (→ `report/`)

La catena verso l'FPGA: quantizzazione, blocchi della libreria, potenza di sistema, harness di
validazione hardware. Stessa pipeline reportlab della terna.

| Script | Produce |
|---|---|
| `build_quantization_report.py` | `report/QUANTIZATION_STUDY_REPORT.{md,pdf}` |
| `build_blocco_a_report.py` | `report/Trade_Off_Study_Parte_A.{md,pdf}` |
| `build_fpga_phase_b_report.py` | `report/FPGA_PHASE_B_REPORT.{md,pdf}` |
| `build_b2_0_checkpoint_report.py` | `report/B2_0_CHECKPOINT_REPORT.{md,pdf}` |
| `build_harness_snn_report.py` | `report/B2_0_HARNESS_SNN_REPORT.{md,pdf}` (SNN da sola: T6a/T6b) |
| `build_harness_snn_iidm_report.py` | `report/B2_0_HARNESS_SNN_IIDM_REPORT.{md,pdf}` (composto: T7a/T7b) |

## Export verso MATLAB

| Script | Produce |
|---|---|
| `export_champions.py` | `matlab/champions_export.mat` — i pesi dei champion quantizzati po2, che alimentano la catena Simulink → HDL |

Tutti e tre i `build_*` sono **sorgente unica → md+pdf** (reportlab). Vedi `report/README.md`.

## Studio e valutazione

- `closed_loop_identify.py` — identificazione closed-loop + sweep V2X.
- `dynamic_study_B.py`, `dynamic_study_L0.py` — studi sui parametri dinamici a/b.
- `decode_headroom_probe.py`, `decode_lut_calibrate.py` — decode → LUT / headroom.
- `path_b_validate.py`, `_eventprop_combined_ckpt_pass.py`, `_fpga_eval_mockup.py` — utility di supporto.

## Verifica

- `preflight.py` — controlli pre-esecuzione.
- `audit_checkpoints.py` — audit dei checkpoint.
- `verify_eval_v3.py`, `verify_fpga_eval.py` — verifica del manifest post-run (evaluate v3 / FPGA).

## Animazioni (Manim)

`manim/` — animazioni concettuali per la presentazione: `lif_spike.py`, `alif_fatigue_dark.py`,
`eventprop_adjoint.py`.

> Convenzione: gli script con prefisso `_` sono ausiliari/interni.
