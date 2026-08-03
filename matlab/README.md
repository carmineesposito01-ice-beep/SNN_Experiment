# `matlab/` — libreria HDL SNN car-following + build/verifica

Contiene la **libreria di blocchi** Simulink (`snn_champions_lib.slx`), i **sorgenti** che i blocchi
inglobano, i **builder** che li costruiscono, i **gate** che li verificano e i **generatori** di supporto.
Ogni blocco esiste in doppia precisione (riferimento) e/o fixed-point (HDL-ready).

I file restano "piatti" per una ragione tecnica: i builder e i gate leggono sorgenti e dataset con
`fullfile(here, 'X')` dove `here` = questa cartella → spostarli romperebbe i path. L'ordine lo danno
**questo README** (mappa per convenzione di nome) e le sottocartelle tematiche.

**Eseguire MATLAB (non interattivo):** `"C:\Program Files\MATLAB\R2026a\bin\matlab.exe" -batch "<comando>"`

---

## La libreria — `snn_champions_lib.slx`
Blocchi self-contained, I/O **fisico** `s,v,dv,v_l`, edge-triggered (1 cambio ingressi = 1 inferenza), HDL-ready.
Categorie:
- **Campioni comportamentali** (double, riferimento): `Donatello` · `Leonardo` · `Michelangelo` · `Raffaello`.
- **Estimatori SNN** (HDL, fixed): `Donatello_LUT` (popup NLUT = punti LUT decode) · `Donatello_Tier`
  (tier SLOW/BALANCED/FAST × nfrac + Modalità Avanzata).
- **Controllore IIDM standalone** (HDL): `ACC-IIDM` (9 ingressi: 4 fisici + 5 params → accel).
- **Controllore completo** (HDL): `Donatello_ACC_IIDM_M` (SNN+IIDM in un blocco).

La spiegazione completa di ogni blocco è nella sua **Description** (Block Properties / mask).

## Sorgenti inglobati (i `.m` che le chart leggono a build-time)
I builder li leggono e li appendono come funzioni locali → i blocchi girano/generano VHDL senza `.m` esterni.
- **SNN forward**: `snn_b2_fsm.m` (core time-mux) · `snn_types.m` (tipi Qm.n) · `b2_rom_active.m` (ROM pesi, *generata*).
- **Decode**: `snn_decode_lut.m` · `decode_a*/b*/c*.m` (fasi) · `snn_decode_hdl.m`.
- **IIDM**: `acc_iidm_open.m` (matematica) · `acc_types.m` (tipi) · `iidm_*.m` (fasi prep/nd/use/tanh/final/ab/sabx)
  · `div_seq_*.m` + `sqrt_seq_*.m` (divisore/radice sequenziali) · `iidm_r17_chart_code.m` (chart ACC-IIDM)
  · `tanh_lut_full.m` (*generata*).
- **Normalize** fisico→`xn`: incluso nei chart-code dei builder.

## Builder — `build_*.m` (+ funzioni di montaggio condivise)
- `build_library.m` → i 4 Campioni double.
- `build_hdl_variants.m` → `Donatello_ACC_IIDM_M` (+ i singoli storici Champion/LUT/ACC_IIDM, poi rimossi).
- `build_lut_configurable.m` → `Donatello_LUT` (combinato, architettura splitpipe).
- `build_tier_configurable.m` → `Donatello_Tier`.
- `build_acc_iidm_block.m` → `ACC-IIDM`.
- `reorg_library.m` → riordina la libreria al set-milestone (rimuove i singoli assorbiti).
- `finalize_descriptions.m` → applica le descrizioni concise ai blocchi.
- **Condivise**: `snn_chart_code.m` · `dec_chart_code.m` · `mount_split.m` · `decode_phase_code.m` · `champ_description.m`.
- ⚠️ **Workflow**: `build_hdl_variants` RI-AGGIUNGE i singoli → esegui SEMPRE `reorg_library` subito dopo.

## Gate / runner — `run_*.m` (verifiche, **sempre sul dataset**)
- `run_lib_dataset_test.m` → tutti i blocchi vs riferimento sul dataset (banco `snn_lib_dataset_test.slx`).
- `run_milestone_hdl_gates.m` → HDL self-contained (`makehdl`, `matlab/` fuori path) per i blocchi HDL.
- `run_block_hdl_gate.m` → gate HDL self-contained di un singolo blocco.
- `run_lut_ref_gate.m` → `Donatello_LUT` bit-exact al riferimento (tutti gli N).
- `run_block_traj_test.m` · `run_block_acciidm_m_test.m` · `run_iidm_r17_func_gate.m` → funzionali per-blocco.
- `run_b2_parity_dataset.m` → parità forward vs core sul dataset.
- *Regola: un gate **asserta** e va **provato sensibile** (rompilo apposta). Vedi `../document/HDL_PHASE.md` §2.1.*

## Generatori — `gen_*.m`
`gen_b2_rom` (ROM pesi del champion attivo) · `gen_tanh_lut` (LUT tanh) · `gen_r17_vhdl` / `gen_acciidm_m_vhdl`
(VHDL di un blocco per la sintesi) · `gen_hdl_tops`.

## Dataset (`.mat`)
- `test_dataset.mat` (60 traj) · `test_trajectories.mat` (6 traj, con `ref_params` Python) · `champions_export.mat` (pesi/norm/golden).
- **L'ultimo generato** (esaustivo, 99 traj / 9 scenari con cut-in/cut-out): `Quantizzation_Study/test_dataset_exhaustive.mat` (rif. params `mp_ref13_1_99.mat`).

## Sottocartelle
- `snn_variants/` — snapshot del forward per i tier (`snn_b2_fsm_R2/R5/R9`).
- `study_tradeoff/` · `Quantizzation_Study/` · `Quantizzation_Study_IIDM/` — studi (trade-off Blocco A, quantizzazione rete, quantizzazione IIDM) coi loro dati.
- `axi/` — bitstream + cosim AXI (PYNQ-Z1).
- `archive/` — investigazioni una-tantum (`probe_*`/`check_*`/`diag_*`), **non parte della pipeline**.
- **Generate/gitignored**: `codegen/` · `slprj/` · `hdl_*/` · `hdlsrc_*/` (RTL rigenerabile).
- `../FaseB2.0/` — harness di validazione RTL (SNN e SNN+IIDM) → vedi il suo README.

## Ricette (how-to)
- **Ricostruire la libreria**: `build_library; build_hdl_variants; reorg_library; build_lut_configurable; build_tier_configurable; build_acc_iidm_block; finalize_descriptions`.
- **Verificare che tutto funzioni**: `run_lib_dataset_test(1,20,600)` poi `run_milestone_hdl_gates`.
- **VHDL di un blocco per la sintesi**: `gen_r17_vhdl` (ACC-IIDM) · `gen_acciidm_m_vhdl` (controllore completo).
- **Sintesi OOC (Vivado)**: `vivado -mode batch -source scripts/synth_acc_iidm.tcl -tclargs <srcdir> <outdir> <label>`
  da una work-dir **senza spazi** (la tcl usa `glob`; i path con spazi falliscono → copia lì il VHDL).

> ⚠️ **Non toccare** `closed_loop_demo.slx` e `slblocks.m` (file dell'utente).
