# PRESENTATION_DESIGN — Presentazione CF_FSNN (SNN → la nostra rete → risultati): design

> ⚠️ **STORICO / SUPERATO (2026-07-06).** Questo è il design *iniziale* approvato. La presentazione è stata **implementata, rivista e finalizzata** come **deck unico** `deck_slim.html` (42 slide, Parte 3 organizzata per tier T0→T5), su branch `main`. Per lo stato attuale e il runbook vedi **`PRESENTATION_MILESTONE.md`**.

> **Data:** 2026-07-04 · **Branch:** `EventProp_Study` · **Stato:** **DESIGN APPROVATO dall'utente — NON ancora implementato.**
>
> Design di una presentazione esaustiva e comprensibile del progetto CF_FSNN, in tre macro-parti
> (① le SNN in generale · ② la nostra rete · ③ i nostri risultati). Registra: le **decisioni bloccate**,
> il **metodo** (da ricerca multi-agente), la **scaletta slide-per-slide**, e il **workflow di build** in Quarto.
> Documento scritto **a mano** (non generato da builder). **Prima di scrivere codice/slide**, aprire una
> sessione di implementazione (writing-plans) su questo design.

---

## 0. Come riprendere (leggere prima questo)

**Cosa costruiamo:** una presentazione che spiega CF_FSNN **da zero**, in tre atti — ① cos'è una SNN · ② la
nostra rete PINN/ALIF/EventProp che identifica i 5 parametri ACC · ③ i risultati, in **due sotto-sezioni**
(**3A** validazione del comportamento fisico · **3B** validazione FPGA). Fonte dei contenuti = il **trio v3**
(`HOW_IT_WORKS_v3` teoria, `VALIDATION_REPORT_v3` risultati, `FPGA_REPORT` hardware).

**Chi è il pubblico (decisivo):** è una **tesi**, ma il **tutor non è esperto** del dominio e **conosce già il
progetto**; il target reale dell'esaustività sono i **suoi superiori** (che NON lo conoscono). Quindi il driver
non è "impressionare esperti" ma **insegnare tutto con chiarezza + completezza**. Presentazione **didattica**,
non difensiva. **Nessun limite di durata.** **Bilingue**: slide in **italiano con i termini tecnici anche in
inglese** tra parentesi; **esposizione in italiano**.

**Il principio-chiave (risolve esaustivo vs comprensibile):** **una spina lineare** che chiunque percorre +
**profondità appesa** che scendi a richiesta. Non si sceglie tra le due: per ogni contenuto si decide se sta
**sulla spina** (comprensibile a tutti) o è una slide di **profondità** (inline, alla sua posizione, mostrata
nel deck completo).

**Decisioni bloccate:**
1. **Struttura = C (spina + profondità a "dial").** Un solo deck, due percorsi.
2. **Deck di default = i ~25 slide core `[C]`**; le slide di **profondità `[+]` stanno INLINE alla loro posizione
   logica** (la numerazione = il posto giusto nel flusso), mostrate/nascoste via **profilo Quarto** (reduced/full):
   il deck ridotto le salta, il deck completo le mostra **al loro posto** — **NON** un blocco-appendice terminale.
   Il "taglietto" (per i superiori / Q&A) cade da solo dai tag.
3. **Tooling = Quarto + reveal.js**; figure rigenerate dai nostri script Python al render; 2 hero **Manim**.
4. **Lingua = slide IT + termini EN**, esposizione IT.
5. **Palette = Okabe-Ito** (color-blind safe) con identità-champion + codifica ridondante (colore + tratteggio + marker).
6. **Atto 3 = due sotto-sezioni**: 3A comportamento (VALIDATION) · 3B FPGA (FPGA_REPORT), con divider e mini-recap.

**Prossima azione:** sessione di implementazione (writing-plans) su questo doc → creare la **sottocartella**
`presentation/cf_fsnn_thesis/` (Quarto) + `presentation/_shared/` (tema/palette/helper **riusabili** da presentazioni
future) + `figures.py` (ri-stila dai CSV reali) + i 2 hero Manim + `slides.qmd`.

**Provenienza del metodo:** ricerca multi-agente 2026-07-04 (workflow `wie6wol87`, 6 dimensioni + sintesi:
narrativa, carico cognitivo, spiegare a un profano, convenzioni dei talk scientifici, intuizione NN/SNN/PINN,
delivery & tooling). Playbook integrale in scratchpad (`research_playbook.md`), riassunto qui sotto.

---

## 1. Il metodo (dalla ricerca) — le regole che non si violano

**Master resolver — spina vs profondità.** Comprensibilità = proprietà della **spina** (un throughline, un arco
per atto, concreto-prima-di-astratto, budget di gergo). Esaustività = proprietà della **profondità** (build
progressivi, narrazione parlata, le slide `[+]` inline + i deep-dive). Il throughline è l'arbitro: ciò che non lo
fa avanzare va in profondità.

**Assertion-Evidence (Alley).** Ogni slide: **titolo = frase intera con la conclusione** (con il verbo), corpo =
**un solo visual** che la prova. **Zero elenchi puntati.** I titoli letti in fila = l'intero ragionamento.

**ADEPT + concreteness fading (per OGNI concetto).** Analogia → Diagramma → Esempio → Frase-in-italiano →
**formula per ultima**. Se una slide *apre* con l'equazione, è rotta.

**Banca delle analogie (ognuna con il «dove si rompe»):**
| Concetto | Analogia | Dove si rompe |
|---|---|---|
| Neurone LIF | secchio che perde (leaky bucket) | l'uscita è tutto-o-niente; l'ampiezza non porta info, solo il **tempo** |
| ANN vs SNN | dimmer sempre acceso vs interruttore **Morse** | — (semina l'argomento energia) |
| Soglia adattiva (ALIF) | **stanchezza**: dopo lo spike la soglia sale, poi recupera (~100 ms) | è memoria a breve termine, non fatica biologica letterale |
| Ricorrenza + raggio spettrale | **eco nel canyon**: >1 esplode, <<1 dimentica, ~1 memoria utile | il vincolo C11 = "tenere l'eco appena viva" |
| EventProp vs surrogate | il **dirupo**: conti esatti solo negli istanti di spike (adjoint) vs "far finta che sia una rampa" | NON confonderli: erode il contributo del metodo |
| Loss PINN | **due allenatori** (dati + fisica), penalità **soft** | è **inverso** (osservo→deduco), non forward |
| Pesi potenza-di-due + FPGA | "moltiplicare è caro, **scorrere** è gratis" (MAC→shift) | + event-driven: spendi energia solo quando scatta uno spike |
| I 5 parametri | **le abitudini di guida** di un conducente | v0 crociera, T distanza-tempo, s0 gap da fermo, a accel., b frenata |

**Altre regole:** budget di gergo per atto (termini introdotti *just-in-time*, una sola parola per concetto);
**un solo colore-accento** = "questo è il nostro risultato"; **notazione/colore coerenti** nei tre atti;
introdurre ogni figura con **assi → cosa è un punto → cosa guardare** *prima* di rivelare i dati; **profondità
non uniforme** (a fondo su 1-2 idee portanti, superficiale sul resto); **risultati onesti** (baseline giusto,
limiti dichiarati, Pareto come "ciò che è possibile", non "vinciamo").

**Onestà sui NOSTRI numeri (da non tradire):**
- Il fronte di Pareto **non è "battiamo il champion"**: il champion vince la fisica di ~5.5% (`val_data` 0.1926 vs
  best EventProp 0.2031); EventProp vince **NRMSE + stabilità (ρ) + FPGA-friendliness**; **entrambi guidano sicuri**.
- L'edge FPGA di EventProp è **ρ<1 + 0 neuroni morti + AC<MAC**, **NON** la sparsità: la rete spara **~13-19%**
  (non ~1.5%); vantaggio energetico **~5-6×** (non 22-30×) — dopo la correzione del bug `n_ticks` (STATUS §7).

---

## 2. Macro-architettura (Sezione 1 del design, APPROVATA)

**La spina (teal, la percorrono tutti):** cold open → atto 1 (SNN) → atto 2 (la nostra rete) → atto 3 (risultati:
**3A comportamento · 3B FPGA**) → chiusura.

**Il throughline (frase-guida, identica ad apertura e chiusura):**
> *«Una rete spiking «cerebrale» osserva un'auto e ne ricava le 5 impostazioni del suo cruise-control, abbastanza
> efficiente da girare su un FPGA da ~200 €.»*

**Cold open (~60-90 s):** SCQA che apre una *curiosity gap* (le reti neurali sono ovunque → ma consumano troppo
per l'hardware minuscolo → e se una rete «sparasse» a impulsi come un cervello?); presentare subito i 5 parametri
come "abitudini di guida" sulla scena delle due auto. Il gap resta aperto fino alla fine.

**Chiusura (~60 s):** tornare *esattamente* alla domanda d'apertura e chiuderla ("sì — eccola sul PYNQ-Z1") +
*new bliss* (intelligenza al bordo sicura ed efficiente). Ultima slide = **riassunto strategico** (throughline +
2-3 contributi + l'unico numero che conta), non "grazie, domande?".

**Esempio-guida unico (coral):** **una sola traiettoria di car-following** attraversa i tre atti (atto 1 la usa
per motivare i segnali temporali; atto 2 la fa passare nella rete; atto 3 mostra i 5 parametri recuperati e i
risultati su *quella stessa* traiettoria). Massima continuità = massimo taglio del carico cognitivo.

**Profondità (gray):** build progressivi + narrazione parlata + le slide `[+]` **inline alla loro posizione**
(mostrate/nascoste per profilo, **mai un blocco-appendice terminale**).

**Convenzioni trasversali:** indicatore di avanzamento **a 3 punti** (SNN / rete / risultati) su ogni slide, con
l'atto 3 che segnala la **sotto-sezione attiva** (comportamento · FPGA); **slide-recap di raccordo** ai giunti
(atto 1→2, 2→3, **e tra 3A e 3B**); **tag per-slide** `[C]` (spina) vs `[+]` (profondità, inline).

---

## 3. Scaletta slide-per-slide (Sezione 2, APPROVATA)

**Legenda:** `[C]` = core (deck di default) · `[+]` = profondità (inline alla posizione giusta; nel deck completo).
Fonti: `HIW`=`HOW_IT_WORKS_v3`, `VAL`=`VALIDATION_REPORT_v3`, `FPGA`=`FPGA_REPORT`.

### Cold open
| # | tag | assertion (titolo) | visual / evidenza | fonte |
|---|---|---|---|---|
| 1 | C | Titolo + throughline | board PYNQ-Z1 + scena due auto | intro |
| 2 | C | «Nel modo di guidare si nascondono 5 abitudini: le ricaviamo guardando» | scena con `[v0,T,s0,a,b]` etichettati; SCQA | VAL 2.1 |

### Atto 1 — SNN da zero *(pallino 1)*
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 3 | C | «Le reti hanno 3 generazioni; le spiking sono la terza» | timeline 3 generazioni | HIW 1 |
| 4 | C | «Un neurone «tiene un numero», la rete lo trasforma a strati» | sketch ANN | HIW 2 |
| 5 | C | «ANN vs SNN = dimmer sempre acceso vs interruttore Morse (info nel *tempo*)» | dimmer vs spike train | HIW 2 |
| 6 | C | «Il neurone LIF è un secchio che perde: riempi → superi la linea → scatti → svuoti» | **Manim hero #1**; rottura tutto-o-niente | HIW 3 |
| 7 | C | «La soglia adattiva (ALIF) «stanca» il neurone → memoria a breve termine» | spike train che si dirada, soglia che sale | HIW 4 |
| 8 | + | «Dentro è tutto spiking: come si codifica un input continuo» | schema di codifica; anti-equivoci | HIW 5 |
| 9 | C | «La ricorrenza è un'eco: >1 esplode, <<1 dimentica, ~1 = memoria utile» | canyon/eco + raggio spettrale (setup atto 3) | HIW 11 |
| 10 | C | «Ma lo spike non ha derivata → il backprop classico non basta» | il dirupo; cliffhanger | HIW 6 |
| 11 | + | «**Metodo 1**: surrogate gradient + BPTT (il dirupo trattato come rampa)» — *neutro* | rampa sul dirupo | HIW 7 |
| 12 | C | «**Metodo 2**: EventProp — gradiente *esatto* negli istanti di spike (adjoint), più economico» — *neutro; a voce: è una di tre famiglie* | **Manim hero #2** forward/adjoint | HIW 8 |
| 13 | + | «**Metodo 3**: STDP — apprendimento biologico locale, «chi scatta insieme si lega», non supervisionato» — *neutro, nessuna denigrazione* | STDP Hebbiano | HIW 9 |

> **Nota (correzione utente):** l'Atto 1 descrive le SNN **in generale** → i tre metodi sono presentati **neutri**.
> Il "no all'STDP" è un verdetto **specifico della nostra rete** e si sposta nell'Atto 2 / profondità.

*→ slide-recap di raccordo Atto 1→2*

### Atto 2 — la nostra rete *(pallino 2)*
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 14 | C | «È un problema **inverso**: osservo la traiettoria, deduco i 5 parametri» | traiettoria→?→5 param; preempt PINN-forward | VAL 2.1 |
| 15 | C | *answer-first*: «La nostra rete: spiking ricorrente, fisica-informata, EventProp, che identifica i 5 param ACC» | **SCHEMA MASTER** (traiettoria→core ALIF ricorrente→5 uscite), riusato | HIW 10 |
| 16 | C | «La loss PINN = due allenatori (dati + fisica), penalità *soft*, 5 componenti» | schema con loss `data/phys/ou/bc/sr` | HIW 12 |
| 17 | + | «Il bersaglio fisico: il modello ACC-IIDM» | equazione IIDM, i 5 param dentro | HIW 13 |
| 18 | C | «Ricorrenza low-rank: memoria potente ma economica (rank 8)» | highlight sullo schema | HIW 10 |
| 19 | C | «Pesi potenza-di-due: «moltiplicare è caro, scorrere è gratis» → FPGA-economica» | MAC vs shift | HIW 15 |
| 20 | + | «Come si quantizza senza rompere il training: Straight-Through Estimator» | STE | HIW 15 |
| 21 | C | «Un vincolo sul raggio spettrale tiene l'eco «appena viva» → stabile per costruzione (C11)» | ρ vincolato ~0.5; callback slide 9 | HIW 11 |
| 22 | + | «Il triangolo: ogni scelta (ALIF/po2/low-rank/EventProp) rilegge le altre» | triangolo di sintesi | HIW 17 |

> A voce sulla slide 15: *perché EventProp per il nostro problema inverso, e non STDP (non supervisionato, non
> mira ai 5 parametri → limite di identificabilità)*; slide di *descend* accanto (`HIW 9`).

*→ slide-recap di raccordo Atto 2→3*

### Atto 3 — i risultati *(pallino 3)*

**Apertura dell'atto:**
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 23 | C | recap + *answer-first*: «Funziona ed è distribuibile» + come leggiamo (evaluate 6-tier, 4 champion + oracolo) | scorecard/legenda champion | VAL 1/3 |
| 24 | C | **MONEY SLIDE**: «Non «vinciamo»: siamo su un **fronte di Pareto** — cediamo ~5.5% di fisica (0.203 vs 0.193), guadagniamo stabilità + FPGA-deployability; **entrambi guidano sicuri»** — apre le due sotto-sezioni | Pareto con build; punto operativo cerchiato = Donatello | VAL 2.2/10 |

**3A — Validazione: il comportamento fisico** *(sotto-pallino: comportamento)*
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 25 | C | «Identifichiamo bene i 5 parametri; dove ciascuno diventa osservabile» | tabella per-canale + stratificazione | VAL 4.1/4.2 |
| 26 | + | «a e b sono strutturalmente accoppiati (FIM, equifinalità): un limite onesto» | ellisse a-b / FIM | VAL 4.3 |
| 27 | C | «In closed-loop siamo sicuri come l'oracolo: 0 collisioni, min-gap preservato» — con «cosa ancora fallisce» | min-gap vs oracolo | VAL 5 |
| 28 | + | «Robustezza fisica: asciutto/bagnato/ghiaccio + curva di rottura (il ghiaccio è un limite del *plant*, ~60% coll. anche per l'oracolo)» | plant + breakdown | VAL 6 |
| 29 | + | «Nel traffico: string stability, plotone di 12, diagramma fondamentale» | micro→meso→macro | VAL 7 |
| 30 | + | «V2X: l'hold-last-CAM maschera la perdita pacchetti; da sola la rete è insicura (blind 0.67 coll.)» | canale V2X | VAL 8 |
| 31 | C | «La stabilità è *misurata*: ρ EventProp 0.05-0.39 vs BPTT 1.16-2.99; 0 gradienti infiniti; 0 neuroni morti» | discriminante di stabilità; callback eco | VAL 9.3 |
| 32 | + | «Solidità dello studio: multi-seed (std 0.0011), copertura dataset» | seed/dataset | VAL 11 |

*→ mini-recap di raccordo 3A→3B (dal comportamento all'hardware)*

**3B — Validazione FPGA: l'hardware** *(sotto-pallino: FPGA)*
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 33 | C | «Sull'FPGA: 0 DSP, <1% BRAM, ~5-6× energia → sta sul PYNQ-Z1» | scorecard readiness | FPGA 0/4/6 |
| 34 | C | «La quantizzazione po2 è FPGA-ready: perdita trascurabile (QAT ≤ float su 3/4)» | delta quantizzazione | VAL 9.1 · FPGA 1/2 |
| 35 | + | «Onestà sull'energia: il vantaggio è AC<MAC + ρ<1 + 0 morti, **non** la sparsità (spara ~13-19%)» | energy AC<MAC + nota correzione | FPGA 4/3 |
| 36 | + | «Sicurezza automotive: SEU/ISO 26262, jitter zero sul deadline, TMR mirato» | SEU/timing | FPGA 5/7 |

### Chiusura
| # | tag | assertion | visual | fonte |
|---|---|---|---|---|
| 37 | C | «Sì: una rete «cerebrale» gira su una board da ~200 € — verso un'intelligenza al bordo sicura ed efficiente» | risposta simmetrica + new bliss | VAL 10 |
| 38 | C | **Riassunto strategico**: throughline + 3 contributi + l'unico numero (resta a schermo per le domande) | summary | — |

**Conteggio:** **25 slide `[C]` = deck di default.** **13 slide `[+]`** (8, 11, 13, 17, 20, 22, 26, 28, 29, 30, 32,
35, 36) = profondità **inline alle loro posizioni**, mostrate nel deck completo (per i superiori) / in Q&A.

### Profondità inline (il serbatoio, alle posizioni giuste)
Le slide `[+]` **non** formano un blocco terminale: stanno **inline alla loro posizione numerata** (la 8 tra la 7
e la 9, la 26 subito dopo la 25, ecc.) e si mostrano/nascondono per **profilo** (deck ridotto = solo `[C]`; deck
completo = `[C]`+`[+]`). I deep-dive più tecnici vivono come slide di *descend* **accanto al concetto relativo**
(non in coda): adjoint di EventProp (dopo la 12) · loss a 5 componenti in dettaglio (dopo la 16) · ACC-IIDM
completo (17) · discriminante/prova di stabilità ρ (dopo la 31) · generatore dati + copertura (dopo la 25/32) ·
STE / Qm.n (dopo la 20/34) · budget risorse PYNQ-Z1 LUT/BRAM/energia (dopo la 33) · SEU/TMR (36) · WCET/timing ·
termico · «perché EventProp e non STDP» (dopo la 15) · config champion + caveat baseline ckpt-pass (STATUS §9.4).

---

## 4. Workflow di build (Sezione 3, APPROVATA)

**Pipeline:** `risultati CSV` + `champions/` + `script Manim` → (`figure.py` restyle Okabe-Ito · `MP4 hero`) →
`slides.qmd` (Quarto) → `reveal.js` (deck HTML) + `PDF statico` (fallback).

1. **Figure dai dati reali, mai ri-eseguendo i job.** `presentation/figures.py` legge gli **stessi CSV** dei
   report (`results/…`) e i `champions/` locali, e li **ri-stila per il palco** (font grandi, de-junk alla Tufte,
   un solo accento, build progressivi). DRY, deterministico, **niente Azure, nessun numero inventato**.
2. **Quarto = sorgente unica** (`slides.qmd`): math MathJax, reveal incrementali; al render **esegue Python** →
   figure sempre fresche (niente "figura vecchia").
3. **Due hero Manim** pre-renderizzati in MP4 e incorporati: secchio LIF (carica→scatta→svuota) e forward/adjoint
   di EventProp. (3° eventuale — autovalori del raggio spettrale che si contraggono — **rinviato**.)
4. **Palette Okabe-Ito** (color-blind safe) con identità-champion (Raffaello→vermiglio, Leonardo→blu,
   Donatello→viola, Michelangelo→arancio, oracolo→grigio) + **codifica ridondante** colore + tratteggio + marker
   → il Pareto si legge anche in scala di grigi e per chi ha CVD.
5. **Robustezza in aula:** export **PDF statico** come fallback proiettore (build appiattiti; per gli hero, un
   frame-chiave al posto del video). Regola ferrea: **nessuna demo live** (training/sim/board) — sempre il video.
6. **Dove vive:** `presentation/cf_fsnn_thesis/` nel repo CF_FSNN (sottocartella dedicata; `presentation/_shared/`
   raccoglie tema/palette/helper **riusabili da presentazioni future**). Build **100% locale** → **push solo quando
   Azure è fermo**, commit **senza Co-Authored-By**.
7. **Profondità inline via profilo (reduced/full).** Le slide `[+]` sono **taggate** e restano **alla loro
   posizione** nel flusso; un profilo Quarto/reveal le **mostra** (deck completo per i superiori) o le **salta**
   (deck ridotto ~25). Meccanismo: attributo/classe per-slide + condizione di render (es. parametro Quarto o
   stack verticali reveal.js), un solo `slides.qmd` sorgente per entrambi i deck.

**Layout file proposto:**
```
presentation/
  _shared/                    # RIUSABILE tra presentazioni future
    theme/                    # tema reveal.js (SCSS) + palette Okabe-Ito + font
    figures_common.py         # helper di restyle condivisi (palette, mapping champion, stile assertion-evidence)
    manim_common/             # scene/utility Manim condivise
  cf_fsnn_thesis/             # QUESTA presentazione (sottocartella dedicata)
    slides.qmd                # sorgente unica (Quarto → reveal.js), tag [C]/[+] per profilo reduced/full
    figures.py                # legge i CSV di results/ + champions/, ri-stila per il palco (usa _shared)
    _quarto.yml               # config: reveal.js, tema (da _shared), incremental, MathJax, profili
    assets/
      manim/                  # LIF_spike.mp4, eventprop_adjoint.mp4 (pre-renderizzati)
      img/                    # board PYNQ-Z1, scena due auto
    figures/                  # PNG/SVG rigenerati da figures.py
    _output/                  # deck HTML + PDF statico (gitignored)
scripts/manim/                # sorgenti Manim (LIF_spike.py, eventprop_adjoint.py)
```

**Lingua:** slide in **italiano** con i termini tecnici chiave **anche in inglese** tra parentesi (imparabili e
ricercabili); **esposizione in italiano**.

**Consegna / "testing" della presentazione:** check color-blind (simulatore) + contrasto WCAG (≥4.5:1 testo
piccolo) + font ≥18-24 pt; **prove a voce a cronometro** (≥3 run, budget ~10% per Q&A); **mai sforare**
(gli sforamenti rubano tempo all'Atto 3).

---

## 5. Mappa contenuti → fonti (trio v3)

| Atto | Fonte | Sezioni |
|---|---|---|
| ① SNN da zero | `HOW_IT_WORKS_v3` Parte I | 1 generazioni · 2 ANN vs SNN · 3 LIF · 4 ALIF · 5 codifica · 6 perché no backprop · 7 surrogate+BPTT · 8 EventProp · 9 STDP |
| ② la nostra rete | `HOW_IT_WORKS_v3` Parte II | 10 architettura · 11 raggio spettrale ρ(U·V) · 12 loss PINN 5-comp · 13 ACC-IIDM · 14 generatore · 15 po2/STE · 17 triangolo |
| ③ 3A comportamento | `VALIDATION_REPORT_v3` | 2.2 Pareto · 4 identificazione · 5 sicurezza · 6 robustezza fisica · 7 traffico · 8 V2X · 9.3 stabilità · 10 verdetto/deploy · 11 solidità |
| ③ 3B FPGA | `FPGA_REPORT` (+ VAL 9.1) | 0 scorecard · 1 po2 · 2 fixed-point · 3 sparsità/salute · 4 energia · 5 timing · 6 risorse · 7 SEU · 8 I/O · 9 termico |

**Champion (per la legenda dell'Atto 3):** Raffaello `R33_C2_A1_T12_fix` (baseline Prodigy, rosso) · Leonardo
`LS3_PEAK_R0_launch_d03` (champion BPTT, blu) · Donatello `PE_t05_gp0002` (eventprop, best-NRMSE 0.152, viola,
**candidato deploy**) · Michelangelo `A_lr1e2_t06_r16` (eventprop, best-Adam 0.2031, arancio) · Master Splinter
(oracolo, grigio).

---

## 6. Nodi aperti per l'implementazione (non ora)

- **Verificare quali CSV esistono in locale** (`results/evaluate/v3_TURTLE_POWER!!!/`, `results/evaluate/FPGA/`)
  per rigenerare le figure senza Azure; se qualcuno è solo su Azure, rigenerarlo una volta e cacharne il CSV.
- **Meccanismo profilo reduced/full** in Quarto (parametro di render vs stack verticali reveal.js) — scegliere in
  implementazione.
- **Piano minuti per-slide** (a cronometro) una volta bozzato il deck.
- **3° hero Manim** (raggio spettrale) — decidere se vale il costo.
- **Sorgenti Manim**: scrivere `LIF_spike.py` e `eventprop_adjoint.py` (o partire da matplotlib animato se il
  costo Manim è troppo per la scadenza).

---

## 7. Riferimenti

- **Metodo:** ricerca multi-agente `wie6wol87` (2026-07-04); playbook in scratchpad `research_playbook.md`.
  Framework portanti: Minto spina-vs-profondità · Assertion-Evidence (Alley) · ADEPT + concreteness fading ·
  Duarte Sparkline + ABT · analogia structure-mapping (Gentner) · risultati onesti (Peyton Jones).
- **Contenuti:** `document/HOW_IT_WORKS_v3.md/.pdf`, `document/VALIDATION_REPORT_v3.md/.pdf`,
  `document/FPGA_REPORT.md/.pdf`; stato del progetto in `document/EVENTPROP_STATUS.md` §0.
- **Tooling:** Quarto (reveal.js backend) · Manim · palette Okabe-Ito · PYNQ-Z1.

> **Nota di ripresa:** questo è il design **approvato**. Prossimo passo = sessione di implementazione
> (writing-plans) su questo documento. Il contenuto esiste già nel trio v3; il grosso è viz + build + le figure
> ri-stilate dai CSV.
