# Harness_SNN_IIDM (Fase B2.0 · T7a) — anello chiuso RTL + metriche

Valida in RTL il **controllore car-following completo** sui **99 scenari** esaustivi e ne produce le
**31 metriche** di car-following, calcolate sulle serie **prodotte dall'RTL**.

> **I numeri stanno negli artefatti, non qui:** [`results/RESULTS.md`](results/RESULTS.md) (sintesi),
> `results/metrics.json` (31 metriche per scenario, RTL e oracolo), `results/t7_results.mat`.

## Esecuzione — un comando

```matlab
addpath('FaseB2.0/Harness_SNN_IIDM');
run_harness_snn_iidm('smoke')   % 3 scenari (normale · cut-in · collisione), pochi minuti
run_harness_snn_iidm('full')    % tutti i 99
```

Prerequisito, una volta sola (rigenera l'RTL dal blocco):
```matlab
addpath('matlab'); rtl_gen_dut('Donatello_SNN_IIDM','C:/t7hdlv','Verilog')
```

## DUT

**`Donatello_SNN_IIDM`** = `Donatello_Tier@BALANCED/nfrac13` (SNN estimatrice) + `align` (ritardo-appaiato)
+ `ACC-IIDM` (R17). I/O: `s,v,dv,v_l → accel`. Latenza **misurata 554 clock**.

⚠️ **Generare in VERILOG, non VHDL.** Il testbench legge i 5 parametri come segnali interni del top, e un
TB Verilog che accede a segnali interni di un DUT **VHDL** fa **crashare `xelab`**
(`EXCEPTION_ACCESS_VIOLATION`, `HDL_PHASE` §9.10bis).

⚠️ **Il composto non si pilota mai con ingressi costanti**: `align` rilascerebbe valori identici a quelli
tenuti, le sue uscite non cambierebbero e l'ACC non vedrebbe alcun fronte.

## Come si verifica l'anello — due prove che non si sovrappongono

| Cancello | Che cosa prova | Come |
|---|---|---|
| **PLANT-PAR** | il plant del TB ≡ `qz_cl_sim` | pilotato con la sequenza `accel` dell'**oracolo**, **senza DUT** |
| **T7-EXACT** | il DUT ≡ il **blocco** | il blocco ripilotato sugli ingressi che l'RTL ha **davvero ricevuto**, **senza plant** |

Plant corretto + DUT corretto ⇒ traiettoria corretta. Le due prove **non condividono** il componente
verificato dall'altra, quindi non c'è circolarità.

Altri cancelli: **PARAM-RANGE** (i 5 parametri nei limiti del decode), **NO-REPEAT** (parametri mai
ripetuti ⇒ `align` mai stantio), **T7-SAFE** (0 collisioni **aggiuntive** rispetto all'oracolo — l'unico
cancello duro sulle metriche).

Ogni cancello è **provato sensibile** (`sensitivity_t7`), su un solo scenario anche in `'full'`: la
sensibilità è una proprietà del cancello, non del dataset.

## ⚠️ Il riferimento del DUT è il BLOCCO, non `acciidm_m_traj`

`acciidm_m_traj` è l'estrazione verbatim del blocco **MONOLITICO DEPRECATO** `Donatello_ACC_IIDM_M` e
**non è equivalente al composto**: **385 scarti su 600** control-step di una traiettoria reale, primo al
passo 195. L'equivalenza era stata provata solo su 4 control-step (T5) e 6 (P4). Prova decisiva, stessa
sequenza di ingressi: blocco vs RTL **0**, blocco vs monolitico **385**, RTL vs monolitico **385**.

## Metriche

Motore **canonico** `utils/closed_loop_eval.all_metrics()` (Python), non riscritto: lo stesso che ha
prodotto `VALIDATION_REPORT_v3` e `QUANTIZATION_STUDY_REPORT` ⇒ numeri confrontabili per costruzione.
30 chiavi + `string_stability_gain` = **31**.

☠️ Il contratto è di **9 chiavi** e una fallisce in silenzio: `impact_dv` è letta con
`traj.get('impact_dv', 0.0)`, quindi ometterla restituisce **0** — «collisione a severità nulla» per una
collisione reale (valore vero misurato: 5,39 m/s). `t7_metrics.py` **asserisce** tutte e nove.

**Fuori perimetro:** la *naturalisticità* (KS su time-gap e jerk) opera sul modello PyTorch e su una cache
di guidatori, non su serie di anello chiuso: è coperta a monte da `VALIDATION_REPORT_v3` (T4).

## File

| File | Ruolo |
|---|---|
| `run_harness_snn_iidm.m` | **entry-point unico** (`'smoke'` \| `'full'`) |
| `t7_step_oracle.m` · `t7_oracle_cache.m` | oracolo: `accel` per PLANT-PAR + baseline delle metriche |
| `t7_export_scenarios.m` | scenari → `.mem` (bit pattern IEEE-754) |
| `tb_plant_only.v` · `t7_plant_par.m` | PLANT-PAR (plant senza DUT) |
| `tb_snn_iidm_closed.v` | anello live: plant + DUT + export delle serie |
| `t7_read_series.m` · `t7_hexread.m` | lettura delle serie (⚠️ `hex2num`, **non** `hex2dec`) |
| `t7_block_replay.m` · `t7_rtl_validate.m` | riferimento (il blocco) e cancelli |
| `t7_series_to_mat.m` · `t7_metrics.py` | metriche dal motore canonico |
| `sensitivity_t7.m` | prove di sensibilità dei cancelli |
| `../common/rtl_run_plant_par.sh` · `rtl_run_xsim_closed.sh` | runner (work-dir corta, compila una volta) |

## Trappole già pagate

- **`hex2dec` perde precisione oltre 2⁵³** ⇒ distrugge il confronto bit-esatto in modo silenzioso
  (dava 2241/2400 su un plant corretto). Usare `hex2num` — isolato in `t7_hexread`.
- **Macro al TB via file `.vh`**, mai `-d NOME=val`: il wrapper Git-Bash→`.bat` mangia l'`=`.
- **Work-dir senza spazi**: il repo sta sotto `.../1.Reti Neurali/...` e `glob`/`add_files` si spezzano.
- **Una simulazione xsim per scenario**: lo stato SNN vive nella `hdl.RAM` e si azzera solo all'init.
