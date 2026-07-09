# results/ — Output degli esperimenti

Risultati (CSV, PNG, log, manifest) prodotti dai notebook e dagli script di studio, organizzati
per **campagna di esperimenti**. Questa cartella è versionata (i risultati sono la fonte-verità
dei report e degli studi), quindi è **grande**: non aggiungere qui artefatti temporanei.

## Sottocartelle principali

| Cartella | Campagna |
|---|---|
| `evaluate/` | Le run di **valutazione** che alimentano la terna di `report/`. Due chiavi: `v3_TURTLE_POWER!!!/` (validazione 6-tier dei 4 champion → VALIDATION_REPORT) e `FPGA/` (FPGA-evaluate Fase A → FPGA_REPORT). |
| `Prodigy_Study/` | Studio dell'ottimizzatore Prodigy (la campagna più estesa: R24F→R33). |
| `Loss_Study/` | Studio della loss / evaluation framework (S1…S3, validazione). |
| `Dynamic_Study/` | Studio del "tetto" sui parametri dinamici a/b (L0…L2). |
| `EventProp_BigSweep*`, `EventProp_Spectral_Sweep`, `EventProp_Study` | Studi EventProp (gradiente esatto, raggio spettrale). |
| `SW_OptimizerSweep`, `GRID2x2`, `T30`, `P6/P9/P12/P15`, `A1_onecycle_v3` | Sweep e run storiche di supporto. |
| `_scratch/` | Area di lavoro temporanea (vedi `_scratch/README.md`). |

Alcune sottocartelle hanno un README dedicato (es. `evaluate/v3_TURTLE_POWER!!!/README.md`).

## Come si legge

Ogni run tipicamente contiene: CSV con le metriche per-epoca/per-scenario, PNG diagnostici, e un
manifest/log. I verdetti sintetici delle campagne sono nei `.md` di `document/` (es.
`LOSS_STUDY_AND_EVALUATION.md`, `DYNAMIC_STUDY_B_RESULTS.md`, `PRODIGY_STUDY_CLOSURE.md`).
La verifica dei manifest post-run è in `scripts/verify_eval_v3.py` / `verify_fpga_eval.py`.
