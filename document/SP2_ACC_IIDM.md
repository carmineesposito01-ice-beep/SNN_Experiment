# SP2 — `Donatello_ACC_IIDM`: campione + plant ACC-IIDM open-loop

> Doc di processo del blocco. Spec: `docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`.
> Stato: **completo e verificato** (2026-07-15).

## Cos'è
Blocco unico `s,v,dv,v_l → accel`: campione Donatello **LUT-64** (fixed, cycle-accurate, l'architettura
del bitstream) + **ACC-IIDM open-loop** (double). Porta la catena completa **stato → azione di controllo**,
per testare la rete *dentro* un modello di car-following.

**Sola simulazione: NON sintetizzabile** — per costruzione mescola la SNN in fixed con l'IIDM in double.
È una conseguenza accettata del blocco unico (spec §3): l'artefatto HDL-ready resta `Donatello_Champion`.

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
