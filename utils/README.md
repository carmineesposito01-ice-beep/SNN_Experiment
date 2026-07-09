# utils/ — Toolbox (simulazione, valutazione, profilazione FPGA)

Funzioni di supporto usate da notebook, script di valutazione e generatori di report. Non
contengono il modello (quello è in `core/`) ma tutto ciò che lo circonda.

## Simulazione e valutazione della guida

| File | Contenuto |
|---|---|
| `simulator/` | Il simulatore closed-loop: `engine.py` (dinamica), `metrics.py` (metriche operative/sicurezza), `plots.py`, `anim.py` (animazioni scenari). |
| `closed_loop_eval.py` | Valutazione ad anello chiuso con plant/attrito/canale V2X realistici, contro l'oracolo. |
| `platoon_eval.py` | Valutazione mesoscopica (plotone, string stability) e macroscopica (simulazione ad anello, diagramma fondamentale). |
| `identifiability.py` | Identificabilità dei parametri: matrice di Fisher (FIM), condizionamento, equifinalità, sensibilità causale, naturalisticità (distanza KS). |
| `snn_showcase.py` | "Vetrina" di un episodio (identificazione + guida + spiking) e stime accessorie. |
| `plot_diagnostics.py` | Grafici diagnostici di training (loss, gradienti, spike-rate, scatter parametri). |

## Quantizzazione e profilazione FPGA (Fase A)

| File | Contenuto |
|---|---|
| `quantize.py` | Fixed-point Qm.n e quantizzazione potenze-di-due (po2). |
| `net_diagnostics.py` | Salute della rete: neuroni morti, raggio spettrale ρ(U·V), raster. |
| `weight_profiler.py` | Alfabeto po2 dei pesi, footprint, sparsità del connettoma. |
| `state_profiler.py` | Range dinamico degli stati interni → allocazione dei bit Qm.n. |
| `latency_model.py` | Conteggio operazioni per tick → WCET/timing (deadline 100 ms). |
| `seu_inject.py` | Fault-injection software dei Single-Event-Upset (bit-flip nei pesi po2). |
| `io_hil.py` | Modello del canale V2X e delle code (PDR/latenza/AoI, hold-last handler). |
| `champion_io.py` | Caricamento robusto dei checkpoint champion (schema-detection), condiviso con il simulatore e l'importer Simulink. |

Questi profilatori alimentano `scripts/fpga_figures.py` e quindi `report/FPGA_REPORT`.
