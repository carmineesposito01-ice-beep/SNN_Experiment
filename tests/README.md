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

I test usano i champion versionati in `champions/` (nessun training richiesto) e i moduli di
`core/`, `utils/`. Non dipendono da GPU né da dati esterni.
