# report/ — I deliverable finali (terna v3)

Questa cartella contiene i **tre documenti definitivi** del progetto CF_FSNN, pensati per essere
letti da chiunque (anche esperti del settore) e mutuamente coerenti. Sono generati da script:
**non modificare i `.md`/`.pdf` a mano** — vengono rigenerati e sovrascritti.

## I tre documenti (la "terna")

| File | Cosa spiega | Generatore |
|---|---|---|
| **HOW_IT_WORKS_v3**.{md,pdf} | **La teoria e la rete**: SNN vs ANN, ALIF, addestramento (BPTT+surrogate, EventProp, STDP), architettura, approccio PINN, quantizzazione po2 | `scripts/build_how_it_works_v3.py` |
| **VALIDATION_REPORT_v3**.{md,pdf} | **I risultati**: i 4 champion vs l'oracolo su una validazione closed-loop a 6-tier (accuratezza, sicurezza, traffico, V2X, profilo FPGA) | `scripts/build_validation_report_v3.py` |
| **FPGA_REPORT**.{md,pdf} | **Il profilo hardware** (Fase A pre-silicio): pesi po2, fixed-point, spiking, energia, timing/WCET, risorse, SEU, I/O, termico | `scripts/build_fpga_report.py` |

Ownership dei contenuti: **HOW** = teoria · **VALIDATION** = risultati · **FPGA** = hardware.
I tre si citano a vicenda senza duplicare (ogni tema ha un solo "proprietario").

## Cartelle di figure

- `figures_howitworks_v3/` — diagrammi ed equazioni typeset di HOW (rigenerate da matplotlib).
- `figures_validation_v3/` — figure di VALIDATION (parte ricostruite dai CSV, parte riusate dalla run).
- `figures_fpga/` — le 45 figure a dati reali di FPGA (copiate da `results/evaluate/FPGA/`).

I riferimenti alle figure nei `.md` sono **relativi** (`figures_.../x.png`): restano validi finché
figure e documento stanno nella stessa cartella.

## Come rigenerare

```bash
# da root del repo
python scripts/build_how_it_works_v3.py
python scripts/build_validation_report_v3.py
python scripts/build_fpga_report.py
```

Il rendering è **deterministico** per i `.md` (a parità di codice/dati l'output è identico); i
`.pdf` cambiano solo il timestamp interno. VALIDATION e FPGA leggono i dati reali da
`results/evaluate/` (rispettivamente `v3_TURTLE_POWER!!!/` e `FPGA/`); HOW non richiede checkpoint.

## Pipeline (reportlab)

Ogni script è una **sorgente unica → md + pdf** con font DejaVu. Blocchi supportati:
`cover / h1 / h2 / p / callout / table / img / eq / toc`. Le equazioni sono immagini
mathtext dimensionate come il testo; il `toc` è un vero Sommario con numeri di pagina
(reportlab `TableOfContents` a doppia passata). Non c'è LaTeX nel percorso di rendering.

## Note

- Le **versioni obsolete** (HOW_IT_WORKS v1/v2, VALIDATION_REPORT v1) sono state rimosse: la
  storia resta in git. Qui vive solo la terna corrente.
- La presentazione (deck) è un deliverable separato in [`../presentation/`](../presentation/).
