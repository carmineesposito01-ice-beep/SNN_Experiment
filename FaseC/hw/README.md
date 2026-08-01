# `FaseC/hw/` — strumenti che girano su Vivado e xsim

Tutto qui dentro è **simulazione o sintesi**: nessuno di questi script tocca la scheda. Gli stadi
su silicio stanno in [`../phase_c/`](../phase_c/) e si eseguono da [`../RUNBOOK.md`](../RUNBOOK.md).

> **Scope, 2026-08-01.** Il plotone è **fuori dallo studio su hardware**: P3 su silicio è
> cancellato. Ciò che resta qui è un risultato **software/RTL** più una **caratterizzazione**
> delle risorse — nessuno dei due alimenta la campagna sulla scheda.

---

## Due famiglie di strumenti

### 1. Sonda risorse — `probe_resources.{sh,tcl}` + `gen_resource_report.py`

Quante istanze del composto entrano nello Zynq-7020, e a che prezzo.

```bash
./probe_resources.sh "<lista N>" "<lista max_dsp>" [dut|wrapper]
PROBE_FASE=impl PROBE_PERIOD_NS=25.0 ./probe_resources.sh "4 5" "220" wrapper
python gen_resource_report.py            # log -> results/P3_resources.json
```

| Argomento | Significato |
|---|---|
| lista N | quante istanze per punto |
| lista max_dsp | tetto ai DSP; sotto il tetto i moltiplicatori finiscono in LUT/FF |
| `dut` | solo `Donatello_SNN_IIDM` — la logica di calcolo |
| `wrapper` | `snniidm_axi_lite`, che contiene il DUT: **l'unità deployabile** |
| `PROBE_FASE=impl` | place & route **veri** invece della sola sintesi |

**Tre cose che questo strumento ha insegnato, e che vale la pena non riscoprire:**

1. **Il conteggio LUT non prova la deployabilità.** A N=5 le LUT entrano (47 842 su 53 200) e il
   **placer fallisce**: una slice ha 4 LUT e 8 FF, e il packing è limitato dai *control set*.
   Vivado: «6040 slice disponibili, le non piazzate ne richiedono 7964». Il numero vero è **4**.
2. **N istanze con gli stessi ingressi verrebbero fuse** dal sintetizzatore, e la misura direbbe
   che il plotone è quasi gratis. Per questo ogni istanza ha porte proprie — e la fusione si
   esclude **misurando**: `LUT/(LUT₁·N) = 1,0000` esatto per N=1,2,3.
3. **Il wrapper costa 183 LUT per istanza**, costante su tre punti. La previsione a N=6 dal
   costo costante ha sbagliato di **5 LUT su 72 mila**.

Il primo punto misurato è di **taratura**: N=1 deve riprodurre le risorse già note da T7b. Contro
il riferimento giusto (`u_dut`, non il top) dà +5,3 % LUT e +3,1 % FF — lo scarto atteso fra
post-sintesi e post-implementazione.

### 2. Plotone in RTL — `p2_export.py`, `tb_platoon.v`, `run_p2.sh`, `p2_compare.py`, `p2_exact.m`

```bash
python p2_export.py --out C:/t7cp2 --n 4         # scenari + golden
./run_p2.sh C:/t7cp2 88 4 600 700 par            # PLATOON-PAR (plant, senza DUT)
python p2_compare.py --work C:/t7cp2 --nscen 88 --modo platoon-par
./run_p2.sh C:/t7cp2 88 4 600 700 loop           # anello chiuso, N DUT
matlab -batch "p2_exact('C:/t7cp2', 88, 4, 700)" # P2-EXACT (contro il blocco)
```

**La decomposizione, e perché non è circolare** — la stessa di T7a:

| | Confronta | Non usa |
|---|---|---|
| **PLATOON-PAR** | il plant Verilog contro le traiettorie di P1, accelerazioni rigiocate | il DUT |
| **P2-EXACT** | l'accel di ogni DUT contro il **blocco** ripilotato sugli stessi ingressi | il plant |

Plant corretto **+** DUT corretto ⇒ anello corretto. Il riferimento di P2-EXACT è il **blocco**,
non P1: in P1 l'accel è float32 continua, nell'RTL è quantizzata a `sfix13_En8`, e i due non
calcolano la stessa grandezza — misurato, distano in mediana il 25 % di un LSB.

**Tre trappole già pagate, che il codice evita per iscritto:**

- **`hex2dec` distrugge il confronto bit-esatto in silenzio.** Arrotonda oltre 2⁵³, e in T7a
  faceva fallire PLANT-PAR con 2241/2400 disallineamenti su un plant **corretto**. Si usa
  `t7_hexread` (che è `hex2num`).
- **Il motore del plotone calcola l'incremento di velocità in float32** — `_accel` torna da torch
  in singola precisione e numpy non promuove il prodotto con uno scalare Python. L'esportatore lo
  riproduce scrivendo l'incremento già arrotondato; `shortreal` in xsim **non** arrotonda
  (verificato: `double == shortreal` dà 1).
- **Il teletrasporto del `cut_in`** riguarda 33 scenari su 99. Senza, il leader si ferma di colpo
  senza il gap compensativo e la collisione è inevitabile per costruzione.

---

## Artefatti prodotti

| File | Da | Contiene |
|---|---|---|
| `../results/P3_resources.json` | `gen_resource_report.py` | curva risorse, instradabilità, WNS |
| `../results/P3_probe.log` | `probe_resources.sh` | l'output grezzo — è la prova da cui l'artefatto è rigenerabile |
| `../results/p2_platoon_par.json` | `p2_compare.py` | PLATOON-PAR |
| `../results/p2_exact.json` | `p2_exact.m` | P2-EXACT |
| `../results/p2_costo_quantizzazione.json` | `p2_quant_cost.py` | quanto costa `sfix13_En8` sul plotone |

Tutti nella busta `{data, prov}` degli altri artefatti della Fase C, quindi
`../run_phase_c.sh summary` li elenca con la loro provenienza.

---

## Costi misurati (non stimati)

| Operazione | Costo |
|---|---|
| un punto di sonda, sintesi | ~150 s |
| un punto di sonda, place & route | ~14 min |
| export di 88 scenari | ~4 min |
| PLATOON-PAR, 88 scenari | ~10 min |
| anello chiuso, 88 scenari × 4 DUT | **~118 min** — ~80 s/scenario, misurato su 88 punti |
| P2-EXACT, 88 × 4 replay del blocco | ~21 min |

**Ogni run lunga è preceduta da un punto singolo**, per misurare il costo invece di stimarlo — e
con una cautela: il primo punto include la compilazione, e stimare da lì **sottostima**. La
prima stima dell'anello chiuso, derivata da "114 s per compilazione + 1 scenario", dava 75
minuti contro i 118 reali. Un secondo punto costa poco e toglie l'ambiguità.

⚠️ **Non incanalare una run lunga in `tail`**: il codice stampa l'avanzamento per-scenario, ma
`tail` lo trattiene fino alla fine, e per venti minuti non si distingue "sta lavorando" da
"è appesa" senza andare a guardare la CPU del processo. Lasciare scorrere, o scrivere su file.

Il resto:
i cancelli si provano **prima**: 32 secondi per sapere che i 21 minuti successivi misurano
qualcosa.

---

## Requisiti

- Vivado 2026.1 in `C:/AMDDesignTools/2026.1/Vivado/bin` (`VIVADO_BIN` per cambiarlo)
- Sorgenti RTL del composto in `C:/t7bimpl/src` (`PROBE_SRC` / `P2_SRC`)
- MATLAB R2026a con Simulink, per `p2_exact.m`
- **Work-dir senza spazi**: xsim e `read_verilog` si spezzano sui percorsi con spazi — il repo
  sta sotto `.../1.Reti Neurali/...`, e gli script lo verificano e abortiscono.
