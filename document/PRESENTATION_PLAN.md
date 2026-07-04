# Presentazione CF_FSNN — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** costruire il deck Quarto/reveal.js della presentazione CF_FSNN (3 atti, 38 slide, profilo ridotto ~25 + completo) descritto in `document/PRESENTATION_DESIGN.md`, con figure ri-stilate dai CSV reali e 2 animazioni hero.

**Architecture:** una sottocartella `presentation/cf_fsnn_thesis/` con sorgente unica `slides.qmd`; uno strato condiviso `presentation/_shared/` (tema reveal.js + palette Okabe-Ito + helper di restyle) riusabile da presentazioni future; le figure sono rigenerate **in locale** da `figures.py` leggendo i CSV in `results/evaluate/`; le 2 animazioni hero sono GIF prodotte con matplotlib+Pillow; i profili *reduced*/*full* mostrano/nascondono le slide `[+]` via `content-visible when-profile`.

**Tech Stack:** Quarto (output reveal.js) · Python 3.13 + matplotlib 3.10 / numpy / pandas / Pillow (già presenti in locale) · animazioni matplotlib→GIF (writer Pillow, niente manim/ffmpeg) · palette Okabe-Ito (color-blind safe).

**Riferimenti di contenuto (NON duplicati qui):** la scaletta slide-per-slide (titoli assertion-evidence, tag `[C]/[+]`, fonti) è in `document/PRESENTATION_DESIGN.md` §3; le regole di metodo/analogie in §1; i numeri esatti nel trio v3. Questo piano costruisce l'**infrastruttura** e definisce i **template**; il contenuto di ogni slide si prende dallo storyboard §3.

---

## Struttura dei file (cosa crea/modifica ogni file)

```
presentation/
  _shared/
    theme/
      cf_theme.scss           # tema reveal.js: font grandi, palette accento, spaziatura
    figures_common.py         # palette Okabe-Ito, mapping champion (colore+tratteggio+marker), rcParams "palco", loader CSV
    manim_common/
      anim_style.py           # stile condiviso per le GIF (font, dpi, colori)
  cf_fsnn_thesis/
    _quarto.yml               # config reveal.js + profili reduced/full + MathJax + tema da _shared
    slides.qmd                # sorgente unica del deck (38 slide, tag [C]/[+])
    figures.py                # rigenera/ri-stila TUTTE le figure dai CSV/PNG → figures/
    assets/
      img/                    # board PYNQ-Z1, scena due auto (statiche)
      manim/                  # lif_spike.gif, eventprop_adjoint.gif (prodotte da scripts/manim)
    figures/                  # output PNG di figures.py (gitignored)
    _output/                  # deck HTML + PDF (gitignored)
scripts/manim/
  lif_spike.py                # hero #1: membrana LIF carica→spike→reset → GIF
  eventprop_adjoint.py        # hero #2: forward + adjoint EventProp → GIF
tests/presentation/
  test_figures_common.py      # test della logica palette/mapping (TDD)
```

Convenzioni di progetto rispettate: build **100% locale** (niente Azure); **commit senza Co-Authored-By**; **push solo quando Azure è fermo**; risultati/figure grezzi restano in `results/` (sorgente), il deck vive in `presentation/`.

---

## FASE 0 — Toolchain e scaffolding

### Task 0.1: Installare Quarto e verificare i pacchetti Python

**Files:** nessuno (setup ambiente).

- [ ] **Step 1: Verificare cosa manca**

Run:
```bash
quarto --version || echo "QUARTO ASSENTE"
python -c "import matplotlib, numpy, pandas, PIL; print('py deps OK')"
```
Expected: `QUARTO ASSENTE` + `py deps OK` (matplotlib/numpy/pandas/Pillow sono già presenti).

- [ ] **Step 2: Installare Quarto (Windows)**

Run (PowerShell):
```powershell
winget install --id Posit.Quarto -e
```
Se `winget` non è disponibile: scaricare l'installer da https://quarto.org/docs/get-started/ ed eseguirlo.

- [ ] **Step 3: Verificare Quarto**

Run:
```bash
quarto --version
```
Expected: una versione ≥ 1.4 (es. `1.6.x`). Se `command not found`, riaprire la shell (PATH aggiornato dall'installer).

- [ ] **Step 4: Commit** (nessun file da committare; saltare — è solo ambiente)

---

### Task 0.2: Creare l'albero delle cartelle

**Files:**
- Create: `presentation/_shared/theme/`, `presentation/_shared/manim_common/`, `presentation/cf_fsnn_thesis/assets/img/`, `presentation/cf_fsnn_thesis/assets/manim/`, `presentation/cf_fsnn_thesis/figures/`, `scripts/manim/`, `tests/presentation/`

- [ ] **Step 1: Creare le directory**

Run (bash):
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN"
mkdir -p presentation/_shared/theme presentation/_shared/manim_common \
         presentation/cf_fsnn_thesis/assets/img presentation/cf_fsnn_thesis/assets/manim \
         presentation/cf_fsnn_thesis/figures presentation/cf_fsnn_thesis/_output \
         scripts/manim tests/presentation
```

- [ ] **Step 2: Aggiungere il `.gitignore` degli output**

Create `presentation/cf_fsnn_thesis/.gitignore`:
```
figures/
_output/
.quarto/
```

- [ ] **Step 3: Verificare**

Run: `find presentation -type d | sort`
Expected: le 6 directory create sopra.

- [ ] **Step 4: Commit**

```bash
git add presentation/cf_fsnn_thesis/.gitignore
git commit -m "chore: scaffold presentation/ folders for cf_fsnn_thesis"
```

---

### Task 0.3: Tema reveal.js + `_quarto.yml` con profili reduced/full

**Files:**
- Create: `presentation/_shared/theme/cf_theme.scss`
- Create: `presentation/cf_fsnn_thesis/_quarto.yml`

- [ ] **Step 1: Scrivere il tema** (`presentation/_shared/theme/cf_theme.scss`)

```scss
/*-- scss:defaults --*/
$font-size-root: 30px;
$presentation-font-size-root: 30px;
$presentation-heading-font-weight: 600;
$body-color: #111111;
$link-color: #0072B2;

/*-- scss:rules --*/
.reveal .slides section { text-align: left; }
.reveal h2 { font-size: 1.25em; line-height: 1.2; margin-bottom: 0.4em; }
.reveal .assertion { font-size: 1.15em; font-weight: 600; }
.reveal figure img { max-height: 70vh; width: auto; display: block; margin: 0 auto; }
.reveal .progress-dots { position: fixed; top: 12px; right: 16px; font-size: 0.5em; color: #888; }
.reveal .accent { color: #009E73; font-weight: 600; }
```

- [ ] **Step 2: Scrivere `_quarto.yml`** (`presentation/cf_fsnn_thesis/_quarto.yml`)

```yaml
project:
  title: "CF_FSNN"

format:
  revealjs:
    theme: [default, ../_shared/theme/cf_theme.scss]
    slide-number: c/t
    incremental: false
    transition: none
    html-math-method: mathjax
    fig-align: center
    embed-resources: false

profile:
  default: reduced
  group:
    - [reduced, full]
```

- [ ] **Step 3: Smoke-test del render** (deck vuoto)

Create un `presentation/cf_fsnn_thesis/slides.qmd` minimo temporaneo:
```markdown
---
title: "CF_FSNN — smoke test"
---

## Prima slide

Funziona.
```
Run:
```bash
cd "presentation/cf_fsnn_thesis" && quarto render slides.qmd
```
Expected: crea `slides.html` senza errori.

- [ ] **Step 4: Verificare il profilo full**

Run: `cd "presentation/cf_fsnn_thesis" && quarto render slides.qmd --profile full`
Expected: render OK (nessuna slide condizionale ancora, ma il profilo è accettato).

- [ ] **Step 5: Commit**

```bash
git add presentation/_shared/theme/cf_theme.scss presentation/cf_fsnn_thesis/_quarto.yml presentation/cf_fsnn_thesis/slides.qmd
git commit -m "feat(presentation): reveal.js theme + quarto config with reduced/full profiles"
```

---

## FASE 1 — Stile condiviso + palette (TDD sulla logica)

### Task 1.1: `figures_common.py` — palette Okabe-Ito, mapping champion, stile palco

**Files:**
- Create: `presentation/_shared/figures_common.py`
- Test: `tests/presentation/test_figures_common.py`

- [ ] **Step 1: Scrivere il test che fallisce** (`tests/presentation/test_figures_common.py`)

```python
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "figures_common",
    pathlib.Path(__file__).resolve().parents[2] / "presentation/_shared/figures_common.py")
fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)

CHAMPIONS = ["Raffaello", "Leonardo", "Donatello", "Michelangelo", "Master Splinter"]

def test_all_champions_have_a_style():
    for c in CHAMPIONS:
        s = fc.champion_style(c)
        assert set(s) >= {"color", "linestyle", "marker", "label"}

def test_styles_are_cvd_safe_distinct():
    # ogni champion deve differire da ogni altro su ALMENO 2 canali su 3
    styles = {c: fc.champion_style(c) for c in CHAMPIONS}
    keys = list(styles)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = styles[keys[i]], styles[keys[j]]
            diff = sum(a[k] != b[k] for k in ("color", "linestyle", "marker"))
            assert diff >= 2, f"{keys[i]} vs {keys[j]} troppo simili ({diff} canali diversi)"

def test_palette_is_okabe_ito():
    assert fc.OKABE_ITO["blue"] == "#0072B2"
    assert fc.OKABE_ITO["vermillion"] == "#D55E00"

def test_unknown_champion_raises():
    import pytest
    with pytest.raises(KeyError):
        fc.champion_style("Nonexistent")
```

- [ ] **Step 2: Eseguire il test → deve fallire**

Run: `python -m pytest tests/presentation/test_figures_common.py -v`
Expected: FAIL (`figures_common.py` non esiste / attributi mancanti).

- [ ] **Step 3: Implementare** (`presentation/_shared/figures_common.py`)

```python
"""Stile condiviso per le figure della presentazione CF_FSNN (palco + color-blind safe)."""
import matplotlib.pyplot as plt
import pandas as pd

OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7",
}
ACCENT = OKABE_ITO["green"]  # un solo accento = "questo è il nostro risultato / guarda qui"

# identità-champion: colore Okabe-Ito vicino al carattere del report + tratteggio + marker (ridondanza CVD)
_CHAMPION_STYLE = {
    "Raffaello":       dict(color=OKABE_ITO["vermillion"], linestyle="--", marker="X", label="Raffaello (BPTT)"),
    "Leonardo":        dict(color=OKABE_ITO["blue"],       linestyle="-",  marker="s", label="Leonardo (BPTT)"),
    "Donatello":       dict(color=OKABE_ITO["purple"],     linestyle="-",  marker="o", label="Donatello (EventProp)"),
    "Michelangelo":    dict(color=OKABE_ITO["orange"],     linestyle="-.", marker="^", label="Michelangelo (EventProp)"),
    "Master Splinter": dict(color=OKABE_ITO["black"],      linestyle=":",  marker="D", label="Oracolo"),
}

def champion_style(name: str) -> dict:
    return dict(_CHAMPION_STYLE[name])

def apply_stage_style() -> None:
    """rcParams per slide proiettate: font grandi, de-junk (Tufte), niente cornici superflue."""
    plt.rcParams.update({
        "figure.figsize": (10, 5.6), "figure.dpi": 140, "savefig.dpi": 140,
        "font.size": 18, "axes.titlesize": 20, "axes.labelsize": 18,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "lines.linewidth": 2.5, "lines.markersize": 9,
        "savefig.bbox": "tight", "figure.autolayout": True,
    })

def load_csv(repo_root, rel_path: str) -> pd.DataFrame:
    import pathlib
    return pd.read_csv(pathlib.Path(repo_root) / rel_path)
```

- [ ] **Step 4: Eseguire il test → deve passare**

Run: `python -m pytest tests/presentation/test_figures_common.py -v`
Expected: PASS (4 test verdi).

- [ ] **Step 5: Commit**

```bash
git add presentation/_shared/figures_common.py tests/presentation/test_figures_common.py
git commit -m "feat(presentation): shared Okabe-Ito palette + CVD-safe champion styles (tested)"
```

---

### Task 1.2: Figura worked-example — il discriminante FPGA (ρ vs accuratezza) dai CSV reali

**Files:**
- Create: `presentation/cf_fsnn_thesis/figures.py` (prima funzione + `main`)

Questa è la figura più importante (money slide 24 / discriminante 31): la usiamo come **template** per tutte le altre.

- [ ] **Step 1: Implementare `figures.py` con la prima figura**

```python
"""Rigenera/ri-stila TUTTE le figure della presentazione dai CSV reali. 100% locale."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_shared"))
import figures_common as fc
import matplotlib.pyplot as plt

REPO = pathlib.Path(__file__).resolve().parents[2]           # .../CF_FSNN
VAL = REPO / "results/evaluate/v3_TURTLE_POWER!!!"
FPGA = REPO / "results/evaluate/FPGA"
OUT = pathlib.Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

def fig_discriminant():
    """ρ(U·V) [x] vs accuratezza [y], area marker ∝ vantaggio energetico. Zona verde ρ<1 = sicura."""
    e = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    a = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/01_Accuracy/accuracy.csv")
    df = e.merge(a[["champion", "accuracy_pct"]], on="champion")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    ax.axvspan(0, 1, color=fc.OKABE_ITO["green"], alpha=0.08)          # zona contrattiva sicura
    ax.axvline(1, color="#888", linestyle="--", linewidth=1)
    for _, r in df.iterrows():
        st = fc.champion_style(r["champion"])
        ax.scatter(r["spectral_radius"], r["accuracy_pct"],
                   s=60 * r["advantage_x"], color=st["color"], marker=st["marker"],
                   edgecolor="black", linewidth=0.6, zorder=3, label=st["label"])
    ax.set_xscale("log")
    ax.set_xlabel("raggio spettrale ρ(U·V)  —  <1 = contrattivo (sicuro in fixed-point)")
    ax.set_ylabel("accuratezza identificazione (%)")
    ax.set_title("EventProp è contrattivo (ρ<1); i BPTT no")
    ax.legend(loc="lower left", frameon=False)
    fig.savefig(OUT / "discriminant.png"); plt.close(fig)

FIGURES = [fig_discriminant]

def main():
    for f in FIGURES:
        f(); print("OK", f.__name__)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Eseguire e verificare l'output**

Run: `python presentation/cf_fsnn_thesis/figures.py`
Expected: stampa `OK fig_discriminant` e crea `presentation/cf_fsnn_thesis/figures/discriminant.png`.

- [ ] **Step 3: Ispezione visiva**

Aprire `figures/discriminant.png`: 4 champion, Donatello/Michelangelo a ρ<1 (zona verde), Raffaello/Leonardo a ρ>1; marker distinti per colore+forma; testo leggibile.

- [ ] **Step 4: Commit**

```bash
git add presentation/cf_fsnn_thesis/figures.py
git commit -m "feat(presentation): figures.py + discriminant figure from real CSVs (template)"
```

---

## FASE 2 — Il resto delle figure (stesso template)

### Task 2.1: Figure dati Atto 3 (restyle Okabe-Ito dai CSV)

**Files:**
- Modify: `presentation/cf_fsnn_thesis/figures.py` (aggiungere una funzione per figura, registrarla in `FIGURES`)

Ogni figura segue il **template** di Task 1.2: `load_csv` → `apply_stage_style` → plot con `champion_style` → `savefig(OUT/...)`. Sorgenti reali (colonne verificate):

| Funzione | Slide | CSV sorgente | Cosa disegna |
|---|---|---|---|
| `fig_pareto` | 24 | `01_Accuracy/accuracy.csv` + `08_Energy_Spiking/energy.csv` | val_data/NRMSE vs stabilità/energia; punto operativo Donatello cerchiato (accento) |
| `fig_accuracy_perparam` | 25 | `01_Accuracy/accuracy.csv` | barre NRMSE per canale (v0,T,s0,a,b) × champion |
| `fig_fim` | 26 [+] | `04_Identifiability/fim.csv` | sensibilità/correlazione FIM (equifinalità) |
| `fig_safety` | 27 | `02_Safety_ClosedLoop/safety.csv` | collisione/brake-margin/TTC vs oracolo |
| `fig_plant` | 28 [+] | `07_VehicleDynamics/plant.csv` | collisione asciutto/bagnato/ghiaccio |
| `fig_string_meso` | 29 [+] | `03_StringStability/string_stability.csv` + `12_Mesoscopic/meso_summary.csv` | gain testa→coda <1 |
| `fig_macro_fd` | 29 [+] | `13_Macroscopic/macro_summary.csv` | diagramma fondamentale (Raffaello v0 gonfiato) |
| `fig_v2x` | 30 [+] | `06_V2X_Robustness/v2x.csv` | hold-last vs blind (66.67%) |
| `fig_spike_dead` | 31 | `08_Energy_Spiking/energy.csv` | spike-rate + `dead_frac` per champion |

- [ ] **Step 1..N (una per figura):** aggiungere la funzione, `python figures.py`, verificare il PNG, commit. Esempio per `fig_safety`:

```python
def fig_safety():
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/02_Safety_ClosedLoop/safety.csv")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    order = ["Raffaello", "Leonardo", "Donatello", "Michelangelo", "Master Splinter"]
    df = df.set_index("champion").loc[[c for c in order if c in df["champion"].values if False] or df.index]
    # barre di collision_rate per champion, oracolo evidenziato
    for i, c in enumerate([c for c in order if c in df.index]):
        st = fc.champion_style(c)
        ax.bar(i, df.loc[c, "collision_rate"] if "collision_rate" in df else df.loc[c].iloc[0],
               color=st["color"], edgecolor="black", linewidth=0.6, label=st["label"])
    ax.set_ylabel("tasso di collisione")
    ax.set_title("Tutti sicuri come l'oracolo")
    ax.set_xticks(range(len([c for c in order if c in df.index])))
    ax.set_xticklabels([c for c in order if c in df.index], rotation=20)
    fig.savefig(OUT / "safety.png"); plt.close(fig)
```
> **Verifica colonne prima di scrivere ogni funzione:** `head -1 "results/evaluate/v3_TURTLE_POWER!!!/<dir>/<file>.csv"` per confermare i nomi esatti delle colonne (il template sopra assume `collision_rate`; adattare al reale).

- [ ] **Step finale: Commit** dopo ogni 2-3 figure:
```bash
git add presentation/cf_fsnn_thesis/figures.py
git commit -m "feat(presentation): Act-3A data figures restyled from CSVs"
```

### Task 2.2: Figure FPGA (Atto 3B) e conceptuali (Atto 1-2)

**Files:** Modify `presentation/cf_fsnn_thesis/figures.py`

| Funzione | Slide | Sorgente | Cosa disegna |
|---|---|---|---|
| `fig_readiness_radar` | 33 | `FPGA/00_Readiness/scorecard.csv` (assi `ρ<1,Fix-pt,Sparsità,Energia,Timing,SEU`) | radar small-multiples per champion |
| `fig_resources` | 33 | `FPGA/00_Readiness/scorecard.csv` (`footprint_B`) + testo "0 DSP, <1 BRAM" | barre footprint |
| `fig_energy_ann` | 34 [+] | `FPGA/04_Energy/energy_power.csv` | SNN vs ANN (AC<MAC) |
| `fig_seu` | 36 [+] | `FPGA/07_SEU_ISO26262/seu_sensitivity.csv` | criticità per bit / degrade vs flips |
| `fig_quant` | 33 | `05_Quantization/quantization.csv` + `quant_weight_ablation.csv` | errore vs bit + QAT assorbe po2 |

**Atto 1-2 (conceptuali):** riuso delle 15 figure già pronte in `document/figures_howitworks_v3/` (rigenerabili con `python scripts/build_how_it_works_v3.py`, senza checkpoint). Copiarle in `assets/img/` e usarle dove il diagramma è già chiaro; ri-disegnare in stile palco SOLO quelle che non si leggono a proiettore. Le 2 più importanti (membrana LIF, adjoint) diventano animazioni (Fase 3).

- [ ] Per ciascuna: aggiungere funzione / copiare asset, rigenerare, verifica visiva, commit.

---

## FASE 3 — Le 2 animazioni hero (matplotlib → GIF)

### Task 3.1: Hero #1 — membrana LIF (carica → spike → reset)

**Files:**
- Create: `scripts/manim/lif_spike.py`

- [ ] **Step 1: Implementare l'animazione** (`scripts/manim/lif_spike.py`)

```python
"""Hero #1: dinamica LIF (secchio che perde) → GIF. Niente manim/ffmpeg: matplotlib + Pillow."""
import pathlib, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

def simulate(T=120, thr=1.0, leak=0.875, drive=0.35):
    V, out = 0.0, []
    for t in range(T):
        V = leak * V + drive
        spike = V >= thr
        if spike: V -= thr
        out.append((V + (thr if spike else 0), spike))
    return out

def main():
    data = simulate()
    xs = list(range(len(data)))
    fig, ax = plt.subplots(figsize=(10, 5), dpi=130)
    ax.axhline(1.0, color="#D55E00", linestyle="--", label="soglia")
    (line,) = ax.plot([], [], color="#0072B2", lw=2.5, label="potenziale V")
    spikes = ax.scatter([], [], color="#009E73", s=80, zorder=5, label="spike")
    ax.set_xlim(0, len(data)); ax.set_ylim(0, 1.4)
    ax.set_xlabel("tempo (tick)"); ax.set_ylabel("potenziale di membrana")
    ax.set_title("Il neurone LIF: un secchio che perde"); ax.legend(loc="upper right", frameon=False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)

    def frame(i):
        line.set_data(xs[:i + 1], [d[0] for d in data[:i + 1]])
        sx = [x for x, d in zip(xs[:i + 1], data[:i + 1]) if d[1]]
        sy = [1.05 for _ in sx]
        spikes.set_offsets(np.c_[sx, sy] if sx else np.empty((0, 2)))
        return line, spikes

    anim = FuncAnimation(fig, frame, frames=len(data), interval=50, blit=True)
    anim.save(OUT / "lif_spike.gif", writer=PillowWriter(fps=20))
    print("OK", OUT / "lif_spike.gif")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rendere e verificare**

Run: `python scripts/manim/lif_spike.py`
Expected: crea `presentation/cf_fsnn_thesis/assets/manim/lif_spike.gif`. Aprirla: il potenziale sale, tocca la soglia, spara (punto verde) e si resetta, ripetutamente.

- [ ] **Step 3: Commit**
```bash
git add scripts/manim/lif_spike.py
git commit -m "feat(presentation): LIF membrane hero animation (matplotlib->GIF)"
```

### Task 3.2: Hero #2 — forward + adjoint EventProp

**Files:** Create `scripts/manim/eventprop_adjoint.py`

Stesso schema di 3.1 (matplotlib FuncAnimation → GIF via PillowWriter). Contenuto: pannello sinistro = forward (spike che avanzano nel tempo, il "dirupo"); pannello destro = adjoint λ che torna all'indietro e "salta" **solo** agli istanti di spike. Salvare in `assets/manim/eventprop_adjoint.gif`.

- [ ] Implementare, `python scripts/manim/eventprop_adjoint.py`, verificare la GIF, commit.

> **Fallback già scelto:** se serve qualità tipo-Manim, `pip install manim` + ffmpeg e riscrivere queste due scene; ma la via GIF sopra è sufficiente e non richiede nuove installazioni.

---

## FASE 4 — Il deck: scheletro + slide atto per atto

### Task 4.1: Scheletro di `slides.qmd` (throughline, progress, dividers, profili)

**Files:** Modify `presentation/cf_fsnn_thesis/slides.qmd` (sostituisce lo smoke-test)

- [ ] **Step 1: Scrivere l'intestazione + le convenzioni**

```markdown
---
title: "Una rete «cerebrale» che legge la guida"
subtitle: "SNN + PINN + EventProp per identificare un controllore ACC — target FPGA"
format:
  revealjs:
    theme: [default, ../_shared/theme/cf_theme.scss]
---

## {.center}

::: {.assertion}
Una rete spiking «cerebrale» osserva un'auto e ne ricava le 5 impostazioni del suo
cruise-control — abbastanza efficiente da girare su un FPGA da ~200 €.
:::

<!-- THROUGHLINE: identico ad apertura e chiusura -->
```

- [ ] **Step 2: Definire i 3 template di slide** (commentati nel file, da riusare)

Template A — assertion-evidence con figura (slide `[C]`):
```markdown
## Il neurone LIF è un secchio che perde {data-menu-title="LIF"}

![](assets/manim/lif_spike.gif){fig-align="center"}

::: {.notes}
Analogia: si riempie, supera la linea, scatta, si svuota. Rottura: l'uscita è
tutto-o-niente; l'ampiezza non porta info, solo il *tempo*.
:::
```

Template B — slide di profondità `[+]` (appare SOLO nel profilo full, alla sua posizione):
```markdown
::: {.content-visible when-profile="full"}
## Metodo 3: STDP — apprendimento biologico locale {data-menu-title="STDP +"}

![](figures/stdp.png)

::: {.notes}
Neutro: «chi scatta insieme si lega», non supervisionato. (Il "no" per NOI è nell'Atto 2.)
:::
:::
```

Template C — divider di raccordo (tra atti / tra 3A e 3B):
```markdown
# Atto 2 — La nostra rete {.divider}

::: {.progress-dots}
● SNN · ○ rete · ○ risultati
:::
```

- [ ] **Step 3: Render di prova** (entrambi i profili)

Run:
```bash
cd "presentation/cf_fsnn_thesis" && quarto render slides.qmd && quarto render slides.qmd --profile full
```
Expected: entrambi rendono; il full ha ≥ slide del reduced.

- [ ] **Step 4: Commit**
```bash
git add presentation/cf_fsnn_thesis/slides.qmd
git commit -m "feat(presentation): slides.qmd skeleton (throughline, templates, dividers, profiles)"
```

### Task 4.2–4.6: Scrivere le slide, atto per atto (dallo storyboard §3)

**Files:** Modify `presentation/cf_fsnn_thesis/slides.qmd`

Il **contenuto di ogni slide è nello storyboard** `PRESENTATION_DESIGN.md` §3 (titolo assertion-evidence, tag `[C]/[+]`, visual, fonte). Per ciascuna slide: scegliere il template (A per `[C]`, B per `[+]`, C per i divider), incollare il titolo esatto dallo storyboard, agganciare la figura da `figures/` o `assets/`, mettere i dettagli parlati in `::: {.notes}`.

- [ ] **Task 4.2 — Cold open + Atto 1** (slide 1–13): scrivere le slide, `quarto render`, verifica che l'arco 1 sia leggibile "da zero". Commit.
- [ ] **Task 4.3 — Atto 2** (slide 14–22): schema master riusato con highlight progressivi. Commit.
- [ ] **Task 4.4 — Atto 3 apertura + 3A** (slide 23–32): Pareto money slide + comportamento. Commit.
- [ ] **Task 4.5 — Atto 3B + Chiusura** (slide 33–38): FPGA + riassunto strategico. Commit.
- [ ] **Task 4.6 — Verifica conteggi:** render reduced → contare ~25 slide; render full → 38.

Run per contare le slide (reduced): dopo `quarto render`, ispezionare `_output/slides.html` (numero di `<section`), oppure usare la slide-number in alto. Expected: reduced ~25, full 38.

> **Onestà da rispettare nelle note/slide (dallo spec §1 / inventario §E):** Pareto = trade-off non "vinciamo"; edge FPGA = ρ<1 + 0 morti + AC<MAC (non sparsità); energia = **stima** Horowitz 45 nm; una sola cifra energia per slide (worst-case ~5.11–8.38× **oppure** ~4.77–6.01×, spiegando la differenza in nota); spike "~13–21%"; state-range FPGA solo baseline.

---

## FASE 5 — Output, accessibilità, consegna

### Task 5.1: Export PDF statico (fallback proiettore)

**Files:** nessun nuovo file (config già in `_quarto.yml`)

- [ ] **Step 1: Aggiungere il format PDF** in `_quarto.yml` sotto `format:`:
```yaml
    revealjs:
      # ...esistente...
  pptx: default        # opzionale, se una commissione chiede .pptx
```
Per il PDF di reveal.js si usa la stampa del browser: `quarto render slides.qmd --to revealjs` poi aprire con `?print-pdf` e stampare, **oppure** installare `decktape`. In alternativa aggiungere un `format: beamer` non è adatto (perde le GIF). **Scelta:** PDF via `decktape` (Node) sul deck full.

- [ ] **Step 2:** `npm i -g @astefanutti/decktape` poi `decktape reveal presentation/cf_fsnn_thesis/_output/slides.html presentation/cf_fsnn_thesis/_output/slides.pdf`
Expected: `slides.pdf` (build appiattiti; per le GIF resta un frame — accettabile come fallback).

- [ ] **Step 3: Commit** (solo config; gli output sono gitignored)
```bash
git add presentation/cf_fsnn_thesis/_quarto.yml
git commit -m "feat(presentation): PDF fallback via decktape"
```

### Task 5.2: Passata di accessibilità

**Files:** nessuno (verifica)

- [ ] **Step 1: Color-blind** — le figure usano già Okabe-Ito + tratteggio + marker (Task 1.1). Aprire 2-3 figure chiave in un simulatore CVD (es. https://www.color-blindness.com/coblis-color-blindness-simulator/) e confermare che i champion restano distinguibili.
- [ ] **Step 2: Contrasto/leggibilità** — font root 30px (tema); verificare che nessun testo di figura sia <18px e che il deck si legga a distanza (zoom out del browser al 50%).
- [ ] **Step 3:** Nessun asset live: confermare che non ci sono demo/loop live (solo GIF/PNG). ✓ per costruzione.

### Task 5.3: Build finale + prova

- [ ] Render finale dei due profili; aprire il reduced e fare una prova a voce a cronometro (§ metodo). Annotare i minuti per-slide per il piano di esposizione.

---

## FASE 6 — Aggancio al resume-trail + commit finale

### Task 6.1: Agganciare la presentazione alla mappa di ripresa

**Files:**
- Modify: `document/EVENTPROP_STATUS.md` (§0 MAPPA DEI DOCUMENTI — aggiungere una riga alle "Fasi future")
- (memoria già aggiornata: `cf-fsnn-presentation-design`)

- [ ] **Step 1:** In `EVENTPROP_STATUS.md`, nella riga "Fasi future (post-FPGA)", aggiungere il rimando:
`+ document/PRESENTATION_DESIGN.md (design presentazione 3 atti, APPROVATO) + document/PRESENTATION_PLAN.md (piano build).`

- [ ] **Step 2: Commit**
```bash
git add document/EVENTPROP_STATUS.md
git commit -m "docs: wire PRESENTATION_DESIGN/PLAN into EVENTPROP_STATUS resume map"
```

### Task 6.2: Push (solo quando Azure è fermo)

- [ ] Confermare con l'utente che **Azure è fermo**, poi:
```bash
git push origin EventProp_Study
```

---

## Self-review (checklist eseguita)

**1. Copertura dello spec:**
- Macro-architettura (spina/throughline/3 atti/esempio-guida/appendice) → Fase 4 (scheletro + slide). ✓
- Scaletta 38 slide `[C]/[+]` → Task 4.2–4.6 dallo storyboard §3. ✓
- Profili reduced/full → Task 0.3 (`_quarto.yml`) + Template B (`content-visible when-profile`). ✓
- Figure dai CSV reali (Okabe-Ito) → Fase 1–2. ✓
- 2 hero → Fase 3 (matplotlib→GIF, adattato al toolchain locale). ✓
- Palette Okabe-Ito + ridondanza → Task 1.1 (testato). ✓
- PDF fallback / niente demo live → Task 5.1/5.2. ✓
- Sottocartella + `_shared` riusabile → Fase 0/1. ✓
- Lingua IT + termini EN → convenzione di scrittura in Task 4.x. ✓
- Onestà numeri (Pareto, energia, spike, FPGA=stima) → nota in Task 4.6 + inventario §E. ✓

**2. Placeholder scan:** i punti "una funzione per figura" (Task 2.1/2.2) sono espansi da un **template completo** (Task 1.2) + tabella con sorgenti CSV reali verificate; non sono placeholder ma ripetizioni del pattern. Il contenuto delle slide è nello storyboard §3 (completo), non "TBD".

**3. Coerenza dei tipi/nomi:** `figures_common.champion_style()/apply_stage_style()/load_csv()/OKABE_ITO/ACCENT` usati coerentemente in `figures.py`; percorsi `REPO/VAL/FPGA/OUT` coerenti; profili `reduced/full` coerenti tra `_quarto.yml` e i template.

> **Nota di scala:** questo piano ha molte micro-ripetizioni (una figura/slide alla volta). È deliberato: ogni figura è il template di Task 1.2 con un CSV diverso; ogni slide è un template di Task 4.1 con il titolo/figura dallo storyboard §3. Non c'è logica nuova oltre a `figures_common` e agli hero.
