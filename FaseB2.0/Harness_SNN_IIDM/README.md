# Harness_SNN_IIDM (Fase B2.0 · T7) — DA FARE

> **Scaffold + requisiti raccolti il 2026-07-29** (durante T6b, mentre si chiariva la divisione fra i due harness).
> Nulla è ancora implementato qui: questo README è il **capitolato** di T7, con gli asset già verificati esistenti.

## DUT

**`Donatello_SNN_IIDM`** (blocco composto della libreria, creato in T4 da `matlab/build_snn_iidm_block.m`):
`Donatello_Tier@BALANCED` + `align` (ritardo-appaiato) + **`ACC-IIDM` R17** — la versione a **~77,9 MHz OOC**
(divisore e radice sequenziali; il 9,30 MHz di SP4 è superato). I/O: `s,v,dv,v_l → accel`.

⚠️ **NON** è il DUT di T6a/T6b (che è la SNN sola, `Donatello_Tier@BALANCED`).

## Dataset — i 99, non i 60

**`matlab/Quantizzation_Study/test_dataset_exhaustive.mat`** (99 scenari = 11 config-veicolo × 9 scenari).
Motivo (deciso dall'utente): scenari **più uniformi** e include i **cut-in aggressivi inevitabili**, quindi è il
dataset adatto a verificare **tutte** le metriche di car-following. È **closed-loop-native** (nessun `val`) → serve
l'anello. Riferimento oracolo closed-loop: **`matlab/Quantizzation_Study/mp_ref13_1_99.mat`** ✅ verificato presente.

*(I 60 di `test_dataset.mat` sono il dataset di T6a/T6b: hanno `val` e 60 config-veicolo distinte, adatti alla rete sola.)*

## Metriche di car-following — DA VALIDARE TUTTE

Fonti: `report/VALIDATION_REPORT_v3.md` §3/§5 (root, branch `main`) · `report/QUANTIZATION_STUDY_REPORT.md` §4
(questo worktree — **già girato sui 99**, quindi i numeri saranno confrontabili).

| Metrica | Significato | Fonte |
|---|---|---|
| **collisioni** + **collisioni AGGIUNTIVE vs oracolo** | sicurezza assoluta; *0 extra* = sicura quanto il controllore a conoscenza perfetta | QZ §4 (3 inevitabili da cut-in aggressivo, uguali all'oracolo) |
| **min_gap** · **min_TTC** | prossimità al pericolo | VAL §5 |
| **brake margin** · **max DRAC** | margine di frenata (`B_max = 9 m/s²`) e decelerazione richiesta | QZ eq. 4.1 |
| **TET / TIT** | tempo ed integrale sotto soglia TTC (esposizione) | VAL §3 |
| **impact Δv / severità** | violenza dell'urto dove è inevitabile (oracolo: 7.69 m/s) | QZ §4 |
| **rms_jerk** · **frac_iso** | comfort (soglia ISO) | VAL §3/§5 |
| **head_to_tail_gain** | string stability (<1 = stabile) | VAL §3 |
| **naturalisticità** (KS su time-gap e jerk) | distanza dalle distribuzioni umane | VAL §4 |

**Riuso, non riscrittura:** `matlab/Quantizzation_Study/qz_safety_metrics.m` ✅ verificato presente
(firma `m = qz_safety_metrics(series, collided, min_gap, impact_dv)`; è la porta di `utils/closed_loop_eval.py`)
→ stesse metriche dei report pubblicati ⇒ **numeri confrontabili**. Baseline = **oracolo**.

## Conseguenza tecnica: serve il plant nel testbench

La validazione RTL è **closed-loop**: l'ego integra e ri-alimenta il DUT. Pattern già collaudato:
**`matlab/axi/acciidm_m/tb_acciidm_m_closed.v`** ✅ verificato presente, col cancello **PLANT-PAR**
(plant == riferimento **senza** RTL, pilotato con la sequenza `accel` del riferimento) che isola i difetti
d'integrazione **prima** dell'anello live. Da adattare al composto.

## Probe da fare / già validi

| Probe | Stato per T7 |
|---|---|
| **latenza del DUT** | ⚠️ **DA RIMISURARE**: i 364 clock sono della **SNN sola**; il composto ha latenza diversa (SNN + `align` + IIDM). Taratura di contatore/campionamento dipende da questa. |
| **costo simulazione 99 in anello** | ⚠️ **DA MISURARE** prima di impegnare ore (come si fece con `probe_golden_cost` in T6a) |
| P2 mixed-language · P3 board repoPaths · P4 BD+PS7/FCLK | ✅ **validi** (non dipendono dal DUT) — vedi `../Harness_SNN/results/PROBES_T6B.md` |

## Requisiti di metodo (dalla Fase B2.0, vincolanti)

Entry-point **unico** + numeri in **artefatti su disco** · **stesso perimetro** fra prova e metriche riportate ·
**niente ripieghi in corsa** · **probe-first** sulle assunzioni. Vedi `../README.md` §Requisiti.
