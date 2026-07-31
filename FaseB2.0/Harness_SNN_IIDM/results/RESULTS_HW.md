# T7b · Caratterizzazione hardware di `Donatello_SNN_IIDM` — sintesi

> **Generato**, non scritto a mano: `python hw/gen_results_hw.py`, che compone i sommari JSON emessi dai
> tre generatori di dettaglio. Ogni numero nasce in UN posto solo, dal proprio report grezzo.
> Dettaglio: [`SWEEP_FCLK.md`](SWEEP_FCLK.md) · [`NETLIST.md`](NETLIST.md) · [`POWER.md`](POWER.md) ·
> [`COSIM_AXI.md`](COSIM_AXI.md) · [`RESULTS.md`](RESULTS.md) (T7a, livello RTL).

Dispositivo **xc7z020clg400-1** (PYNQ-Z1), Vivado 2026.1, `-jobs` fisso per il determinismo.

## I numeri, con la loro natura

| Grandezza | Valore | Natura |
|---|---|---|
| Params letti dal **PS via AXI** == blocco | **0 / 58 522** su 99 scenari, gating ON e OFF | misurato |
| Netlist **post-place&route** == blocco | **0 / 1507** (3 scenari dichiarati, funcsim) | misurato |
| **Frequenza deployabile** | **40 MHz** — WNS +0.022 ns · WHS +0.033 ns | **misurato** |
| **Limite del cammino critico** | **41.1 MHz** — al punto piu' stretto (50 MHz), che NON chiude | **derivato** |
| Risorse post-route @40 MHz | 8453 LUT (15.9 %) · 4556 FF (4.3 %) · 69 DSP (31.4 %) · 1 BRAM (0.7 %) | misurato |
| Finestra attiva (inferenza + protocollo AXI) | **582 clock** (555 di latenza + 27 di AXI) | misurato |
| Latenza / margine sul control-step 0.1 s | 13.9 µs / **≈7207×** (duty **0.0146 %**) | derivato |
| Potenza **idle** (dinamica) | **0.011 W** — finestra convergente su 200/1000/5000 | misurato |
| Potenza **attiva** (mentre calcola), su 8 carichi reali | **0.026 W** dinamica — identica a 3 decimali su tutti; la dispersione vera e' **2.9 %** sui *toggle* | misurato |
| **Potenza al duty REALE** (control-step intero) | **0.011 W** dinamica (+ 0.103 W di statica) | **misurato, NON composto** |
| **Energia dinamica** per control-step | **1.10 mJ** | derivato (`P_dyn × 0.1 s`) |
| Statica del device (pavimento del chip, **separata**) | 0.103 W → 10.3 mJ per control-step | misurato |
| **Copertura SAIF** / confidenza | **12506 / 19951 net = 62.7 %** · `High` | misurato |
| Bitstream PYNQ-Z1 | **non ancora prodotto** | — |

## Tre cose che questi numeri NON dicono

| Domanda | Stato | Perche' |
|---|---|---|
| La netlist e' equivalente su **tutti** i 99 scenari? | **non provato** (N=3 dichiarato) | costo: ~28 h (penalizzazione gate-level **44×**, misurata qui) |
| Il **worst case** energetico? | **non determinato** | si riporta il **massimo osservato** fra carichi reali. Il worst sintetico fu **smentito su misura** in T6b: risulto' il piu' basso di tutti |
| Il guadagno in watt del **clock gating**? | **non misurabile con questo flusso** | `report_power` deriva la potenza dei net di clock dal VINCOLO di frequenza, non dal SAIF (accertato in T6b anche in negativo) |

## Due premesse su cui NON costruire

- **Il PS7 quantizza la frequenza richiesta** (15→15.152 MHz, 30→30.303 MHz, 35→34.484 MHz, 45→45.455 MHz). Il periodo **non** e' `1000/f_richiesta`: va letto
  dalla tabella dei clock del `report_timing`. Una tabella costruita sull'assunzione aveva **4 righe
  sbagliate su 8**.
- **OOC e sistema sono perimetri diversi e i numeri non si scambiano.** Lo stesso circuito a 40 MHz
  **chiude nel sistema** (WNS +0.022) e **non chiude in OOC** (WNS -0.194). Un numero OOC non e' una
  capacita' del progetto ed e' confrontabile solo con altri numeri OOC dello stesso perimetro.

## Riesecuzione

```bash
bash hw/run_harness_snniidm_hw.sh summary     # i numeri in pochi secondi, dagli artefatti
bash hw/run_harness_snniidm_hw.sh <stadio>    # check | cosim | sweep | netlist | power | bitstream | all
```
Lo stadio `check` confronta la firma md5 dei sorgenti con quella registrata in `results/src.sig`: una
differenza **blocca** gli stadi di calcolo, perche' i risultati qui si riferirebbero ad altri sorgenti.
