# document/ — Memoria di progetto e riferimenti

Questa cartella contiene **due cose distinte**:

1. **Memoria di progetto** — i file `.md` scritti dal team per documentare, tracciare e poter
   **riprendere** il lavoro in sicurezza (log di studio, design, piani, glossario, procedure di
   ripresa). Sono la "memoria" operativa del progetto.
2. **`papers/`** — i **veri documenti** esterni: paper scientifici di riferimento (PDF), vedi
   [`papers/README.md`](papers/README.md).

> I **report finali** del progetto (la terna HOW_IT_WORKS / VALIDATION / FPGA) **non** sono qui:
> vivono in [`../report/`](../report/). Le loro versioni obsolete sono state rimosse.

Inoltre: `figures_dynamic/` contiene le figure usate da `DYNAMIC_STUDY_B_RESULTS.md`.

## Punti d'ingresso (leggere prima questi)

| File | A cosa serve |
|---|---|
| `SESSION_RESUME.md` | **Riprendere in 5 minuti**: stato attuale + cosa fare adesso |
| `EVENTPROP_STATUS.md` | Master del track EventProp/principale (stato, mappa documenti, prossima azione) |
| `RESUME_PROCEDURE.md` | Procedura deterministica per ri-allineare i documenti e ripartire |
| `GLOSSARY.md` | Glossario di termini e codici (champion, metriche, sigle) |
| `WORKFLOW.md`, `TIMELINE.md`, `P_S.md` | Flusso di lavoro, cronologia, problemi/soluzioni |

## Memoria per categoria

- **Ripresa / navigazione**: `SESSION_RESUME`, `RESUME_PROCEDURE`, `EVENTPROP_STATUS`,
  `GLOSSARY`, `WORKFLOW`, `TIMELINE`, `P_S`, `FUTURE_WORK`, `project_core_guidelines`.
- **Log e risultati di studio**: `AUDIT_2026-06-02`, `BUGS_2026-06-03`, `LOSS_STUDY_AND_EVALUATION`,
  `PRODIGY_DEEP_STUDY`, `PRODIGY_STUDY_CLOSURE`, `EVENTPROP_STUDY_PLAN`, `EVENTPROP_OPTIMIZER_SWEEP`,
  `EVENTPROP_GRID2X2`, `DYNAMIC_STUDY_PLAN`, `DYNAMIC_STUDY_B_RESULTS`, `S2_CAPACITY_DIGRESSION`,
  `S3_CONSOLIDATION_AND_FUTURE_B`, `EVALUATE_UPGRADE`, `SIMULATOR_FINDINGS`.
- **Design / framework**: `EVENTPROP_DESIGN`, `FPGA_EVALUATE_DESIGN`, `FPGA_EVALUATION_FRAMEWORK`,
  `SIMULATOR_DESIGN`, `POST_FPGA_ROADMAP`, `PRESENTATION_DESIGN`, `PRESENTATION_PLAN`,
  `PRESENTATION_MILESTONE`.
- **Note storiche / misc**: `cf_model_recommendation`, `correction`, `optimization_ideas`,
  `training_plan`, `use_cases`.

## Regola d'oro

Questi `.md` sono la memoria: alcuni sono **critici per la ripresa** (`SESSION_RESUME`,
`EVENTPROP_STATUS`, `RESUME_PROCEDURE`) e i loro path sono referenziati altrove — non spostarli
senza aggiornare i riferimenti. Le figure citate da un `.md` sono relative alla cartella `document/`.
