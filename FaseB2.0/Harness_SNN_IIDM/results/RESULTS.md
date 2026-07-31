# T7a — Harness_SNN_IIDM: anello chiuso RTL + metriche

> Rigenerabile con `run_harness_snn_iidm('full')` — 60.3 min.
> DUT **`Donatello_SNN_IIDM`** (Tier@BALANCED + align + ACC-IIDM R17), generato in
> **Verilog**, 99 scenari x 600 control-step. `HOLD_RTL`=600, `HOLD_BLK`=700 (latenza misurata 554).

## Cancelli

| Cancello | Che cosa prova | Perimetro | Esito |
|---|---|---|---|
| **PLANT-PAR** | plant del TB == `qz_cl_sim`, **senza DUT** | 99 scenari | **0 disallineamenti** |
| **T7-EXACT** | RTL == **BLOCCO** sugli ingressi ricevuti | 58522 confronti | **0 disallineamenti** |
| PARAM-RANGE | i 5 parametri nei limiti del decode | 58522 control-step | **0 fuori dominio** |
| **T7-SAFE** | collisioni AGGIUNTIVE vs oracolo | 99 scenari | **0 extra** |

Ogni cancello e' **provato sensibile** (`sensitivity_t7`).
PLANT-PAR e T7-EXACT **non condividono** il componente che l'altro verifica: il primo gira
senza DUT, il secondo senza plant. Insieme coprono l'anello senza circolarita'.

## Sicurezza

Collisioni: RTL **3**, oracolo **3** su 99 scenari — **0 aggiuntive**.
Le collisioni presenti anche nell'oracolo sono **inevitabili** (cut-in aggressivo):
un controllore a conoscenza perfetta le subisce ugualmente.

## Diagnostica NO-REPEAT — comportamento del blocco, non un difetto dell'RTL

**15494 control-step su 58522 (26.5 %)** hanno i 5 parametri identici al precedente. In quei passi
`align` non rilascia i nuovi ingressi fisici e l'ACC non ricalcola: l'accelerazione resta
**congelata** — verificato nel **100 %** dei casi, zero eccezioni.

Non e' un difetto dell'RTL (T7-EXACT e' 0: l'hardware riproduce il blocco esattamente) ed e'
un comportamento **atteso a regime**: e' concentrato negli scenari `static_target` (leader
fermo, 85-87 % dei passi), dove l'ego converge a un equilibrio e i parametri quantizzati
smettono **legittimamente** di cambiare. **53 scenari su 99 non ne hanno affatto** (mediana 0 %).

Impatto misurato rispetto all'oracolo (mediane, scenari congelati vs non congelati):
**la sicurezza e' intatta** — `min_ttc` 0,97x, `max_DRAC` 1,07x, **0 collisioni aggiuntive**;
il costo e' su tracking (`rms_gap_error` 1,37x) e comfort (`rms_jerk` 1,30x).

## Metriche

**31 metriche per scenario**, dal motore canonico `utils/closed_loop_eval`
(lo stesso di VALIDATION_REPORT_v3 e QUANTIZATION_STUDY_REPORT) calcolate sulle serie
**prodotte dall'RTL**, non dal blocco. Dettaglio per scenario: `results/metrics.json`.

## Riferimento del DUT

Il riferimento e' il **blocco composto**, ripilotato sugli ingressi che l'RTL ha
effettivamente ricevuto. Il golden monolitico `acciidm_m_traj` **non e' utilizzabile**:
e' l'estrazione del blocco DEPRECATO `Donatello_ACC_IIDM_M` e diverge dal composto
(385 scarti su 600 control-step, misurato il 2026-07-30).
