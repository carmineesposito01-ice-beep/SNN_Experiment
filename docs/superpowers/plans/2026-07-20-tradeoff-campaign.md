# Campagna di trade-off — piano di esecuzione

> **Per chi esegue:** usare `superpowers:subagent-driven-development` o `superpowers:executing-plans`.

**Goal:** scegliere la configurazione da deployare per i due blocchi HDL-ready — **Donatello**
(accoppiamento SNN↔decode, 5 esperimenti) e **Donatello+IIDM** (17 round IIDM) — con una catena di
ragionamento verificabile da terzi.

**Ordine obbligato: A prima di B.** I 17 punti IIDM incorporano la SNN a **R9** *e* il decode **FUSO**.
Qualunque configurazione scelta nel Blocco A che tocchi il decode li invalida come misura del
deployabile → vanno rigenerati su quella base. (Piu' stringente della versione precedente, dove la
dipendenza scattava solo cambiando la profondita' SNN.)

**Architettura:** due strumenti Tcl validati (`synth_point.tcl` → DCP, `impl_point.tcl` → post-route)
orchestrati da un driver bash **ripartibile**. Ogni punto → una riga CSV + una cartella di artefatti;
un rilancio salta cio' che e' fatto. Nessuno stato in memoria, nessun ordine obbligato.

**Spec:** `docs/superpowers/specs/2026-07-20-tradeoff-study-design.md`
**Riesecuzione:** `matlab/study_tradeoff/README.md` · **Audit:** `matlab/hdl_iidm/RESULTS.txt` §AUDIT

**Stack:** Vivado 2026.1 (build 6511674, licenza BASIC), `xc7z020clg400-1`, xsim per il SAIF, Python 3.

---

## Struttura dei file

| file | responsabilita' | stato |
|---|---|---|
| `matlab/study_tradeoff/common/synth_point.tcl` | VHDL → post-sintesi + DCP, vincolo opzionale | ✅ validato |
| `matlab/study_tradeoff/common/impl_point.tcl` | DCP → post-route + metriche + flag validita' | ✅ validato |
| `matlab/study_tradeoff/common/run_campaign.sh` | driver ripartibile con raffinamento | ✅ scritto |
| `matlab/study_tradeoff/{donatello,donatello_iidm}/points.tsv` | tag, srcdir, periodo, Fmax OOC | ✅ generati |
| `matlab/study_tradeoff/{...}/vhdl_*.tar.gz` | ingressi archiviati + sha256 | ✅ verificati |
| `matlab/study_tradeoff/common/gen_donatello_point.m` | genera il blocco Donatello completo di un worktree | ✅ validato |
| `matlab/study_tradeoff/common/build_block_a.sh` | worktree → HDL → estrazione → periodo (uno alla volta) | ✅ validato |
| `matlab/build_decodedut.m` | probe del decode ISOLATO (fused/p3/p5) | ✅ validato |
| `matlab/gate_donatello_a1.m` | cancello sui dati del blocco Donatello (traiettoria reale) | ✅ validato |
| `matlab/study_tradeoff/common/aggregate.py` | CSV → frontiera, delta OOC↔route, grafici | da creare |
| `matlab/axi/acciidm_m/tb_acciidm_m_saif.v` | banco per il netlist funcsim | da creare |
| `matlab/study_tradeoff/common/power_point.tcl` | SAIF + `report_power` + confidenza | da creare |

**Regola trasversale:** ogni estrazione che fallisce scrive `NA`/`NON AGGANCIATO`, mai una cella vuota;
nessun `catch` senza messaggio. Un `catch` muto ha gia' nascosto l'unica informazione utile.

---

## Task 0 — Commit (PREREQUISITO, richiede consenso esplicito)

Tutto il lavoro R2→R17, gli archivi degli ingressi e gli script dello studio sono **non committati**.

- [ ] **Passo 1: mostrare cosa verrebbe committato**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git status --short && git diff --stat
```

- [ ] **Passo 2: commit** — *non si esegue senza che l'utente lo chieda.*

```bash
git add -A && git commit -m "feat(tradeoff): studio a due blocchi + audit pre-campagna

- 16 round IIDM bit-exact (15.673 -> 77.936 MHz OOC), tutti i cancelli verdi
- archivi verificati degli ingressi: 17 punti IIDM + 8 punti SNN (unica copia)
- matlab/study_tradeoff/: protocollo di misura con vincolo dichiarato, driver ripartibile
- audit: la calibrazione a 125 ns era un artefatto; sintesi vincolata +3,5% con meno area"
```

- [ ] **Passo 3: verificare che gli archivi siano nel commit**

```bash
git show --stat HEAD | grep -E "vhdl_rounds|vhdl_snn_points"
```
Atteso: entrambe le righe.

---

## Task 1 — Cancello di riproducibilita' del driver

- [ ] **Passo 1: rifare un punto gia' misurato in modo indipendente**

```bash
S=matlab/study_tradeoff
bash $S/common/run_campaign.sh $S/donatello_iidm/points.tsv /d/zbd_tradeoff/donatello_iidm iidm_r17
```

Atteso: `valid=VALIDA` e un ritardo coerente con la misura dell'audit (sintesi vincolata + impl a
12,831 ns → 12,451 ns, 80,315 MHz, con un raffinamento perche' il primo tentativo dava WNS +0,380).
**Se il ritardo differisse in modo sostanziale, fermarsi e capire perche' prima di spendere gli altri 24 punti.**

- [ ] **Passo 2: cancello di ripartibilita'**

```bash
bash $S/common/run_campaign.sh $S/donatello_iidm/points.tsv /d/zbd_tradeoff/donatello_iidm iidm_r17
```
Atteso: `SKIP iidm_r17 (gia' nel CSV)`, nessuna riga nuova.

---

## Task 2 — Blocco A: accoppiamento SNN <-> decode — **SI ESEGUE PER PRIMO**

Un blocco composto vale quanto il suo pezzo piu' lento. Gli esperimenti sono la **diagonale bilanciata**
piu' **due controlli** che dimostrano che lo squilibrio e' spreco in entrambe le direzioni.

### Matrice (Fmax composta attesa ~ min dei due pezzi)

| SNN v / decode > | `fused` 31,3 | `p3` 56,9 | `p5` 97,8 |
|---|---|---|---|
| **R2** 29,7 | **SLOW ~30** | — | ctrl ~30 |
| **R5** 62,2 | — | **BALANCED ~57** | — |
| **R9** 99,2 | ctrl **30,367 FATTO** | — | **FAST ~98** |

### Gli esperimenti

| # | esperimento | decode | SNN | commit SNN | attesa | ruolo | stato |
|---|---|---|---|---|---|---|---|
| 1 | SLOW | `fused` | R2 | `bb50f9f0` | ~30 | candidato area minima | da fare |
| 2 | BALANCED | `p3` | R5 | `8b4843dc` | ~57 | candidato compromesso | da fare |
| 3 | FAST | `p5` | R9 | `c9846f40` | ~98 | candidato margine massimo | da fare |
| 4 | ctrl SNN sovradim. | `fused` | R9 | `c9846f40` | 31,3 | +1068 FF non comprano nulla | **30,367** |
| 5 | ctrl decode sovradim. | `p5` | R2 | `bb50f9f0` | ~30 | la simmetria vale al contrario | da fare |

**Perche' R5 e non R4**: area quasi identica (3010/1982 vs 2992/1980 LUT/FF) ma 62,2 contro 52,2 — R5
domina. **Perche' R9 e non R8**: R8 limiterebbe a 91,9; R9 lascia decidere il decode a 97,8 (+5,9 MHz
per +118 FF) e l'accoppiamento e' piu' stretto (1,4% contro 6%).

⚠️ Il modello `min` e' pessimista di ~3%: l'esperimento 4 prevedeva 31,3 e ha misurato 30,367.

### Le due curve (GIA' MISURATE, non si rifanno)

**SNN core** (probe forward-only): R2 29,745 · R3 47,943 · R4 52,151 · R5 62,162 · R6 71,942 ·
R7 72,913 · R8 91,853 · R9 99,157 MHz.

**Decode isolato** (`matlab/build_decodedut.m`, misurato 2026-07-21):
`fused` 31,260 (821 LUT / 206 FF / 29 liv) · `p3` 56,867 (1007 / 388 / 14) ·
`p5` 97,828 (1201 / 702 / 7).

---

- [ ] **Passo 1 — [A2]: macchina a fasi del decode in `chart_code()`**

Oggi `chart_code()` ha solo il flag `dodec` di [A1] (decode in un ciclo a se'). Per `p3`/`p5` serve un
contatore di fase, sul modello di `acciidm_m_chart_code()`. Le funzioni delle fasi ESISTONO GIA' e sono
provate bit-exact (G2 0/60000 nei round IIDM R4/R10/R12/R17): e' cablaggio, non progettazione.

Firme: `decode_a1(raw)->adjv` · `decode_a2(adjv,N)->[k,frac]` · `decode_b1(k,N)->[s0v,delv]` ·
`decode_b2(s0v,delv,frac)->sv` · `decode_c(sv)->p`.
⚠️ `frac` nasce in `a2` e serve in `b2`: va RITARDATO per allinearsi a `b1`.

- [ ] **Passo 2 — cancello sui dati, per OGNI variante di decode**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "gate_donatello_a1"
```
Atteso: `dmax = 0` su traiettorie 1/7/23.
⚠️ `hold` ESPLICITO (500): il default di `run_block_traj_test` e' 400 e la latenza era ESATTAMENTE 400
— margine zero. Ogni fase aggiunta sposta la latenza, quindi il default fallisce su codice CORRETTO.

- [ ] **Passo 3 — cancello di ATTERRAGGIO (l'Fmax, non il dmax)**

⚠️ Un cancello sui dati NON vede se le fasi sono cablate male nell'ordine: i valori sarebbero identici,
solo disponibili prima. **Lo vede la sintesi**: se il path critico resta lungo quanto prima, le fasi non
sono atterrate. Per ogni variante il numero di livelli logici deve scendere (29 -> 14 -> 7 sul probe).

- [ ] **Passo 4 — costruire e misurare i 4 esperimenti mancanti**

⛔ **NIENTE WORKTREE** (metodo precedente, abbandonato dopo verifica). Ai commit dei round SNN le
funzioni `decode_a1`…`decode_c` **non esistevano** — sono nate dopo, nello studio IIDM — quindi dentro
un worktree del 18/07 il decode a fasi e' impossibile da costruire.

✅ **Metodo validato: si scambia UN SOLO FILE.** L'unica cosa che cambia fra i round SNN e'
`matlab/snn_b2_fsm.m` (verificato: gli altri file toccati da quei commit sono probe e RESULTS). La sua
firma e' **identica** ai tre commit e all'albero corrente — `[raw, valid] = snn_b2_fsm(xn, start)` — e
dipende solo da `b2_rom_active` e `snn_types`, stabili.
✅ **L'albero corrente E' GIA' R9** (identico a `c9846f40` a meno dei fine-riga: la SNN non e' piu' stata
toccata dopo la 2d). Per gli esperimenti con R9 non si scambia nulla.

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git show <commit>:matlab/snn_b2_fsm.m > matlab/snn_b2_fsm.m   # SNN allo stato voluto
#   ... build_hdl_variants + rtl_gen_dut('Donatello_LUT64', <outdir>) ...
git checkout -- matlab/snn_b2_fsm.m                            # RIPRISTINO (il file e' pulito vs HEAD)
```

Poi: copiare il VHDL in un path CORTO E SENZA SPAZI, sintesi libera (stima periodo), `run_campaign.sh`
con `TOPMOD=Donatello_LUT64`.
⚠️ Vivado spezza gli argomenti sugli SPAZI: mai passargli un path del repo (`1.Reti Neurali`).
⚠️ Ripristinare `snn_b2_fsm.m` DOPO OGNI esperimento: lasciarlo scambiato falserebbe i successivi in
silenzio.

- [ ] **Passo 5 — verdetto**

Confrontare 1 vs 4 (stessa Fmax, +1068 FF sprecati) e 1 vs 5 (stessa Fmax, +496 FF sprecati): insieme
dimostrano che conta l'ACCOPPIAMENTO, non la profondita' di uno dei due. Poi scegliere fra SLOW /
BALANCED / FAST con la catena vincoli -> obiettivo -> vincitore.

- [ ] **Passo 6 — DECISIONE che sblocca il Blocco B**

⚠️ I 17 punti IIDM incorporano la SNN a **R9** E il decode **FUSO**. Qualunque configurazione scelta qui
che tocchi il decode li invalida come misura del deployabile -> vanno **rigenerati** su quella base.
Non si avvia il Task 3 prima di questa decisione.


## Task 3 — Campagna Donatello+IIDM (17 punti) — **dopo il Task 2**

- [ ] **Passo 1: lanciare (~2 h 40 min)**

```bash
bash matlab/study_tradeoff/common/run_campaign.sh \
     matlab/study_tradeoff/donatello_iidm/points.tsv /d/zbd_tradeoff/donatello_iidm \
     2>&1 | tee /d/zbd_tradeoff/donatello_iidm/run.log
```

- [ ] **Passo 2: stesso cancello del Task 2 passo 2**, atteso 17 punti.

---

## Task 4 — (ASSORBITO nel Task 2)

La rigenerazione del blocco Donatello completo non e' piu' un task a se': **tutti** i 9 punti del
Task 2 sono blocchi completi rigenerati dal proprio commit. `don_now` (working tree) e' il punto
che prima era "Donatello allo stato finale".

Il cancello di coerenza fisica (blocco completo ≤ probe forward-only) e' il **Task 2 passo 5**.

---

## Task 5 — Frontiere di Pareto post-route

- [ ] **Passo 1: `matlab/study_tradeoff/common/aggregate.py`**

```python
#!/usr/bin/env python3
"""Frontiera di Pareto post-route per un blocco + confronto con l'OOC storico.
   uso: aggregate.py <campaign.csv> <points.tsv>"""
import csv, sys

def pareto(pts):
    """pts: [(tag,fmax,lut)]. Non dominato = nessun altro con fmax>= e lut<= (uno stretto)."""
    return sorted([p for p in pts
                   if not any(f2>=p[1] and l2<=p[2] and (f2>p[1] or l2<p[2])
                              for t2,f2,l2 in pts if t2!=p[0])],
                  key=lambda x:-x[1])

csv_path, pts_path = sys.argv[1], sys.argv[2]
ooc={r['tag']:float(r['fmax_ooc']) for r in csv.DictReader(open(pts_path),delimiter='\t')}
rows=[r for r in csv.DictReader(open(csv_path)) if r['fmax_mhz'] not in ('NA','')]
pts=[(r['tag'], float(r['fmax_mhz']), int(float(r['lut']))) for r in rows]
front={t for t,_,_ in pareto(pts)}

print(f"{'punto':16}{'Fmax OOC':>10}{'Fmax route':>12}{'delta':>9}{'LUT':>8}  stato")
for t,f,l in sorted(pts,key=lambda x:-x[1]):
    o=ooc.get(t,float('nan'))
    print(f"{t:16}{o:10.3f}{f:12.3f}{(f-o)/o*100:+8.1f}%{l:8d}  {'FRONTIERA' if t in front else 'dominato'}")

oof={t for t,_,_ in pareto([(t,ooc[t],l) for t,f,l in pts if t in ooc])}
print(f"\nfrontiera OOC        ({len(oof)}): {sorted(oof)}")
print(f"frontiera post-route ({len(front)}): {sorted(front)}")
if front!=oof:
    print(">>> L'ORDINE E' CAMBIATO: e' un RISULTATO, da spiegare nel documento.")
    print(f"    entrati: {sorted(front-oof)}   usciti: {sorted(oof-front)}")
else:
    print(">>> Frontiera invariata: la classifica OOC reggeva.")
```

⚠️ Il confronto OOC↔post-route mette a confronto **sintesi libera** (storico) e **sintesi vincolata +
post-route** (campagna): il delta contiene entrambi gli effetti e va descritto cosi', non come "costo
del routing".

- [ ] **Passo 2: eseguire su entrambi i blocchi e conservare l'output**

```bash
S=matlab/study_tradeoff; mkdir -p results/tradeoff
for b in donatello donatello_iidm; do
  python $S/common/aggregate.py /d/zbd_tradeoff/$b/campaign.csv $S/$b/points.tsv \
    | tee results/tradeoff/pareto_$b.txt
done
```

---

## Task 6 — Potenza sui punti di frontiera

- [ ] **Passo 1:** copiare `matlab/axi/acciidm_m/tb_acciidm_m_open.v` in `tb_acciidm_m_saif.v`
cambiando **solo** il modulo istanziato (`Donatello_ACC_IIDM_M` → `DUT`): interfaccia identica,
verificato in audit.
- [ ] **Passo 2:** per ogni punto di frontiera, `write_verilog -mode funcsim` dal `routed.dcp`, poi
`xvlog` / `xelab -L unisims_ver -L secureip <tb> glbl` / `xsim -R` con `log_saif` + `write_saif`
(metodo di `gen_saif_b2.sh`, che resta il riferimento procedurale).
- [ ] **Passo 3:** `report_power` con **due scenari di duty dichiarati** (back-to-back e duty reale
0,07%) + livello di confidenza + `set_operating_conditions` dichiarate + sensibilita' alla temperatura.
- [ ] **Passo 4:** confidenza bassa ⇒ il numero si **scarta, non si riporta**.

---

## Task 7 — Documento finale

- [ ] **Passo 1:** scala dei tetti **ricalibrata post-route** sul punto raccomandato di ciascun blocco
(`spectrum_iidm.tcl`, metodo del `set_false_path`, riusando il suo `routed.dcp`).
- [ ] **Passo 2:** correggere il commento stale in `scripts/spectrum_iidm.tcl:27` («sintesi da 15
minuti»: misurata 1 min 49 s).
- [ ] **Passo 3:** scrivere `document/TRADEOFF_STUDY.md`: una sezione per blocco (tabella con
provenienza, frontiera coi dominati visibili, tre tier, raccomandazione con la catena esplicita) piu'
una figura d'insieme del **contributo di ciascun pezzo** (tanh → SNN → decode → IIDM).
- [ ] **Passo 4:** includere le tre avvertenze obbligatorie (spec §4): l'Fmax vale come **margine**; la
statica e' ~90% e non discrimina; **ogni frequenza dichiara il vincolo con cui e' stata misurata**.

---

## Cancelli della campagna

| cancello | criterio | dove |
|---|---|---|
| riproducibilita' | `iidm_r17` rifatto dal driver riproduce la misura dell'audit | Task 1 |
| ripartibilita' | il rilancio salta i punti fatti | Task 1 |
| interfaccia identica | stesso numero di porte sui 9 punti ricostruiti | Task 2 passo 2 |
| completezza | 9 + 17 righe, zero campi `NA` | Task 2/3 |
| validita' | ogni riga `valid` ∈ {`VALIDA`, `CONFERMATA`} | Task 2/3 |
| hold | WHS ≥ 0 ovunque | `impl_point.tcl` lo stampa |
| coerenza fisica | Donatello completo **≤** probe forward-only | Task 2 passo 5 |
| dipendenza A→B | Task 3 non parte prima della decisione del Task 2 passo 6 | Task 2 passo 6 |
| potenza | confidenza + scenario di duty dichiarati | Task 6 |

⚠️ **Un cancello che non puo' fallire non e' un cancello.** Quello di riproducibilita' confronta con un
numero misurato prima e in modo indipendente; quello di coerenza fisica puo' fallire davvero, perche'
mette a confronto due misure ottenute per strade diverse.
