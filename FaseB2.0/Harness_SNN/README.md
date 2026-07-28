# Harness_SNN (T6a) — validazione RTL di `Donatello_Tier@BALANCED`

DUT: `Donatello_Tier` @ **TIER=BALANCED, NFRAC=13**. Golden = **il blocco stesso** (`matlab/tier_block_params.m`,
girato in Simulink). Work-dir xsim: **`D:/zbd_tier`** (ROOT corta, SENZA spazi — il repo sta sotto `1.Reti Neurali`).
Utilità condivise: `../common/{rtl_write_vectors.m, rtl_run_xsim.sh}`. VHDL generato: `../../matlab/hdlsrc_donatello_tier/rtlgen_mdl/`.

## Comandi (da questa cartella, `matlab -sd . -batch "..."`)
- **Genera VHDL** (in `matlab/`): `rtl_gen_dut('Donatello_Tier',[],'VHDL',{'TIER','BALANCED','NFRAC','13'})`
- **T6-EXACT (subset)**: `run_rtl_validate_tier('reduced')`
- **Sensibilità**: `sensitivity_t6()`
- **Full-60** (dopo probe): `probe_golden_cost` → `run_rtl_validate_tier('full')`
- **Metriche di stima**: `tier_rtl_metrics(1:60)`

## Cancelli
- **T6-EXACT**: RTL 5 param == blocco (`nMismatch==0`), subset e full-60. Copre **PORT-TYPE** (un tipo di uscita
  diverso da `Q7.13` darebbe mismatch sistematico ≠ 0).
- **LAT**: latenza RTL misurata dal TB (= **364** clock, == blocco) `< HOLD=500`.
- **Sensibilità**: 1 LSB corrotto sul golden → `nMismatch ≥ 1` (il cancello non è cieco).

## Note d'implementazione (perché così)
- Il DUT è un **Variant Subsystem** mascherato → `rtl_gen_dut` usa `get_param('Ports')` (non `find_system`, che non
  guarda sotto la mask) e **salva il modello prima dell'update** (risolve la variante).
- L'**ordine di compilazione** VHDL è **bottom-up** (dal log di `makehdl`: `pkg → DEC → DualPortRAM → SNN → BALANCED_n13
  → VS → Donatello_Tier`), non alfabetico: il Tier è gerarchico (`VS → BALANCED_n13 → {SNN→DualPortRAM, DEC}`).
- xsim gira in `D:/zbd_tier` (i sorgenti VHDL + TB + `.mem` vengono copiati lì); i path passati a bash sono convertiti a forward-slash.

## Prodotti
- `D:/zbd_tier/` (fuori dal repo): `stim_*.mem`, `gold_*.mem`, `hdl/`, `xsim.dir/` — rigenerabili.
- `results/full60.log` (tenuto): esito del full-60.
- `../../matlab/hdlsrc_donatello_tier/` (gitignorato): VHDL generato.
