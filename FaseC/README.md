# Fase C — validazione su silicio e chiusura mesoscopica

Porta su FPGA fisica (PYNQ-Z1, Zynq-7020) il controllore `Donatello_SNN_IIDM` già validato e
caratterizzato in simulazione nella Fase B2.0, e chiude il proxy mesoscopico.

`FaseC/` sta **di primo livello, sorella di `FaseB2.0/`** — non dentro. La Fase C non è un harness della
Fase B2.0: ne *consuma* gli artefatti.

> ### ▶ Da dove si riparte
> **[STATO.md](STATO.md)** — dove siamo, cosa e' gia' provato, cosa manca, quali strade sono
> chiuse e perche'. La Fase C si riprende leggendo **solo** i documenti qui dentro.

| Documento | Cosa contiene |
|---|---|
| [STATO.md](STATO.md) | stato, risultati misurati, decisioni prese, trappole gia' pagate |
| [RUNBOOK.md](RUNBOOK.md) | la procedura operativa con la scheda accesa |
| questo README | mappa dei file, regole di collocazione, come si eseguono i test |
| [hw/README.md](hw/README.md) | gli strumenti che girano su Vivado e xsim |

- **Spec:** [`docs/superpowers/specs/2026-07-31-fase-c-silicio-e-plotone-design.md`](../docs/superpowers/specs/2026-07-31-fase-c-silicio-e-plotone-design.md)
- **Piano:** [`docs/superpowers/plans/2026-07-31-fase-c-silicio-e-plotone.md`](../docs/superpowers/plans/2026-07-31-fase-c-silicio-e-plotone.md)

---

## Tre regole di collocazione

Valgono per ogni file aggiunto qui dentro, adesso e in seguito.

1. **La logica sta in `phase_c/`, importabile.** Le facciate (`run_phase_c.sh`,
   `notebook/phase_c.ipynb`) stanno fuori e non contengono logica propria — altrimenti il cancello di
   parità fra le due non può essere verde, e la ridondanza diventa rassicurante invece che informativa.
2. **I numeri vivono solo in `results/`.** Mai nella chat, mai in una cella del notebook, mai in un
   commento. Un numero senza artefatto non è un risultato.
3. **Un file di test per modulo**, con lo stesso nome: `phase_c/c1_functional.py` → `tests/test_c1.py`.

---

## Struttura

```
FaseC/
  STATO.md                DA DOVE SI RIPARTE — stato, decisioni, trappole
  README.md               questo file
  RUNBOOK.md              procedura con la scheda accesa
  pytest.ini              rende `phase_c` importabile da qualunque cwd
  run_phase_c.sh          FACCIATA 1 — a stadi, l'entry-point
  c_frontend_parity.py    il cancello fra le due facciate

  phase_c/                LA LOGICA
    __init__.py           percorsi verificati (ROOT, RESULTS, PROJECT, T7_WORK, DATASET)
    regmap.py             mappe registri e conversioni di formato — UNICO posto
    driver.py             SnnIidmDriver, SnnTierDriver (sopra overlay reale o mock)
    overlay_hw.py         l'overlay VERO (PYNQ) + BancoPynq per C3; reset PROVATO
    mock_overlay.py       finge la scheda; risponde coi golden di T7a
    golden.py             i golden di T7a: UNICO posto dove vive il formato dei file
    artifacts.py          scrittura/lettura artefatti con provenienza
    params.py             gt_params e campione addestrato
    cli.py                entry-point condiviso dalle DUE facciate
    plots.py              grafici: accelerazione vs traiettoria
    c0_liveness.py        il bus risponde e i registri ritengono
    c1_functional.py      replay dei 99 scenari, bit-esatto
    c2_closedloop.py      PLANT-PAR del PS, poi anello chiuso
    plant_ps.py           port 1:1 di qz_cl_sim
    c3_power.py           differenziale randomizzato + Tj, campagna e cancello sorgente
    dmm.py                da dove arriva il numero di corrente (prompt/seriale/rigioco)
    xadc.py               lettura Tj e tensioni
    platoon.py            P1 (software) e P2 (RTL) -- P3 su silicio cancellato

  tests/                  un file per modulo + conftest.py (fixture dei golden)
  hw/                     script Vivado + dmm_discover.py (byte grezzi dello ZT-702S)
  notebook/phase_c.ipynb  FACCIATA 2 — solo chiamate a phase_c.cli + grafici
  results/                ARTEFATTI — l'unico posto in cui vivono i numeri
```

---

## Cosa gira SENZA la scheda

Gran parte della Fase C. Serve perché quando la scheda si accende non si scriva codice, si esegua.

| Gira adesso | Come |
|---|---|
| Tutti i moduli C0–C3, contro il mock | `python -m pytest` |
| **P1** — plotone (risultato SOFTWARE, fuori dallo studio su scheda) | `./run_phase_c.sh p1` |
| **Sonda risorse** del plotone | `bash hw/probe_resources.sh` (è sintesi Vivado, non silicio) |
| **P2** — plotone in RTL (xsim) | `./hw/run_p2.sh` — è simulazione, non silicio |
| Cancello di parità fra le facciate | `./run_phase_c.sh parity` |

Richiedono la scheda accendibile **solo** C0/C1/C2/C3 sui filoni A e B. Procedura in
[`RUNBOOK.md`](RUNBOOK.md).

> **Scope rivisto il 2026-08-01: il plotone è FUORI dallo studio su hardware.** P3 su silicio è
> cancellato — N istanze su una scheda *simulano* un plotone, e il software lo fa meglio, senza
> il costo del bring-up e senza il limite di 4 veicoli imposto dalle risorse. P1 e P2 restano
> come risultati software/RTL; la sonda risorse resta come caratterizzazione.

---

## Costanti misurate — NON riderivarle

Vengono dalla Fase B2.0. Ricalcolarle qui significherebbe due posti per la stessa decisione.

| Grandezza | Valore | Fonte |
|---|---|---|
| Composto: FCLK deployabile | 40 MHz (WNS +0,022 ns · WHS +0,033 ns) | `FaseB2.0/Harness_SNN_IIDM/results/sweep.json` |
| Composto: latenza / finestra attiva | 555 / 582 clock | `.../results/power_params.json` |
| Composto: duty | 0,0146 % | idem |
| Composto: potenza PL | 11 mW dinamica + 103 mW statica | `.../results/power.json` |
| Composto: energia per control-step | 1,10 mJ dinamica | idem |
| SNN sola: FCLK | 52 MHz | `FaseB2.0/Harness_SNN/results/RESULTS_HW.md` |
| Formato ingressi | `sfix32_En20` | §2.4 report T7 |
| Formato uscita `accel` | `sfix13_En8` (1/256 ≈ 0,0039 m/s², ±16) | idem |
| Golden bit-esatti | `$T7_WORK/axi_{stim,gold,len}_<i>.mem`, i = 1..99 | T7a |

**Mappa registri** — composto: `0x00–0x0C` ingressi · `0x10` controllo (bit0 commit, bit1 gating) e
`done` in lettura · `0x14` accel. SNN sola: identica, ma **5** registri d'uscita `0x14–0x24`.

---

## Variabili d'ambiente

| Variabile | Default | A cosa serve |
|---|---|---|
| `T7_WORK` | `C:/t7bw` | dove stanno i golden di T7a |

---

## Eseguire i test

```bash
cd FaseC && python -m pytest
```

Gira da qualunque directory (`pytest.ini` fissa la rootdir): è il cancello del Task 0, e serve perché le
due facciate eseguano lo stesso codice a prescindere da dove sono state lanciate.
