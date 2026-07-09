# CF_FSNN — Car-Following Spiking Neural Network

Rete neuronale **spiking** (SNN) *physics-informed* che, osservando via V2X la dinamica di
un veicolo (gap, velocità, Δv, velocità del leader), **identifica i 5 parametri** del modello
di car-following **ACC-IIDM** `[v0, T, s0, a, b]` — con l'obiettivo di essere eseguita su
**FPGA** (Zynq-7020 / PYNQ-Z1) grazie a pesi potenze-di-due (moltiplicazione → bit-shift, 0 DSP).

> 🚀 **Riprendere dopo una pausa:** leggi `document/SESSION_RESUME.md` (5 min) e, per il track
> EventProp/principale, il master `document/EVENTPROP_STATUS.md`.
> Ogni cartella ha il suo `README.md`: questo file è la **mappa** dell'intera repository.

---

## 1. Cos'è, in una riga

Un problema **inverso**: non si prevede la traiettoria, si stimano i *cinque numeri* che la
generano. La fisica (ACC-IIDM) fa da ponte tra ciò che la rete produce e ciò che è misurabile
(l'accelerazione), tramite una **loss PINN**. La spiegazione completa è nella terna di report
in [`report/`](report/) — punto di partenza consigliato: `report/HOW_IT_WORKS_v3.pdf`.

## 2. Architettura (baseline)

```
Input(4)  →  HiddenLayer_ALIF(32)  →  OutputLayer_LI(5)  →  σ + bounds  →  [v0, T, s0, a, b]
[s,v,Δv,v_l]  ALIF spiking + ricorrenza          integratore
              low-rank U·V + ritardi assonali     leaky
```

- **~864 parametri** (baseline, rango ricorrenza 8); le varianti EventProp usano rango 16 (~1400).
- **Neurone ALIF** (Adaptive LIF): leak a bit-shift (fattore 7/8), soglia adattiva, reset sottrattivo.
- **Pesi Power-of-Two** (13 livelli): moltiplicazione → shift, **0 DSP** su FPGA.
- **10 tick SNN interni** per ogni passo fisico (Δt = 0.1 s).
- **Loss PINN a 5 componenti**: `L_data` (RMSE mascherata sull'accelerazione) + `L_phys` +
  `L_OU` (mean-reversion di T) + `L_bc` (anti-crash) + `L_sr` (spike-rate); pesi λ = (1, 0.1, 0.05, 1, 0.5).
- **Addestramento**: BPTT + surrogate gradient (produzione; γ = 1.0, fast-sigmoid, STE) via Adam/Prodigy;
  **EventProp** (gradiente esatto via adjoint) come studio.

I 4 **champion** validati: `Raffaello`, `Leonardo` (BPTT) · `Donatello`, `Michelangelo` (EventProp).
Candidato al deploy: **Donatello** (contrattivo ρ<1, 0 neuroni morti, migliore accuratezza).
Dettagli e numeri: `report/VALIDATION_REPORT_v3` e `report/FPGA_REPORT`.

## 3. Mappa della repository

| Cartella | Contenuto | Dettagli |
|---|---|---|
| [`report/`](report/) | **I 3 deliverable finali** (la terna v3: teoria, risultati, profilo FPGA) + i generatori | `report/README.md` |
| [`document/`](document/) | **Memoria** di progetto (`.md` di ripresa/studio/design) + `papers/` (paper esterni) | `document/README.md` |
| [`core/`](core/) | Il modello: rete, neuroni, hardware (surrogate+po2), EventProp, ottimizzatore | `core/README.md` |
| [`data/`](data/) | Generatore di traiettorie sintetiche ACC-IIDM | `data/README.md` |
| [`utils/`](utils/) | Toolbox: simulatore closed-loop, quantizzazione, identificabilità, profilatori FPGA | `utils/README.md` |
| [`scripts/`](scripts/) | Generatori dei report, figure FPGA, script di studio e verifica, animazioni Manim | `scripts/README.md` |
| [`tests/`](tests/) | Test pytest (I/O champion, tier-0 eval, profilatori/SEU FPGA) | `tests/README.md` |
| [`results/`](results/) | Output degli esperimenti (per studio) + `evaluate/` (le run che alimentano i report) | `results/README.md` |
| [`Arch_Tested/`](Arch_Tested/) | Snapshot self-contained delle architetture testate (uno per variante, con README) | `Arch_Tested/README.md` |
| [`champions/`](champions/) | I 4 checkpoint champion frozen (~30 KB l'uno, versionati) | `champions/README.md` |
| [`presentation/`](presentation/) | Deck di presentazione (Quarto + reveal.js) | `presentation/README.md` |
| [`opt_plots/`](opt_plots/), [`sweep_plots/`](sweep_plots/) | Archivi di grafici di ottimizzatore/sweep | i rispettivi README |
| [`original_FSNN/`](original_FSNN/) | La FSNN originale di riferimento (pre-progetto) | `original_FSNN/README.md` |
| **root** | Notebook di studio (48) + entry-point di codice (`train.py`, `config.py`, `eval_report.py`, …) | § 4 e § 5 |

> **Non versionati** (`.gitignore`): `checkpoints/`, `dataset/`, `logs/`, `__pycache__/`, `*.pt`
> (eccezione: i 4 `champions/**`). I dati vengono rigenerati a runtime dal generatore.

## 4. Notebook (nella root)

I 48 `*.ipynb` restano nella root perché **importano `core/`, `data/`, `utils/` e leggono
`results/` con path relativi**: vanno quindi eseguiti con Jupyter **lanciato dalla root del
repo** (cwd = root). Sono raggruppati per famiglia di studio:

- `Training_File*` — addestramento base e sweep architetturali.
- `Prodigy_*`, `Loss_Study_*`, `Dynamic_Study_*`, `EventProp_*` — gli studi (chiusi) dell'ottimizzatore,
  della loss, dei parametri dinamici a/b, di EventProp. Log e verdetti in `document/` e `results/`.
- `Eval_v3_TURTLE_POWER.ipynb`, `Eval_FPGA.ipynb` — producono le run in `results/evaluate/` da cui
  la terna di `report/` estrae numeri e figure.
- `Simulator_Visual.ipynb` — visualizzazione del simulatore closed-loop.

## 5. Come si usa

```bash
# addestramento (da root; device auto in config.py)
python train.py --epochs 20 --tag A1 --scheduler cosine

# valutazione post-training
python eval_report.py --checkpoint checkpoints/<tag>/best_model.pt --n_test 500

# rigenerare la terna di report (md + pdf, in report/)
python scripts/build_how_it_works_v3.py
python scripts/build_validation_report_v3.py
python scripts/build_fpga_report.py
```

## 6. Track paralleli (git worktree)

Il progetto avanza su più tracce isolate (vedi memoria `cf-fsnn-parallel-tracks`):

- **`main` / EventProp_Study** — training a gradiente esatto (master: `document/EVENTPROP_STATUS.md`).
- **worktree `Simulator`** — simulatore ACC-IIDM riusabile.
- **worktree `Simulink_Importer`** — import checkpoint → Simulink → HDL (fase FPGA; nel worktree
  vivono `document/HDL_PHASE.md` e `document/SESSION_RESUME.md` propri).

## 7. Riferimenti principali

- Treiber & Kesting, *Traffic Flow Dynamics: Data, Models and Simulation*, 2ª ed., Springer 2013
  (IDM/IIDM, CAH/ACC, calibrazione, string stability, diagramma fondamentale).
- Wunderlich & Pehle 2021 (EventProp) · Neftci et al. 2019 (surrogate gradient) ·
  Bellec et al. 2018 (ALIF/LSNN) · Raissi et al. 2019 (PINN) · Horowitz 2014 (energia AC/MAC).
- Bibliografie complete (fonti verificate) in coda a ciascun documento di `report/`.
