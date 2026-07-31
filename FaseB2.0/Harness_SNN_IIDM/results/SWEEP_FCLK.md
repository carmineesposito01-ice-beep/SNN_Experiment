# T7b · Sweep FCLK — frequenza deployabile, limite del cammino critico, risorse post-route

> **Rigenerabile.** Implementazioni: `bash hw/run_impl_sweep.sh "15 20 25 30 35 40 45 50"` — un'invocazione Vivado per punto,
> `-jobs` FISSO (determinismo). Questa tabella: `python hw/gen_sweep_report.py`, che **parsa i `.rpt` grezzi**
> in `results/` — nessuna cifra e' trascritta a mano dalla console.

Perimetro: **sistema completo post-route** — PS7 + protocol converter + `snniidm_axi_lite` + DUT,
su xc7z020clg400-1 (PYNQ-Z1). WNS/WHS da `report_timing_summary`, utilizzo da `report_utilization`.

## Sweep

| FCLK chiesto | clock ottenuto [MHz] | periodo [ns] | WNS [ns] | WHS [ns] | ritardo ottenuto [ns] | LUT | FF | chiude |
|---|---|---|---|---|---|---|---|---|
| 15 | 15.152 | 66.000 | +30.749 | +0.022 | 35.251 | 8416 | 4556 | si |
| 20 | 20.000 | 50.000 | +16.097 | +0.052 | 33.903 | 8405 | 4556 | si |
| 25 | 25.000 | 40.000 | +9.519 | +0.037 | 30.481 | 8412 | 4556 | si |
| 30 | 30.303 | 33.000 | +2.764 | +0.045 | 30.236 | 8408 | 4556 | si |
| 35 | 34.484 | 28.999 | +1.008 | +0.026 | 27.991 | 8404 | 4556 | si |
| 40 | 40.000 | 25.000 | +0.022 | +0.033 | 24.978 | 8453 | 4556 | si |
| 45 | 45.455 | 22.000 | -2.470 | +0.048 | 24.470 | 8483 | 4560 | **NO** |
| 50 | 50.000 | 20.000 | -4.355 | +0.023 | 24.355 | 8503 | 4562 | **NO** |

⚠️ Il PS7 **quantizza** la frequenza richiesta: 15→15.152 MHz, 30→30.303 MHz, 35→34.484 MHz, 45→45.455 MHz. In tabella conta il **clock ottenuto**.

Il **WHS** e' positivo ovunque: nessun punto e' scartato per violazione di hold — il che rende il
criterio "chiude" leggibile sul solo setup.

## I due numeri, e la loro natura

| Grandezza | Valore | Natura |
|---|---|---|
| **Frequenza deployabile** | **40 MHz** (WNS +0.022 ns, WHS +0.033 ns) | **misurata** — il piu' alto fra i provati che chiude |
| **Limite del cammino critico** | **41.1 MHz** | **derivata** — `1/ritardo` al punto piu' stretto (50 MHz), che **non** chiude |

Il limite si legge **stringendo** il vincolo, non al crossover WNS=0: a vincolo largo lo strumento smette
di ottimizzare e il ritardo si assesta su un valore che **non** e' il limite del circuito. Lo mostrano i dati:
il ritardo ottenuto scende da **35.25 ns** a **24.36 ns** via via che il vincolo stringe.

## OOC e sistema sono perimetri DIVERSI: i numeri non si scambiano

Tre misure di timing sullo stesso circuito, a confronto:

| Perimetro | Vincolo | Esito | Frequenza implicata |
|---|---|---|---|
| **Sistema completo** (PS7 + converter + wrapper + DUT) | 40 MHz | WNS **+0.022** ⇒ **chiude** | **40 MHz deployabile** |
| Sistema completo, punto piu' stretto | 50 MHz | WNS -4.355 | 41.1 MHz (limite derivato) |
| **OOC** wrapper + DUT (per la netlist) | 40 MHz | WNS **-0.194** ⇒ **NON chiude** | 39.7 MHz |
| OOC del **solo DUT** (misura precedente) | — | — | 41.5 MHz |

Lo stesso circuito alla stessa frequenza **chiude nel sistema e non chiude in OOC**: la stima OOC qui e' piu'
PESSIMISTA di quella di sistema. Ne segue una regola operativa: **un numero OOC non e' una capacita' del
progetto** ed e' confrontabile solo con altri numeri OOC dello stesso perimetro. In particolare, la vicinanza
fra il limite derivato (41.1 MHz) e l'OOC del solo DUT (41.5 MHz) **non** dimostra che il wrapper sia gratuito:
a parita' di perimetro OOC, wrapper + DUT sta piu' in basso del DUT da solo.

Dove sia il collo lo dice invece un'**osservazione diretta**, non una coincidenza fra numeri: il
`report_timing` del sistema individua il cammino critico in **`DEC → align → IIDM`**, interno al blocco.

⚠️ **Qui NON vale la regola «OOC ≈ 2× il deployabile»** registrata per il Tier: la' il cammino critico passava
dal confine d'ingresso e il metro io-timed lo dimezzava. Quella regolarita' vale solo quando il collo sta **al
confine**; su questo blocco, dopo la correzione di `align`, non ci sta piu'.

## Risorse post-route al punto deployabile (40 MHz)

| Istanza | Ruolo | LUT | FF | DSP | RAMB18 |
|---|---|---|---|---|---|
| `sys_wrapper` | **sistema completo** | 8453 | 4556 | 69 | 2 |
| `tier0` | IP AXI (wrapper + DUT) | 8084 | 4097 | 69 | 2 |
| `u_dut` | **`Donatello_SNN_IIDM`** (il blocco) | 7974 | 3794 | 69 | 2 |
| `u_ACC` | └ ACC-IIDM (controllore) | 3032 | 1100 | 17 | 0 |
| `u_Tier` | └ `Donatello_Tier`@BAL/n13 (SNN) | 4077 | 2442 | 52 | 2 |
| `u_SNN` |     └ rete a spike | 2735 | 2045 | 36 | 2 |
| `u_DEC` |     └ decodifica readout | 950 | 397 | 16 | 0 |
| `u_align` | └ `align` (ritardo appaiato) | 876 | 252 | 0 | 0 |
| `ps7_axi_periph` | protocol converter (contorno) | 352 | 426 | 0 | 0 |

Sul dispositivo: **LUT 15.89 %** · **FF 4.28 %** · **DSP 31.36 %** · **BRAM 0.71 %** (1 tile).
Il DSP e' la risorsa piu' impegnata; nessuna e' vicina alla saturazione.

`align` — il blocco che allinea i cinque parametri ai quattro ingressi fisici — costa **876 LUT
(11.0 % del DUT)** e 252 FF. Non e' logica gratuita: e' il prezzo di **una** inferenza per
control-step, cioe' della correttezza del filtro OU.

## Area: insensibile al vincolo

LUT da 8404 a 8503 su tutto lo sweep: **1.2 %** di variazione; FF da 4556 a 4562; DSP e BRAM costanti (69 · 1).
**L'area non e' la leva su cui agire per guadagnare frequenza**, e per converso stringere il vincolo non
costa area in modo apprezzabile.

## Margine sul control-step — il solo requisito temporale vero

Una inferenza+controllo dura **555 clock** (misurato in T7a): e' la **latenza pura del DUT**.

⚠️ Il **duty** riportato in [`POWER.md`](POWER.md) e' leggermente piu' alto perche' misura la finestra
**effettivamente occupata**, protocollo AXI incluso (**582 clock**: 555 di latenza + 27 di scritture e polling
del `done`). I due numeri non sono in contraddizione, misurano due cose diverse: qui la **capacita' del
blocco**, la' l'**occupazione reale del sistema**. Per l'energia vale il secondo.

- a **15.152 MHz**: 555 clock = **36.6 µs** contro un control-step di **0.1 s** ⇒ margine **2730×**, duty **0.0366 %**
- a **40 MHz**: 555 clock = **13.9 µs** contro un control-step di **0.1 s** ⇒ margine **7207×**, duty **0.0139 %**

Nessun punto dello sweep mette in discussione il control-step, nemmeno il piu' lento: **la frequenza qui e'
una caratterizzazione, non un requisito**.
