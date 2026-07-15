# SP2 — `Donatello_ACC_IIDM`: campione + plant ACC-IIDM open-loop

> Doc di processo del blocco. Spec: `docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`.
> Stato: **completo e verificato** (2026-07-15).

## Cos'è
Blocco unico `s,v,dv,v_l → accel`: campione Donatello **LUT-64** (fixed, cycle-accurate, l'architettura
del bitstream) + **ACC-IIDM open-loop** (double). Porta la catena completa **stato → azione di controllo**,
per testare la rete *dentro* un modello di car-following.

**Sola simulazione: NON sintetizzabile** — conseguenza accettata del blocco unico (spec §3): l'artefatto
HDL-ready resta `Donatello_Champion`. Non è un'assunzione di design: è **misurato** (vedi §Sintetizzabilità).

## Interfaccia e uso
| | |
|---|---|
| Ingressi | `s, v, dv, v_l` fisici, **fixed con ≥20 bit frazionari**. Data Type Conversion **fuori** dal blocco: se domani diventa HDL-ready l'interfaccia non cambia → niente rework |
| Uscita | `accel` [m/s²] (double), **tenuta** fino al control-step successivo |
| Semantica | **1 cambio d'ingresso = 1 control-step = DT 0.1 s**; ogni ingresso va tenuto **≥ ~341 campioni** (time-mux: 1 neurone/clock) |
| Loop | **aperto**: il blocco non integra `v` né `s`, li riceve. Unico stato interno: il filtro OU che stima `a_l` |

Latenza misurata: **340 clock**. Edge-triggered: con ingresso costante fa **una sola** inferenza.

## Il punto critico: il gating dell'IIDM — e la prova che il cancello lo vede
`DT` sopravvive all'apertura del loop **solo** dentro il filtro OU: `alf = ALPHA*alf + (1-ALPHA)*(Δv_l/DT)`.
Per questo l'IIDM gira **una volta per control-step** (dentro `if valid`, sul refresh dei parametri).

Girasse a ogni clock, per **340 campioni su 341** vedrebbe `Δv_l = 0` (l'ingresso è tenuto costante durante
l'inferenza) → stimerebbe **`a_l ≈ 0`** e il blend CAH sarebbe sistematicamente sbagliato, **in silenzio**.

Questo non è rimasto un timore teorico. È stata costruita la variante **mis-gated** (chiamata all'IIDM
spostata fuori da `if valid`) e misurata:

| variante | `dmax(accel)` vs riferimento | esito del cancello |
|---|---|---|
| blocco corretto | **0** | passa |
| mis-gated (IIDM a ogni clock) | **0.1836 m/s²** | **fallisce** (assert) |

Cioè: l'errore è fisicamente rilevante *e* il test lo becca. Un cancello che non può fallire non è un
cancello — è la lezione di `HDL_PHASE.md` §2.1, dove un bug nel forward è vissuto mesi perché i test
stampavano e basta.

## Sintetizzabilità — misurata, non assunta
Il «non sintetizzabile» era inizialmente una **claim di design mai verificata** (scritta in Description, doc e
commit). Messa alla prova il 2026-07-15 dando il blocco a HDL Coder nello stesso isolamento del cancello «altro
PC»: **rifiutato, 14 errori**. La claim regge, ma la spiegazione «mescola fixed e double» era incompleta. La
catena vera:

1. l'IIDM gira in **double** → HDL Coder attiva `UseFloatingPoint` e passa all'architettura **`MATLAB Datapath`**
   invece di `MATLAB Function` (quella usata dai blocchi HDL-ready);
2. su quell'architettura: `Call to operation 'tanh' is not supported for Double types` e idem per
   `min(v/v0, 10)^4`;
3. **di rimbalzo**, viene rifiutato anche lo struct dei tipi: `Struct in expression 'Tt' has an empty-typed
   field. This is not supported for MATLAB-to-dataflow conversion` — lo stesso `snn_types('fixed',13)` che nei
   blocchi HDL-ready passa senza problemi.

Cioè: **la causa radice è il double**; gli errori sullo struct sono un *effetto* del cambio d'architettura, non un
difetto di `snn_types`. Chi un domani volesse un ACC-IIDM su FPGA non deve inseguire lo struct: deve portare
l'IIDM in fixed (è l'SP a sé, vedi §Fuori scope).

> ⚠️ **`run_block_hdl_gate` non si lancia su questo blocco.** Cabla 5 uscite (`v0,T,s0,a,b`); questo ne ha 1
> (`accel`), quindi fallirebbe **sull'harness** e l'errore si scambierebbe per un verdetto di HDL Coder — una
> conferma *falsa*. Dal 2026-07-15 il cancello se ne accorge e si ferma con un messaggio esplicito.

## Anello CHIUSO (2026-07-15)
Cancello: **`run_block_closed_loop_test(trajIdx, K, hold, dvMode)`**. Dato il leader (posizione `x_l` e
velocità `v_l`), l'anello calcola gap e `dv`, li passa al blocco e integra l'ego con l'`accel` che ne esce.
Esito: **dmax = 0 su 10/10** (5 traiettorie × 2 convenzioni di `dv`). In anello chiuso `dmax = 0` è un criterio
*forte*: l'errore si retroaziona, quindi 1 LSB al passo k diverge nei passi dopo — o è 0, o si vede.

**Comportamento** (non solo implementazione): l'ego segue il leader in 5/5 scenari, gap sempre limitati
(2.7–44.5 m), nessuna collisione, nessun NaN. Negli scenari `stop_and_go` l'ego va a 0 perché **il leader stesso
si ferma** (`v_l` min = 0): è inseguimento corretto, non un difetto.

> ⚠️ **Non è un test di recupero dei parametri.** In anello chiuso l'ego è guidato dai parametri **stimati dalla
> rete stessa** → il sistema è auto-consistente e i `gt_params` del dataset non sono il bersaglio. Qui si
> verificano implementazione (`dmax = 0`) e comportamento.

### Semantica degli ingressi — misurata, non letta dai commenti
Su 60 traiettorie / 60.000 campioni, contro `data/generator.py`:

| fatto | evidenza |
|---|---|
| `s` (gap) è l'**ingresso #1**; `ds/dt = v_l − v` | `s[k]−s[k−1] == −dv[k]·DT` esatta a meno di 1 LSB |
| **non esistono posizioni assolute né lunghezza veicolo**: il generatore integra il gap direttamente | `s = clip(s + (v_l−v)·DT, …)` — nessun `x_l`/`x_ego` nel sorgente |
| ⇒ `s = x_l − x_ego − L`, con **`L` costante che i dati NON fissano** | scelta di modellazione, non recuperabile dal dataset |
| range operativo fissato dai dati | `s ∈ [1.25, 150] m` |
| ⚠️ **`dv` NON è `v − v_l` della stessa riga**: è `dv[k] = v[k−1] − v_l[k]` (v **prima** dell'update balistico) | ipotesi istantanea: \|res\| max **0.919** m/s (mediana 0.020); ipotesi sfasata: \|res\| max **1.9e-6** (= float32 del generatore) |
| il clip di `s` **non** è un caso limite | **6,06%** del dataset sta esattamente a `s = 150` |

⚠️ Omonimia insidiosa: `s` = gap corrente (**ingresso**) vs `s0` = jam distance (**parametro stimato in uscita**).

### La convenzione del training è riproducibile da un anello su posizioni
Non è un artefatto inaccessibile: basta questa discretizzazione (è quella di `generator.py`):

```
x_l(k) = x_l(k-1) + v_l(k)*DT      leader integrato con la v_l NUOVA
x_e(k) = x_e(k-1) + v(k-1)*DT      ego balistico con la v VECCHIA
v(k)   = clip(v(k-1) + accel*DT, 0, 1.2*v0)
dv(k)  = v(k-1) - v_l(k)           s(k) = clip(x_l(k) - x_e(k), 0.5*s0, 150)
```
Con `dvMode='train'` l'anello soddisfa entrambe le relazioni del dataset a meno di 1 LSB; `dvMode='inst'` le rompe.

### Quanto costa la `dv` istantanea? **Nulla** — misurato
In *anello aperto* sul dataset intero (60 traiettorie), dove i `gt_params` **sono** il bersaglio: stessa
traiettoria, `dv` del dataset vs `dv` ricalcolata istantanea. Errore relativo mediano:

| | v0 | T | s0 | a | b | media |
|---|---|---|---|---|---|---|
| `dv` training | 20.91% | 19.88% | 9.60% | 40.68% | 13.80% | **20.97%** |
| `dv` istantanea | 20.59% | 20.00% | 9.28% | 38.22% | 15.14% | **20.64%** |
| Δ | −0.33 | +0.13 | −0.33 | −2.46 | +1.34 | **−0.33 pp** |

Peggiora in **35/60** traiettorie e migliora in 25/60: testa o croce. **Lo scarto di convenzione (mediana ~4 LSB)
è sotto la sensibilità della rete** ⇒ l'anello «onesto» (quello realizzabile su strada, con `dv` istantanea) è
utilizzabile senza penalità misurabile.

> Sull'errore assoluto (~21%, `a` al 40%): **non è introdotto da qui.** Il readout è stato validato contro il
> `ref_params` del dataset (|diff| ≤ 1.09 su 6 traiettorie), e **anche il riferimento del dataset stima v0 ≈ 26.8
> contro un gt di 17.95**. È il tetto di **identificabilità** già diagnosticato dal progetto (Dynamic_Study): in
> traiettorie di puro inseguimento il veicolo non raggiunge il flusso libero, quindi `v0` è debolmente
> identificabile. Da non attribuire all'anello né al blocco.

### Il punto delicato: due rate diversi
Il modello gira al rate di **clock** (il time-mux vuole ~341 clock per inferenza) ma la fisica avanza al rate di
**control-step**. Senza il contatore nella chart `EGO`, l'ego integrerebbe l'accelerazione a ogni clock, cioè
**~400 volte troppo in fretta**. Serve inoltre un `Unit Delay` (1 clock) sulla retroazione di `accel`: la chart è
direct-feedthrough e senza rompere l'anello algebrico Simulink non compila. È innocuo — l'`accel` serve al
control-step dopo (≥ 400 clock).

## Single source
La matematica ACC-IIDM sta **solo** in `matlab/acc_iidm_open.m`. La usano:
- questo blocco (`build_hdl_variants` la legge a build-time e la inlina come funzione locale);
- il plant closed-loop `cf_plant_lib/ACC_IIDM` (= open-loop + integrazione balistica).

Anche `local_normalize` è a fonte unica (`build_hdl_variants:normalize_code`), condivisa fra i blocchi
HDL-ready e questo: duplicarla avrebbe fatto divergere i blocchi in silenzio alla prima modifica dei
reciproci Q?.30. Il cancello `run_block_sync_check` verifica che i blocchi inlinino i sorgenti **attuali**.

## Verifiche
| cancello | criterio | esito (2026-07-15) |
|---|---|---|
| `run_block_acciidm_test(K, traj, hold)` | `dmax(accel) = 0` vs riferimento (MEX + decode-64 + `acc_iidm_open`) | **0 su 5/5 traiettorie** ([1 6 12 20 30], 12 control-step ciascuna) |
| — sensibilità del test | la variante mis-gated deve farlo fallire | **fallisce, dmax = 0.1836** |
| `run_plant_parity` | plant closed-loop vs golden Python, invariato dopo il refactor | **`s|err| = v|err| = 0` su 3/3** |
| `run_block_sync_check` | i blocchi inlinano i sorgenti attuali (incluso `acc_iidm_open`) | **8 blocchi, 0 stale** |
| `run_block_traj_test('Donatello_Champion')` | i blocchi HDL-ready non regrediscono | **dmax = 0** |

### Perché il test pre-quantizza gli ingressi
`run_block_acciidm_test` pilota il blocco con valori **già rappresentabili** in `fixdt(1,32,20)`, così la
Data Type Conversion dell'harness è un no-op e il riferimento vede *esattamente* i numeri che vede il blocco.
Senza, `dmax = 0` sarebbe irraggiungibile: la SNN è insensibile alle differenze sotto 2⁻²⁰ (la normalize le
assorbe, `HDL_PHASE.md` §3.1.3) ma **l'IIDM è sensibile all'ingresso in modo diretto** — il test misurerebbe
l'arrotondamento dell'harness invece del blocco.

## Gotcha emersi (costati tempo, documentati per non ripagarli)
- **`isempty(<persistent>)` non è intercambiabile con un test sul valore.** Il codegen riconosce
  *letteralmente* `if isempty(p)` come prova di definizione. Scrivere `if ~started` lo fa fallire con
  «*Persistent variable 'v' is undefined on some execution paths*». È l'idioma di `snn_core.m:15-19` e va
  usato alla lettera. Diagnosi: Simulink riporta solo «Errors occurred during parsing of …» — il messaggio
  vero (con riga e colonna) si ottiene dando lo script della chart in pasto a `codegen`, che usa lo stesso
  front-end.
- **Il non-ASCII nella chart NON c'entra** (era la prima ipotesi, sbagliata). Verificato iniettando emoji,
  lettere greche e `§` in un commento di un sorgente inlinato: la chart si parsa e la parità resta 0.

## Fuori scope
ACC-IIDM su FPGA (fixed): è un **SP a sé** — `sqrt(a·b)` e le divisioni sono lo stesso genere di problema che
per la sigmoide ha richiesto una LUT; avrà i suoi numeri e i suoi cancelli. Fuori scope anche: chiudere il
loop dentro il blocco, altri champion, altri plant (Gipps/OVM…).
