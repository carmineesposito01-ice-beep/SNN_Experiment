# EVALUATE UPGRADE — piano + checklist master (da validazione data-driven a physics/network-driven)

> **Scopo**: tracciare l'upgrade dell'`evaluate` (closed-loop) sui 6 livelli del framework + metodologia + hardware,
> implementato **per Tier in ordine**, in modo da **non perdere nessun item** della gap-analysis.
> Aggiornare le caselle man mano. Ogni riga porta il `ref` LX della gap-analysis (tracciabilita').

## Principi (NON violare)
- **Backward-compat / opt-in**: ogni aggiunta ha default = comportamento attuale. Le 4 chiavi legacy di
  `eval_safety` (`collision_rate, mean_min_gap, mean_max_decel, mean_rms_jerk`) + `id_abs_err` restano INTATTE
  (le legge lo Stadio-2 ckpt-pass su Azure e il notebook BigSweep3). Le metriche ricche stanno dietro `rich=True`.
- **Metrica PRIMARIA = fisica** (`val_data` / accel); NRMSE e SSM = lenti. Mai giudicare sull'NRMSE da solo.
- **Riuso**: estendere `utils/closed_loop_eval.py` (metriche per-traiettoria) e `scripts/closed_loop_identify.py`
  (aggregazione), NON riscrivere. `simulate()` resta il cuore.
- **Documentare man mano** (questo file) + test per ogni Tier. **Niente push finche' Azure (Stadio-2) gira.**

## Verita' guida emerse dall'audit
- `bigsweep3_closedloop.csv`: `collision_rate=0` OVUNQUE → la metrica primaria attuale e' **satura, zero discriminazione**.
- `max_decel ~ 4 m/s²` SUPERA gia' la soglia ISO 15622 (−3.5) → segnale gia' nei dati, non flaggato.
- SSM ricche gia' calcolate in `closed_loop_eval.py:97-150` ma **scartate** da `_agg` (4 medie, 1 seed).
- Rumore OU + packet-loss modellati in `generator.py` ma **mai iniettati in `simulate()`** (gap validita' esterna).

---

## TIER 0 — Fondazione di reporting *(la base attraverso cui passano tutti i Tier successivi)* ✅ FATTO
> Implementato in `utils/closed_loop_eval.py` (flag ISO in `comfort_metrics`) + `scripts/closed_loop_identify.py`
> (`_summarize/_wilson_ub/_bootstrap_ci/_agg_rich`, `eval_safety(rich=False, n_seeds=1)`). Test: `tests/test_eval_tier0.py` (verde).
> **Uso**: `eval_safety(model, cache, rich=True)` → aggiunge `out['rich']` (distribuzioni, per-scenario+worst-case,
> Δ SNN-oracolo+CI, Wilson, intra_std). `rich=False` = comportamento legacy INVARIATO (Azure ckpt-pass / BS3 intatti).
- [x] **T0.1** `L2.surfacing`/`L2.ssm` — far emergere TTC/TET/TIT/DRAC/min_time_headway/gap_error/string_gain (gia' calcolate, scartate da `_agg`)
- [x] **T0.2** `L2.distrib`/`L3.statistics` — distribuzioni: mean/std/p5/p50/p95/p99/min/max per ogni metrica
- [x] **T0.3** `extra:Wilson` — intervallo di Wilson (UB95) sul `collision_rate` (0/n ≠ 0 reale)
- [x] **T0.4** `extra:bootstrap` — CI bootstrap del Δ (SNN−oracolo) appaiato = test di **non-inferiorita'**
- [x] **T0.5** `extra:per-scenario` — stratificazione per scenario + **worst-case** (no media trasversale)
- [x] **T0.6** `L2.jerk_ISO`/`L2.comfort` — flag ISO 15622 in `comfort_metrics` (max|jerk|, frac |jerk|>2, decel<−3.5, accel>2)
- [x] **T0.7** `audit:oracle-gate` — gate **oracolo-relativo** (`delta_snn_minus_oracle` con CI)
- [x] **T0.8** `audit:intra_std` — `intra_std` dell'identificazione (std su T di `forward_sequence`) come gate di stabilita'
- [x] **T0.9** `audit:multi-seed` — `n_seeds` opt-in per CI riproducibili (default 1 = legacy)

## TIER 1 — Scenari di coda + soglie + efficienza + energia ✅ FATTO
> `utils/closed_loop_eval.py`: `build_scenarios(include_tail=True)` (+4 scenari), soglie in `safety_metrics`
> (DRAC/TTC/CPI), `energy_proxy` in `comfort_metrics`, steady-state in `tracking_metrics`.
> `scripts/closed_loop_identify.py`: `eval_safety(tail=True)` + rollout RMSE/braking-dist, `make_ood_cache()`,
> `breakdown_curve()`. Test esteso (verde). Default (`tail=False`) = legacy invariato.
- [x] **T1.1** `L6.cut_out` — leader veloce → ostacolo fermo (v=0) rivelato tardi (TTC~2s)
- [x] **T1.2** `L6.static_target` — target statico permanente (v_leader≡0; punto di rottura ISO 15622)
- [x] **T1.3** `L6.panic_stop` — panic stop a −B_MAX (−9 m/s²)
- [x] **T1.4** `L6.aggressive_cut_in` — cut-in gap~3m (TTC~0.5s), leader 0.30·v0 → DRAC→B_MAX
- [x] **T1.5** `L6.ood_params` — `make_ood_cache()`: param oltre/ai bordi `_PHYS_BOUNDS` (beyond, edge)
- [x] **T1.6** `L6.extra:breakdown` — `breakdown_curve()`: sweep decel {5..10} e gap cut-in {8..2}, collision oracolo-vs-SNN
- [x] **T1.7** `L2.DRAC` — `frac_drac_critical` (>3.35) + `TED_drac`/`TID_drac` + `cpi` (proxy MADR medio 8.45; raffinabile a MADR stocastico)
- [x] **T1.8** `L2.TTC` — `frac_ttc_below_{1.0,1.5,2.0,3.0}`
- [x] **T1.9** `L2.deltav_eff` — `mean_abs_dv_ss` + `mean_abs_gap_err_ss` (ultimo 50%)
- [x] **T1.10** `L1.rmse_accel` — `rich.rollout.rmse_accel/mae_accel` (rollout SNN-vs-oracolo, non teacher-forcing)
- [x] **T1.11** `L1.braking_dist` — `rich.rollout.braking_dist_err` per scenario di arresto
- [x] **T1.12** `L4.energy_comfort` — `energy_proxy` (load-based ∫max(0,v·a)); bande ISO 2631 derivabili da `rms_accel`

## TIER 2 — Plant fisico (L4) + degradazione V2X (L3) in closed-loop ✅ FATTO
> `utils/closed_loop_eval.py`: `_plant_step` (L4), `_channel_obs` (L3), `param_chattering`, e
> `simulate(plant=None, channel=None)` (default = legacy identico, verificato dal test).
> `scripts/closed_loop_identify.py`: `eval_safety(plant=, channel=)` passthrough, `v2x_robustness_sweep()`,
> `cbr_to_pdr()`. Il canale degrada solo la PERCEZIONE del leader; la fisica usa vl VERO.
- [x] **T2.1** `L4.actuator_lag` — `plant={'tau_act':0.3..0.5}` (lag 1° ordine su a_cmd)
- [x] **T2.2** `L4.friction_limit` — `plant={'mu':0.9/0.45/0.18}` → clip a ±μ·g
- [x] **T2.3** `L4.grade` — `plant={'grade':θ}` → −g·sinθ
- [x] **T2.4** `L4.drag_rolling` — `plant={'drag':True, Cd,A,m,Crr}` → ½ρCdAv²+rolling
- [x] **T2.5** `L4.plant_module` — `_plant_step()` unificato; **ablation** = eval con `plant=None` vs `plant={...}`
- [x] **T2.6** `L4.extra:plant_in_eval` — `eval_safety(plant=...)` → simulate (ramo identificato/EventProp)
- [x] **T2.7** `L4.extra:jerk_limiter` — `plant={'jerk_max':...}`
- [x] **T2.8** `L4.extra:asym_tau` — `plant={'tau_brake':..,'tau_throttle':..}`
- [x] **T2.9** `L3-01` — `channel={'pdr':..}` hold-last-CAM (+ `{'gilbert':(p_bad,p_good)}` burst)
- [x] **T2.10** `L3-02` — `channel={'latency_steps':k,'jitter_steps':j}` (buffer FIFO ritardato)
- [x] **T2.11** `L3-03` — `channel={'sensor_noise_scale':..}` (OU su gap/vel, riusa NOISE_* di config)
- [x] **T2.12** `L3-04` — `v2x_robustness_sweep()` → collision_rate + min_ttc_p5 vs PDR/latenza (curva = knee)
- [x] **T2.13** `L3-05` — `param_chattering()` (std + frazione energia FFT >0.5Hz per canale)
- [x] **T2.14** `L3-06` — `simulate()` ritorna `aoi_mean`/`aoi_max` (Age-of-Information) quando channel attivo
- [x] **T2.15** `L3.extra:adversarial_loss` — `channel={'blackout_steps':(t0,t1)}` (loss forzato sull'evento)
- [x] **T2.16** `L3.extra:DCC_CBR` — `cbr_to_pdr(density)` (proxy DCC densità→CBR→PDR)

## TIER 3 — String stability macroscopica (L5)
- [ ] **T3.1** `L5.platoon` — catena N=5-10 follower (ego_i → leader di i+1), head-to-tail gain
- [ ] **T3.2** `L5.freq_sweep` — sweep |Γ(ω)| (banda 0.005-0.5Hz) + criterio max_ω|Γ|≤1; **chirp+FFT** invece di K sinusoidi
- [ ] **T3.3** `L5.L2_Linf` — norme L2/Linf (strict string stability) oltre allo std-ratio
- [ ] **T3.4** `L5.distributions` — plotone **eterogeneo** (param identificati diversi) + CI
- [ ] **T3.5** `L5.local_proxy` — rinominare/promuovere lo std-ratio attuale a caso N=1 (non confonderlo con string stability)
- [ ] **T3.6** `L3-08`/`L5.extra:v2x` — latenza CAM **dentro** il plotone (destabilizzazione)
- [ ] **T3.7** `L5.extra:spacing` — mappa T identificato → regione string-stabile IIDM

## TIER 4 — Metodologia profonda (identificabilita', calibrazione, formale)
- [ ] **T4.1** `L1.identifiability` ⭐ — FIM/Jacobiano (cond, autovettori piatti); correla cond(FIM) ai casi ProdigyEvent
- [ ] **T4.2** `extra:equifinality` — enumerare param I/O-equivalenti lungo gli autovettori piatti
- [ ] **T4.3** `extra:excitation` — persistent excitation: gli scenari eccitano tutti i 5 param? (rango FIM cumulata)
- [ ] **T4.4** `L1.causal_sensitivity` — corr param-predetti vs stato-CAM (dT/dvar(vl)>0?) = logica vs overfitting
- [ ] **T4.5** `L2.calibration_protocol` — gap come MoP primaria + holdout temporale + floor intra/inter-driver (8-12%/12-32%)
- [ ] **T4.6** `audit:nrmse_stratified` — NRMSE stratificato per regime/scenario (smaschera param non identificabili)
- [ ] **T4.7** `L5.formal_safety` — reachability/worst-case set-based (frontiera regione safe) [high]
- [ ] **T4.8** `extra:naturalisticity` — Wasserstein/KS time-gap & jerk SNN vs driver reali

## TIER 5 — Validita' hardware (FPGA)
- [ ] **T5.1** `L6.fpga` — quantizzazione fixed-point (fake-quant pesi+readout) → Δ NRMSE + closed-loop float-vs-quant
- [ ] **T5.2** `L3.extra:fixedpoint_twin` — quantizzazione combinata con degradazione V2X (validita' esterna hardware completa)

---

## Deliberatamente NON implementati (con motivazione)
- `L2.PET` — nel car-following 1D **PET ≡ time-headway** (gia' calcolato; Do et al. 2025). Aggiungerla = ridondanza.
  Azione: documentare nel docstring perche' si usa TTC+DRAC (standard rear-end).
- `L4.extra:friction_ellipse` — accoppiamento long/lat non implementabile in 1D; **solo nota** che il clip −μg
  assume guida rettilinea (zero domanda laterale).

## Stato Tier
| Tier | Titolo | Stato |
|---|---|---|
| 0 | Fondazione reporting | ✅ fatto (test verde) |
| 1 | Scenari coda + soglie + energia | ✅ fatto (test verde) |
| 2 | Plant L4 + V2X L3 | ✅ fatto (test verde) |
| 3 | String stability L5 | da fare |
| 4 | Metodologia (identificabilita') | da fare |
| 5 | Hardware FPGA | da fare |
