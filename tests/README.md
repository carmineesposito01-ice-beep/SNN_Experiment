# tests/ — Suite di test (pytest)

Test automatici delle parti sensibili della pipeline. Eseguire dalla **root** del repo:

```bash
pytest tests/ -q
```

| File | Cosa verifica |
|---|---|
| `test_champion_io.py` | Caricamento robusto dei checkpoint champion (`utils/champion_io.py`, schema-detection). |
| `test_eval_tier0.py` | Il tier-0 dell'evaluate (reporting/accuratezza). |
| `test_fpga_io.py` | Il modello I/O-HIL FPGA (canale V2X, code). |
| `test_fpga_profilers.py` | I profilatori FPGA (pesi, stati, latenza). |
| `test_fpga_seu.py` | La fault-injection SEU (bit-flip nei pesi po2). |
| `presentation/test_figures_common.py` | Le figure comuni della presentazione. |
| `test_export_champions.py` | L'export dei champion verso MATLAB (`scripts/export_champions.py` → `matlab/champions_export.mat`). ⚠️ **rigenera** quel file: dopo averlo eseguito, `git status` lo mostra modificato per la sola data nell'intestazione `.mat`. |
| `test_sim_eventprop.py` | Lo stepper EventProp del simulatore (`sim/eventprop_stepper.py`). |
| `test_sim_platoon.py` | La simulazione di plotone dell'interfaccia (`sim/ui/platoon.py`). |

⚠️ **`test_fpga_io.py`, `test_fpga_profilers.py` e `test_fpga_seu.py` non sono test pytest**: sono
script autonomi che chiamano `sys.exit()` a livello di modulo. Il nome `test_*` fa sì che pytest
provi a raccoglierli e vada in `INTERNALERROR`, quindi `python -m pytest tests` non completa. Si
eseguono a mano (`python tests/test_fpga_io.py`). Per la sola suite pytest:

```bash
python -m pytest tests --ignore=tests/test_fpga_io.py --ignore=tests/test_fpga_profilers.py --ignore=tests/test_fpga_seu.py
```

La **Fase C** ha una suite propria, separata e completa: `cd FaseC && python -m pytest` (230 test).

I test usano i champion versionati in `champions/` (nessun training richiesto) e i moduli di
`core/`, `utils/`. Non dipendono da GPU né da dati esterni.
