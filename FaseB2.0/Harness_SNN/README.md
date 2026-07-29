# Harness_SNN (Fase B2.0 · T6a) — validazione RTL di `Donatello_Tier@BALANCED`

Prova che il **VHDL generato** del blocco SNN riproduce **bit-exact il blocco** in Vivado xsim, sul dataset dei 60,
e ne riporta l'accuratezza di stima dei 5 parametri IDM.

**DUT:** `Donatello_Tier` @ **TIER=BALANCED, NFRAC=13** (libreria `matlab/snn_champions_lib.slx`).
**Golden:** il **blocco stesso** (oracolo `matlab/tier_block_params.m`, girato in Simulink), calcolato **una volta**
e messo in cache (`matlab/tier_golden_cache.m`) → **prova RTL e metriche usano gli stessi identici dati**.

## Come rilanciare TUTTO (un comando)

```bash
"C:/Program Files/MATLAB/R2026a/bin/matlab.exe" -sd "<questa cartella>" -batch "run_harness_snn"
```

Esegue: VHDL (se assente) → golden in cache → **T6-EXACT su tutte le 60** → sensibilità → metriche → `results/`.
**Runtime ~75 min** (≈28 min golden + ≈45 min xsim). Job lungo: lanciarlo in background e **lasciarlo finire**.

Gate rapido di sviluppo: `run_harness_snn('smoke')` (subset diversificato, ~15 min).
⚠️ **I numeri riportabili sono solo quelli di `full`**: prova e metriche devono coprire **lo stesso perimetro**
(su popolazioni diverse i numeri non sono appaiabili e lo scostamento non è leggibile, nemmeno se è 0).

## Prodotti

| Percorso | Contenuto |
|---|---|
| `results/RESULTS.md` | tabella cancelli + configurazione misurata + metriche (**la fonte dei numeri per i report**) |
| `results/harness_snn_results.mat` | struttura completa (`rtl`, `sens`, `metrics`, `golden`, tempi) |
| `../../matlab/golden_tier_bal.mat` | cache golden (gitignorata, rigenerabile) |
| `../../matlab/hdlsrc_donatello_tier/rtlgen_mdl/` | VHDL generato (gitignorato, rigenerabile) |
| `D:/zbd_tier/` | artefatti xsim + `.mem` (fuori dal repo: work-dir **corta, senza spazi**) |

## Cancelli

| Cancello | Cosa prova |
|---|---|
| **T6-EXACT** | RTL 5 param == blocco (`nMismatch==0`). Copre **PORT-TYPE**: un tipo ≠ `Q7.13` darebbe mismatch sistematico |
| **LAT** | latenza RTL **misurata** dal TB (364 clock = latenza blocco) `< HOLD=500` |
| **Sensibilità** | 1 LSB corrotto sul golden → `nMismatch ≥ 1` (il cancello non è cieco) |

## Prerequisiti

MATLAB R2026a + HDL Coder · Vivado 2026.1 in `C:/AMDDesignTools/2026.1` · Git-Bash (per il runner xsim).

## Note d'implementazione (lezioni HDL — non ri-scoprirle)

- Il DUT è un **Variant Subsystem mascherato**: `find_system` **non guarda sotto la mask** → `rtl_gen_dut` usa
  `get_param(blk,'Ports')` e **salva il modello prima dell'update** (risolve la variante). Il 4° argomento
  `maskParams` forza `TIER`/`NFRAC` → `makehdl` genera **solo** la variante scelta.
- **Ordine di compilazione VHDL bottom-up**, letto dal **log di `makehdl`** (`pkg → DEC → DualPortRAM → SNN →
  BALANCED_n13 → VS → Donatello_Tier`): alfabetico non funziona (gerarchia profonda).
- Lo **stato SNN vive nella `hdl.RAM` (DualPortRAM)**: il `reset` a runtime **non la azzera**, solo l'init di una
  simulazione → **una simulazione xsim per traiettoria** (il runner compila una volta e cicla).
- Ingressi a **≥20 bit frazionari** (`fixdt(1,32,20)`): sotto, ~1 spike flippato ogni ~25 step.

## File

`run_harness_snn.m` (entry-point) · `run_rtl_validate_tier.m` (T6-EXACT + LAT) · `sensitivity_t6.m` ·
`tier_rtl_metrics.m` · `tier_export_vectors.m` · `subset_diverse.m` · `tb_tier_stream.v` · `test_tier_export.m` ·
`probe_golden_cost.m`. Condivisi: `../common/{rtl_write_vectors.m, rtl_run_xsim.sh}`.
Golden/gen HDL: `../../matlab/{tier_block_params.m, tier_golden_cache.m, rtl_gen_dut.m}`.
