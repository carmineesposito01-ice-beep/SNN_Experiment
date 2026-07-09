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
