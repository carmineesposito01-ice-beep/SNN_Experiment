# report/ — I deliverable finali

Questa cartella contiene i documenti definitivi del progetto CF_FSNN, pensati per essere letti da
chiunque (anche esperti del settore) e mutuamente coerenti. Sono generati da script:
**non modificare i `.md`/`.pdf` a mano** — vengono rigenerati e sovrascritti.

Sono **due famiglie**, con perimetri diversi:

- la **terna v3** — teoria, risultati e profilo hardware pre-silicio (sezione qui sotto);
- i **report di Fase B / B2.0** — la catena verso l'FPGA, dalla quantizzazione al silicio
  (sezione più in basso). Sono arrivati col merge del ramo `Simulink_Importer`.

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

---

## I report di Fase B / B2.0 — la catena verso l'FPGA

Coprono ciò che succede **dopo** la terna: la conversione del controllore in hardware, la sua
validazione bit-esatta e la caratterizzazione su silicio. Stessa pipeline reportlab, stessa
regola: generati, non scritti a mano.

| File | Cosa spiega | Generatore |
|---|---|---|
| **QUANTIZATION_STUDY_REPORT**.{md,pdf} | quanti bit servono davvero: sweep per-campo, collo della fedeltà contro quello dell'hardware | `scripts/build_quantization_report.py` |
| **Trade_Off_Study_Parte_A**.{md,pdf} | i blocchi della libreria: area, Fmax, scelte di architettura | `scripts/build_blocco_a_report.py` |
| **FPGA_PHASE_B_REPORT**.{md,pdf} | Fase B: potenza di sistema misurata, duty reale, confronto SNN-vs-ANN | `scripts/build_fpga_phase_b_report.py` |
| **B2_0_CHECKPOINT_REPORT**.{md,pdf} | il punto di situazione di Fase B2.0 | `scripts/build_b2_0_checkpoint_report.py` |
| **B2_0_HARNESS_SNN_REPORT**.{md,pdf} | harness della SNN da sola: validazione RTL (T6a) e caratterizzazione hardware (T6b) | `scripts/build_harness_snn_report.py` |
| **B2_0_HARNESS_SNN_IIDM_REPORT**.{md,pdf} | harness del composto SNN+IIDM: T7a/T7b, clock gating, energia per control-step | `scripts/build_harness_snn_iidm_report.py` |

### Cartelle di figure

`figures_quant/` · `figures_blocco_a/` · `figures_phase_b/` · `figures_b2_0/` ·
`figures_harness_snn/` · `figures_harness_snn_iidm/` — una per report, coi riferimenti
**relativi** come nella terna.

### Dove continua il lavoro

La **Fase C** (bring-up su silicio) non produce un report in questa cartella: vive in
[`../FaseC/`](../FaseC/) coi suoi artefatti in `FaseC/results/`. Il punto d'ingresso è
[`../FaseC/STATO.md`](../FaseC/STATO.md).

---

## Note

- Le **versioni obsolete** (HOW_IT_WORKS v1/v2, VALIDATION_REPORT v1) sono state rimosse: la
  storia resta in git. Qui vive solo la terna corrente.
- La presentazione (deck) è un deliverable separato in [`../presentation/`](../presentation/).
