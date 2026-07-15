# SIMULATOR_DESIGN — Simulatore plug&play (Fase ①): design MVP v1 + piano di adozione

> **Data:** 2026-07-02 · **Branch:** `EventProp_Study` · **Stato (allora):** design approvato, non ancora
> implementato. · **Stato OGGI: ✅ IMPLEMENTATO ed ESTESO ben oltre questo MVP** — vedi il banner sotto e
> `document/SIMULATOR_SESSION_RESUME.md`. **Questo file è un record STORICO**: le frasi al presente qui
> dentro ("non implementato", "prima di scrivere codice…") vanno lette come *"al 2026-07-02"*.
>
> Questo documento chiude la sessione di design della **Fase ①** (la prima delle 3 fasi post-FPGA, vedi
> `document/POST_FPGA_ROADMAP.md`). Registra: le **decisioni bloccate**, il **design dell'MVP v1**, e il
> **piano di adozione** dagli strumenti esistenti (dalla ricerca web multi-agente del 2026-07-02).
> **Prima di scrivere codice**, aprire una sessione di implementazione (writing-plans) su questo design.

> **🏁 AGGIORNAMENTO (2026-07-13) — questo design È STATO IMPLEMENTATO ed ESTESO ben oltre l'MVP v1.**
> L'MVP v1 qui descritto è stato costruito (Plans 1–4, 2026-07-06/07) e poi esteso fino a un cockpit a
> **3 modi / 13 dock** (Live + Meso/Macro + Post-run) con deep-scrub, grafo node-link, energia SynOps,
> selettore champion e dashboard post-run — ora a una **milestone** (2026-07-13, 148 test). **Questo file
> resta come record storico del design iniziale.** Per lo **stato attuale** vedi
> **`document/SIMULATOR_SESSION_RESUME.md`** + il roadmap `docs/superpowers/2026-07-07-simulator-extension-study.md`.
> NB: alcune scelte v1 sono state superate — es. il raster spike → grafo node-link; il dock v_mem →
> assorbito nell'Inspector (nessun dock v_mem separato).

---

## 0. Come riprendere (leggere prima questo)

**Cos'è la Fase ①:** un **simulatore desktop plug&play** per reti SNN che **identificano parametri**. Carichi un
checkpoint, scegli uno scenario, lui simula mostrando **(a)** le auto dall'alto in tempo reale e **(b)** la rete
in diretta (spike/membrana/5 parametri), e puoi **iniettare eventi live** (es. "frena il leader"). È il *driver*
della Fase ③ (FPGA-in-the-Loop): nasce con un seam `NetworkBackend` (SW oggi | FPGA domani).

**Stato:** design MVP v1 **approvato**, non implementato. **Prossima azione:** sessione di implementazione
(writing-plans) su questo doc. Il backend di calcolo esiste già (`utils/closed_loop_eval.py` ecc.); il lavoro è
viz + UI + le astrazioni.

**Le 4 decisioni fondative (bloccate in questa sessione):**
1. **Stack desktop = PySide6 (LGPL) + pyqtgraph (MIT).** Un solo framework copre top-down + pannelli rete + widget;
   `QThread` è il seam pulito per l'FpgaBackend (③); massima maturità/riuso cross-progetto.
2. **Scope v1 = MVP snello.** Il cuore interattivo; rinvia EstimationQuality, UKF live, scenari dichiarativi.
3. **Loop = single-thread** (QTimer + accumulatore fixed-timestep "Fix-Your-Timestep"), **senza** interpolazione in
   v1. Il contratto `NetworkBackend` resta sincrono/thread-agnostic → il QThread arriva con l'FpgaBackend, non ora.
4. **v_mem esposto via attributi diretti** dell'`ALIFCell` (`potential`, `fatigue`, `prev_spike`) — **zero modifiche
   alla rete** (pattern AttributeMonitor).

---

## 1. Decisioni bloccate (con il perché)

| # | Tema | Decisione | Perché |
|---|---|---|---|
| ① | stack desktop | **PySide6 + pyqtgraph** | un framework per top-down+plot+widget; QThread = seam ③; maturità/riuso |
| ① | scope v1 | **MVP snello** | YAGNI: valore interattivo subito, seam pronti per il resto |
| ① | loop/threading | **single-thread** (QTimer + accumulatore) | forward SW velocissimo per pochi veicoli; niente bug threading ora |
| ① | interpolazione render | **no in v1** | pochi veicoli, dt modesto; si aggiunge se serve visivamente |
| ① | v_mem / probe | **attributi diretti ALIF** (AttributeMonitor) | `potential/fatigue/prev_spike` già live in-place; zero intrusione |
| ① | seam identify | **`NetworkBackend` fa forward+identify** (Identifier esplicito rinviato) | in v1 la SNN è l'unico identificatore; il seam Identifier serve con il baseline classico |
| ① | pannello rete | **3 viste**: raster spike · v_mem · 5 parametri | è ciò che si vuole "in diretta" |

Architettura a interfacce **SOLID/DIP**: il loop dipende solo dalle astrazioni; le estensioni (altri
car-following, controllo laterale, FpgaBackend) sono nuovi impl dietro le stesse interfacce.

---

## 2. Architettura a componenti (interfacce + impl v1)

| Componente | Ruolo | v1 | Riusa / seam |
|---|---|---|---|
| **`SimStepper` + `SimState`** | motore closed-loop a **passo singolo** | refactor di `simulate()` | `_plant_step`, `_channel_obs`, `acc_iidm_accel` |
| **`NetworkBackend`** (Protocol) | `reset · set_input→step→get_output→5param · probeable · read_probe` | `SoftwareBackend` (wrappa `model.forward_step`+`reset_state`); `FpgaBackend` = **stub** | `make_backend(target)`; contratto **sincrono/thread-agnostic** |
| **`CarFollowingModel`** | (param+stato)→accel; **registry** | solo **ACC-IIDM** | `CF_FSNN_Net.acc_iidm_accel`; IDM rinviato |
| **`Scenario`** | genera scenario/profilo leader | wrappa `build_scenarios` + manuale | `closed_loop_eval.build_scenarios` |
| **`EventInjector`** | coda eventi drenata a ogni step | verbo **`brake_leader`** (=`slow_down(v,dur)`) da bottone | ordine deterministico; flag `control_source` |
| **`AttributeProbe`** | snapshot `potential/fatigue/prev_spike` → **ring-buffer** | per-passo (granularità n_ticks configurabile) | `net_diagnostics._last_hidden` |
| **`Renderer`** (PySide6) | vista top-down + pannelli rete | `QGraphicsView` + pyqtgraph | legge **snapshot immutabili** |
| **`ReplayLog`** | seed + event-log → rerun bit-identico | sì (loop già deterministico) | — |

**Contratto `NetworkBackend` (firma da fissare, fusione FMI + Rockpool + Nengo):**
```
NetworkBackend (Protocol):
    __init__(config, dt)
    init() / reset()
    set_input(obs) -> step(dt) -> get_output()   # -> 5 parametri [v0,T,s0,a,b]
    probeable: dict[target -> list[attr]]          # introspezione dichiarativa (Nengo)
    read_probe(spec) -> array                       # spike | v_mem | param_5
```
Factory alla composition root: `make_backend(target="software"|"fpga"|None)`; `None` → auto-fallback (FPGA se PYNQ
raggiungibile, altrimenti Software). Il loop **non conosce** il compute target.

---

## 3. Il cuore — `SimStepper` (refactor single-step di `simulate()`, costo BASSO)

**Verificato** leggendo `utils/closed_loop_eval.py:139-221`: `simulate()` è già un `for t in range(N)` pulito, con
**tutto lo stato mutabile in variabili/dict espliciti**: `s, v, a_l_filt, vl_prev` (scalari) + `pl_state` (plant) +
**`ch_state` / `ch_rng` (canale V2X, ritardo incluso)** + lo stato interno del modello (resettato una volta). Il
ritardo-V2X NON rompe la purezza dello step perché `ch_state` è già un dict esternalizzato.

**Refactor:** si hoista l'init (`closed_loop_eval.py:153-167`) in `SimState`; `step(events) -> StepResult` esegue il
corpo del loop (`closed_loop_eval.py:171-211`) su quello stato. Punti d'inserzione:
- **eventi**: riga 171 (dove oggi c'è il check `cut_in` pre-schedulato → diventa "drena la coda eventi");
- **backend**: riga 185 (`model.forward_step(obs)→params` → `backend.set_input/step/get_output`).

`StepResult` è immutabile: posizioni veicoli, 5 parametri stimati, snapshot probe, flag (collisione, control_source).

> **Ancora di regressione (test d'oro):** senza eventi e con `SoftwareBackend`, `SimStepper` deve riprodurre
> `simulate()` batch **bit-identico**. È l'invariante di correttezza del refactor.

La fisica usa `vl` **VERO** (non osservato): il canale V2X degrada solo la *percezione* del controllore. Mantenere
questa separazione nello `SimStepper`.

---

## 4. Data flow del loop (single-thread, Fix-Your-Timestep)

```
QTimer.tick
  └─ accumulatore consuma dt fisso (Fix-Your-Timestep; niente interpolazione in v1)
       └─ SimStepper.step(eventi drenati) -> StepResult (immutabile)
            ├─ Renderer.top-down  <- posizioni veicoli (QGraphicsView, item ruotato)
            └─ Renderer.netpanel  <- snapshot probe (pyqtgraph: raster / v_mem / 5-param)
Bottone "frena il leader"  -> EventInjector.enqueue(Event)  -> drenato al passo successivo
Pausa/scrub  -> lettura dal ring-buffer degli ultimi N passi
```

**Fix-Your-Timestep** (Glenn Fiedler): la fisica avanza a `dt` deterministico mentre il render gira a ~60 FPS;
l'accumulatore assorbe il jitter del timer. Interpolazione tra snapshot rinviata (pochi veicoli non la richiedono).

---

## 5. Pannello rete live + probe

`AttributeProbe` fa lo snapshot degli attributi ALIF **dopo lo step** (o ogni `sample_every` passi — disaccoppia il
refresh UI dal `dt` fisico ~0.01s, pattern `nengo.Probe`), in un **ring-buffer** di N passi. Tre viste pyqtgraph:
- **raster spike** ← `prev_spike`
- **traccia v_mem** ← `potential` (con soglia effettiva `base_threshold + fatigue.clamp(min=0)`)
- **5 parametri stimati** nel tempo ← output del backend

Lo `synapse`/smoothing si applica **solo a valle nel Renderer**, mai nel backend (che restituisce il dato grezzo).
**Granularità n_ticks:** `forward_step` gira `n_ticks` micro-step per passo di controllo → il probe espone per-passo
(default) o per-tick (opzione), da fissare nel contratto. **Nota:** il nodo `dt_plant ↔ n_ticks_SNN` è già stato
fonte del bug spike-rate del progetto ([EVENTPROP_STATUS.md](EVENTPROP_STATUS.md) punto 7) → definirlo con cura.

---

## 6. Eventi live + replay deterministico

- **`Event(tick, verbo, target)`**; coda a **ordine stabile** (a parità di tick, ordine d'inserzione) drenata a ogni
  step. Vocabolario dei verbi ispirato a **TraCI**; v1 espone `brake_leader` (=`slow_down(v,duration)`, frenata
  graduale del leader).
- **`control_source {USER_OVERRIDE | MODEL}`** per veicolo; feedback visivo (colore del veicolo). `release_to_model`
  (=`setSpeed(-1)` di TraCI) restituisce il controllo al `CarFollowingModel` — rinviato oltre `brake_leader` in v1.
- **`ReplayLog`**: salva `seed + lista-eventi`; il rerun riproduce la sessione **bit-identica** → banco-prova
  scientifico ripetibile (requisito, non accessorio: elevato a tale su indicazione della critica di ricerca).

---

## 7. Layout moduli (file piccoli, alta coesione)

```
sim/
  __init__.py
  state.py        # SimState, StepResult (dataclass immutabili)
  stepper.py      # SimStepper: corpo del loop single-step (riusa i primitivi di closed_loop_eval)
  backend.py      # NetworkBackend (Protocol), SoftwareBackend, FpgaBackend (stub), make_backend()
  models.py       # CarFollowingModel registry (ACC-IIDM in v1)
  scenario.py     # Scenario: wrappa build_scenarios + scenario manuale
  events.py       # Event, EventInjector, verbi (brake_leader)
  probe.py        # ProbeSpec, AttributeProbe (ring-buffer su potential/fatigue/prev_spike)
  replay.py       # ReplayLog (seed + event-log)
  ui/
    app.py        # shell QApplication: carica checkpoint, scegli scenario, run/pausa, inietta evento
    topdown.py    # renderer top-down (QGraphicsView, item veicolo ruotato)
    netpanel.py   # pannelli rete (pyqtgraph: raster / v_mem / 5-param)
    loop.py       # driver QTimer + accumulatore fixed-timestep
scripts/
  run_simulator.py   # entry point
tests/
  test_sim_stepper.py   # GOLDEN: bit-identico vs simulate() batch (no eventi)
  test_sim_events.py    # determinismo della coda eventi
  test_sim_replay.py    # riproducibilità del replay (seed+event-log)
```

---

## 8. Error handling + testing

- **Checkpoint plug&play → schema-detection OBBLIGATORIA.** Il loader deve distinguere baseline **rank-8** vs
  eventprop **rank-16** (famiglia). È il bug del ckpt-pass del progetto: caricare un baseline come
  `eventprop_alif_full` → **readout random silenzioso** (caveat §9.4 di `EVENTPROP_STATUS.md`). Validare
  famiglia/rank **prima** di istanziare; fallire con messaggio chiaro se il checkpoint non è riconosciuto.
- **Backend timeout.** Il contratto `step()` prevede una deadline (no-op in v1 SW; diventa il wrapper di
  `DMA.wait()` — bloccante — per l'FpgaBackend, con degrade al SoftwareBackend).
- **Test (80%+ sul nuovo codice):** golden bit-identico (`SimStepper` vs `simulate()`), determinismo coda eventi,
  riproducibilità replay; smoke-test headless della UI (istanziazione senza display).

---

## 9. Fuori da v1 (rinviato, seam già pronti)

| Rinviato | Riattiva la domanda §E |
|---|---|
| **EstimationQuality** (baseline classico scipy `least_squares` + covarianza JᵀJ + FIM/Cramér-Rao + ellisse a-b) | — (nuovo sottosistema; mostra *perché* a/b non si separano) |
| **OnlineIdentifier** (UKF `filterpy` a stato aumentato, re-identify live post-evento) | **UKF vs MHE** (do-mpc) |
| **Scenari dichiarativi + trigger-condition** (condizione→azione, pattern OpenSCENARIO) | **formato Scenario** (estendere `build_scenarios`?) |
| **IDM nel registry** (`highway-env` `IDMVehicle.acceleration`, come validazione/leader) | — |
| **Controllo laterale / MOBIL** (stato 2D + cambio-corsia) | — (progettare le posizioni **2D (x,y)+heading** già in v1 per non ostacolarlo) |
| **QThread** (loop su worker + snapshot immutabili) | — (arriva con l'FpgaBackend, Fase ③) |

---

## 10. Piano di adozione dagli strumenti esistenti (dalla ricerca 2026-07-02)

Ricerca web multi-agente (5 dimensioni → 38 tool → verifica avversariale dei 12 candidati top, 8 confermati / 0
smentiti). Solo cose che **non** avevamo già; ogni voce verificata sui doc ufficiali.

**In v1 (P0):**
| Feature/Pattern | Da dove | Nostra astrazione | Modo |
|---|---|---|---|
| Stack top-down + plot + widget in un framework | **PySide6 + pyqtgraph** | Renderer | adopt-dep |
| Firma backend `init/reset/set→step→get` | **FMI/FMU** + Rockpool | NetworkBackend | port-pattern |
| Target-arg + auto-fallback HW→SW | **Nengo** (`target='sim'\|'loihi'`) | backend factory | port-pattern |
| ProbeSpec dichiarativo (`sample_every`) | **nengo.Probe** | Renderer + `probeable` | port-pattern |
| Hook per-layer zero-intrusione (spike/v_mem) | **SpikingJelly** monitors | SoftwareBackend | port-pattern |
| Tassonomia verbi eventi live | **SUMO TraCI** | EventInjector | port-pattern |
| Blueprint viewport top-down (mondo→pixel, veicolo ruotato) | **highway-env** `pos2pix`/`blit_rotate` | Renderer | port-pattern |
| Fix-Your-Timestep (accumulatore) | **Glenn Fiedler** (gafferongames) | loop driver | port-pattern |
| Replay deterministico (seed+event-log) | pattern event-sourcing | ReplayLog | port-pattern |

**Rinviato (P1/P2):** firma env `reset/step→(state,info)` **stile** Gymnasium (non ereditare `Env`) · baseline
`scipy.least_squares`+`lmfit` · UKF `filterpy` · FIM/Cramér-Rao (numpy) · IDM di `highway-env` · trigger-condition
(OpenSCENARIO/ScenarioRunner) · `pyqtgraph.RemoteGraphicsView` (valutare prima del QThread manuale, con l'FPGA).

**Correzioni verificate (da non perdere in implementazione):**
- `highway-env` `IDMVehicle.acceleration()` è **metodo d'istanza** `(self, ego, front, rear)`, **non** classmethod;
  `DISTANCE_WANTED = 5.0 + LENGTH` (non 10). Rifattorizzare estraendo `target_speed`/`LENGTH` in argomenti espliciti.
- QGraphicsView: **flip dell'asse Y** (mondo y-su vs scena Qt y-giù) e **logica-camera** che segue l'ego
  (`centerOn`/`setTransform` per-frame) NON sono "gratis" — vanno messe a budget.
- (Se mai Dear PyGui) bug `#2382`: `configure_item()` ignora la traslazione della matrice → animare con
  `apply_transform()`.

**Esclusi (verificati):** matplotlib/FuncAnimation (blitting incompatibile con scena che scorre), pygame-solo
(no widget/plot), Streamlit/Panel/Bokeh/Kivy (web o rerun-model, incompatibili con loop stateful + eventi live),
Intel Lava come dipendenza (**libreria archiviata da Intel, mag-2026** → solo pattern), MATLAB HDL Verifier FIL
(farebbe di MATLAB il driver → due simulatori; scartato già in `POST_FPGA_ROADMAP.md`).

---

## 11. Domande aperte residue (per l'implementazione / le versioni successive)

- **v1:** default di `sample_every` e dimensione del ring-buffer del probe; granularità del probe (per-passo vs
  per-tick); lista degli scenari esposti in v1 (quali `build_scenarios` + il manuale); dimensione/scala della vista
  top-down (metri visibili, follow-ego vs fixed).
- **Rinviate (riattivate dalle feature P1/P2):** UKF vs MHE per il re-identify live; formato Scenario dichiarativo;
  modalità step del seam FPGA (lockstep-con-timeout vs free-running+polling) — da decidere quando si costruisce
  l'FpgaBackend (Fase ③).

---

## 12. Riferimenti

**Provenance ricerca:** workflow multi-agente `wf_1b8fb60f` (2026-07-02, 19 agenti, 5 dimensioni: SNN-infra ·
viz-desktop · traffico · identificazione · HW-backend). Fonti primarie verificate agent-per-agent (doc/repo
ufficiali).

**Tool chiave (fonti primarie):**
- PySide6 (Qt for Python, LGPL) · pyqtgraph (MIT) — GUI + plotting real-time desktop.
- Nengo / NengoLoihi (`target='sim'|'loihi'`, `nengo.Probe`) — pattern backend-swap + probe dichiarativo.
- SpikingJelly `activation_based.monitor` (AttributeMonitor) — hook per-layer zero-intrusione.
- SUMO TraCI — vocabolario verbi di controllo live (`setSpeed`, `slowDown`, `setSpeed(-1)`).
- highway-env (Farama) — `IDMVehicle.acceleration()`, `WorldSurface.pos2pix`, `VehicleGraphics.blit_rotate`.
- Gymnasium (Farama) — firma `reset()/step()` come API riusabile del plant (rinviata).
- Glenn Fiedler, "Fix Your Timestep!" (gafferongames.com) — accumulatore fixed-timestep.
- PYNQ (Overlay/MMIO/allocate/DMA) — lifecycle dell'FpgaBackend (Fase ③).
- FMI/FMU · Rockpool (XyloSim↔XyloSamna) — contratto backend `init/reset/set→step→get`.

**File del progetto rilevanti:**
- Backend riusato: `utils/closed_loop_eval.py` (`simulate`, `build_scenarios`, `_plant_step`, `_channel_obs`),
  `scripts/closed_loop_identify.py` (`identify`), `utils/snn_showcase.py`, `utils/net_diagnostics.py`
  (`_last_hidden`, `spike_raster`).
- Rete: `core/neurons.py` (`ALIFCell`: attributi `potential`/`fatigue`/`prev_spike`), `core/network.py`
  (`forward_step`, `n_ticks`), `core/{eventprop,hardware}.py`.
- Contesto fasi: `document/POST_FPGA_ROADMAP.md` (§1 = Fase ①), `document/EVENTPROP_STATUS.md` (punto 6 + punto 7).

> **Nota di ripresa:** questo è il design **approvato** dell'MVP v1. Prossimo passo = sessione di implementazione
> (writing-plans) su questo documento. Il backend di calcolo esiste già; il grosso è viz + UI + le astrazioni.
