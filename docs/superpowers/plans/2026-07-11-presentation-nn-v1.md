# Presentation_NN v1 — Implementation Plan (nuovo deck NN-first)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire la **prima bozza (v1)** di una nuova presentazione Quarto+reveal.js `presentation/cf_fsnn_nn/`, riordinata sullo storyboard a 32 slide, riusando i blocchi del deck esistente + le figure dei 3 report, con placeholder per logo/illustrazioni/4 animazioni nuove.

**Architecture:** Nuovo progetto Quarto **affiancato** che riusa il tema condiviso `presentation/_shared/theme/cf_dark.scss`. Master `slides_nn.qmd` = front-matter + 7 include di file-atto in `_acts_nn/`. Le slide riusate si **copiano** dai `_acts_slim/*.qmd` esistenti (fonte stabile nel repo); le ~10 slide nuove/merge hanno markup completo qui sotto. Asset (`assets/` tracciati) e `figures/` (generate, prese dal working-tree di `main`) copiati e **committati** → deck autonomo, renderizzabile senza pipeline Python.

**Tech Stack:** Quarto 1.9.38 (reveal.js), tema SCSS `cf_dark`, KaTeX. Nessun Python richiesto in v1 (figure riusate as-is).

**Spec:** `docs/superpowers/specs/2026-07-11-presentation-nn-design.md`.

---

## Convenzioni (valide per tutti i task)

- **Directory di lavoro:** `presentation/cf_fsnn_nn/` (dentro il worktree `.worktrees/Presentation_NN`).
- **Render / verifica build:** da `presentation/cf_fsnn_nn/` → `quarto render slides_nn.qmd`; atteso exit 0 e `_output/slides_nn.html` prodotto.
- **Root working-tree di main** (per copiare le figure generate): due livelli sopra il worktree →
  `../../presentation/cf_fsnn_thesis/figures/` (percorso relativo da `presentation/cf_fsnn_nn/`:
  `../cf_fsnn_thesis/figures/` **non** basta perché nel worktree quella dir è gitignored/assente; usare il root:
  `../../../presentation/cf_fsnn_thesis/figures/`). **Percorso assoluto sicuro:**
  `D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/presentation/cf_fsnn_thesis/figures/`.
- **Commit:** conventional, **senza `Co-Authored-By`**. Push su `Presentation_NN` solo alla fine (Task 9).
- **Gotcha reveal/Quarto (obbligatori):** KaTeX (già default) · **niente `###` dentro le `.card`** · niente `title:""` negli include · tutte le figure **bundlate** dentro `cf_fsnn_nn/` (mai riferimenti fuori dal progetto).
- **Classi note del tema** (usarle identiche): `.divider`, `.act1/.act2/.act3`, `.twocol`, `.vis`, `.side`, `.explain`, `.eq`, `.math`, `.card`, `.card-title`, `.threecol`, `.footerbar`, `.notes`, `.pill`, `.accent`, `.progress-dots`.
- **Copia di una slide riusata:** aprire il file sorgente indicato, copiare il blocco che inizia con l'heading `## <titolo esatto>` **fino** all'heading successivo (escluso), incollarlo nel file-atto di destinazione, applicare le adattazioni indicate. I percorsi `assets/...` e `figures/...` **restano invariati** (stessa struttura copiata in Task 2).

---

## File Structure

```
presentation/cf_fsnn_nn/
  _quarto.yml               # Task 1 — copia di cf_fsnn_thesis/_quarto.yml + logo placeholder
  slides_nn.qmd             # Task 1 — master: front-matter + 7 include
  cf_slim.scss              # Task 1 — copia di cf_fsnn_thesis/cf_slim.scss
  fit-equations.js          # Task 1 — copia di cf_fsnn_thesis/fit-equations.js
  .gitignore                # Task 1 — ignora _output/ .quarto/ __pycache__/  (NON figures/)
  assets/                   # Task 2 — copia di cf_fsnn_thesis/assets/ (img, manim, results)
    img/kineton_logo_placeholder.svg   # Task 1 — placeholder logo
  figures/                  # Task 2 — figure-risultato (da main) + eq_* dei report
  _acts_nn/
    act0_progetto.qmd       # Task 3 — s2,3,4  (s1 = title slide dal master)
    act1_snn.qmd            # Task 4 — divider + s6,7,8
    act2_rete.qmd           # Task 5 — divider + s9,10,11,12,13,14,15
    act3_training.qmd       # Task 6 — divider + s16,17,18,19
    act4_risultati.qmd      # Task 7 — divider + s20,21,22,23,24,25
    act5_fpga.qmd           # Task 8 — divider + s26,27,28,29,30
    act6_verdetto.qmd       # Task 9 — divider + s31,32
```

**Slide esistenti ESCLUSE dalla v1** (fuori dallo storyboard a 32 slide; disponibili per la rifinitura, da segnalare all'utente): `Modello Fisico — ACC-IIDM` (×2), `T4 · Identificabilità sloppy`, `T4 · Fisher`, `T5 · Neuroni morti e saturi`, `In una frase`, `Codifica neurale` (già hidden), `SNN — Training 2`, `SNN — Neurone LIF`. Da NON aggiungere in v1; elencarle nel commit finale.

---

## Task 1: Scaffold del progetto Quarto + smoke render

**Files:**
- Create: `presentation/cf_fsnn_nn/_quarto.yml`
- Create: `presentation/cf_fsnn_nn/slides_nn.qmd`
- Create: `presentation/cf_fsnn_nn/cf_slim.scss` (copia)
- Create: `presentation/cf_fsnn_nn/fit-equations.js` (copia)
- Create: `presentation/cf_fsnn_nn/.gitignore`
- Create: `presentation/cf_fsnn_nn/assets/img/kineton_logo_placeholder.svg`
- Create (stub vuoti): `presentation/cf_fsnn_nn/_acts_nn/act{0,1,2,3,4,5,6}_*.qmd`

- [ ] **Step 1: Crea la cartella e copia i file di stile invariati**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN/presentation"
mkdir -p cf_fsnn_nn/_acts_nn cf_fsnn_nn/assets/img
cp cf_fsnn_thesis/cf_slim.scss      cf_fsnn_nn/cf_slim.scss
cp cf_fsnn_thesis/fit-equations.js  cf_fsnn_nn/fit-equations.js
```

- [ ] **Step 2: Scrivi `cf_fsnn_nn/_quarto.yml`**

```yaml
project:
  output-dir: _output

format:
  revealjs:
    theme: ../_shared/theme/cf_dark.scss
    slide-number: c/t
    navigation-mode: linear
    html-math-method: katex
    fig-align: center
    embed-resources: false
    logo: assets/img/kineton_logo_placeholder.svg
    include-after-body: fit-equations.js
```

- [ ] **Step 3: Scrivi `cf_fsnn_nn/slides_nn.qmd` (master)**

```markdown
---
title: "CF-SNN — Rete spiking per il Car-Following"
subtitle: "AI-acceleration su FPGA · dai segnali V2X ai parametri di controllo"
format:
  revealjs:
    theme: [../_shared/theme/cf_dark.scss, cf_slim.scss]
---

{{< include _acts_nn/act0_progetto.qmd >}}

{{< include _acts_nn/act1_snn.qmd >}}

{{< include _acts_nn/act2_rete.qmd >}}

{{< include _acts_nn/act3_training.qmd >}}

{{< include _acts_nn/act4_risultati.qmd >}}

{{< include _acts_nn/act5_fpga.qmd >}}

{{< include _acts_nn/act6_verdetto.qmd >}}
```

- [ ] **Step 4: Scrivi `cf_fsnn_nn/.gitignore`** (nota: NON ignora `figures/`, che vogliamo committare)

```
_output/
.quarto/
/.quarto/
**/*.quarto_ipynb
__pycache__/
```

- [ ] **Step 5: Scrivi il logo placeholder `assets/img/kineton_logo_placeholder.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 64" width="240" height="64">
  <rect x="1" y="1" width="238" height="62" rx="8" fill="none" stroke="#7aa2f7" stroke-width="2" stroke-dasharray="6 4"/>
  <text x="120" y="30" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#7aa2f7" font-weight="700">KINETON</text>
  <text x="120" y="48" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#9aa5ce">logo — placeholder</text>
</svg>
```

- [ ] **Step 6: Crea i 7 file-atto come stub minimi** (una riga commento ciascuno, per far girare il render)

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN/presentation/cf_fsnn_nn/_acts_nn"
for f in act0_progetto act1_snn act2_rete act3_training act4_risultati act5_fpga act6_verdetto; do
  printf '<!-- %s — popolato nei task successivi -->\n' "$f" > "$f.qmd"
done
```

- [ ] **Step 7: Smoke render (toolchain + tema OK)**

Run: `cd presentation/cf_fsnn_nn && quarto render slides_nn.qmd`
Expected: exit 0; prodotto `_output/slides_nn.html`. La title slide mostra titolo/sottotitolo e il logo placeholder nell'angolo. Se `quarto` non è in PATH → risolvere l'installazione prima di proseguire (NON aggirare).

- [ ] **Step 8: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN"
git add presentation/cf_fsnn_nn/_quarto.yml presentation/cf_fsnn_nn/slides_nn.qmd \
        presentation/cf_fsnn_nn/cf_slim.scss presentation/cf_fsnn_nn/fit-equations.js \
        presentation/cf_fsnn_nn/.gitignore presentation/cf_fsnn_nn/assets/img/kineton_logo_placeholder.svg \
        presentation/cf_fsnn_nn/_acts_nn/*.qmd
git commit -m "feat(presentation): scaffold nuovo deck cf_fsnn_nn (Quarto+reveal, tema condiviso)"
```

---

## Task 2: Copia asset + figure + verifica integrità

**Files:**
- Create: `presentation/cf_fsnn_nn/assets/**` (da `cf_fsnn_thesis/assets/`)
- Create: `presentation/cf_fsnn_nn/figures/**` (da main + report)

- [ ] **Step 1: Copia gli asset tracciati (img/manim/results) dal deck esistente**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN/presentation"
cp -r cf_fsnn_thesis/assets/img     cf_fsnn_nn/assets/img_src && cp -r cf_fsnn_nn/assets/img_src/. cf_fsnn_nn/assets/img/ && rm -rf cf_fsnn_nn/assets/img_src
cp -r cf_fsnn_thesis/assets/manim   cf_fsnn_nn/assets/manim
cp -r cf_fsnn_thesis/assets/results cf_fsnn_nn/assets/results
```
(Nota: `assets/img/` esiste già con il logo placeholder — la copia sopra preserva il placeholder e aggiunge le img del deck.)

- [ ] **Step 2: Copia le figure-risultato generate dal working-tree di `main`**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN/presentation/cf_fsnn_nn"
mkdir -p figures
SRC="D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/presentation/cf_fsnn_thesis/figures"
for f in champions_roster_intro champions_roster accuracy_heatmap nrmse_stratified safety_delta plant string macro_fd discriminant quant energy_ann seu readiness_radar v2x fim spike_dead; do
  cp "$SRC/$f.png" figures/ 2>/dev/null || echo "MANCA: $f.png (verifica in Step 4)"
done
```

- [ ] **Step 3: Copia le figure-equazione dei report (per le slide nuove)**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN"
HOW="report/figures_howitworks_v3"; FPGA="report/figures_fpga"
cp "$HOW/eq_norm.png"   presentation/cf_fsnn_nn/figures/
cp "$HOW/eq_li.png"     presentation/cf_fsnn_nn/figures/
cp "$HOW/eq_decode.png" presentation/cf_fsnn_nn/figures/
cp "$FPGA/eq_qmn.png"                          presentation/cf_fsnn_nn/figures/
cp "$FPGA/02_FixedPoint__state_ranges.png"     presentation/cf_fsnn_nn/figures/state_ranges.png
cp "$FPGA/04_Energy__synops_split.png"         presentation/cf_fsnn_nn/figures/synops_split.png
cp "$FPGA/07_SEU_ISO26262__concept_-_cosa_sono_i_bit-flip.png" presentation/cf_fsnn_nn/figures/seu_concept.png
```

- [ ] **Step 4: Verifica integrità — ogni figura referenziata esiste**

Run (dopo aver popolato gli atti sarà più utile; qui verifica che i file copiati esistano):
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN/presentation/cf_fsnn_nn"
ls figures/ | sort
ls assets/manim/ | wc -l   # atteso ~14 gif
```
Expected: presenti almeno `champions_roster*.png, accuracy_heatmap.png, safety_delta.png, plant.png, string.png, macro_fd.png, discriminant.png, quant.png, energy_ann.png, seu.png, readiness_radar.png, v2x.png, eq_norm.png, eq_li.png, eq_decode.png, eq_qmn.png, state_ranges.png, synops_split.png, seu_concept.png`. Se un file `MANCA` → cercarlo in `report/figures_validation_v3/` o `report/figures_fpga/` (nomi in spec §5) e copiarlo col nome atteso; **non** inventare figure.

- [ ] **Step 5: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN"
git add presentation/cf_fsnn_nn/assets presentation/cf_fsnn_nn/figures
git commit -m "feat(presentation): bundle asset (manim/img) + figure-risultato ed equazioni nel nuovo deck"
```

---

## Task 3: Atto 0 — Il progetto (s2, s3, s4)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act0_progetto.qmd`

- [ ] **Step 1: Scrivi `act0_progetto.qmd`** (3 slide nuove; s1 = title slide dal master)

````markdown
## Obiettivo — parametri di car-following da segnali V2X, su FPGA

::: {.twocol}
::: {.vis}
[▶ illustrazione — placeholder]{.pill}
![](figures/v2x.png)
:::
::: {.side}
::: {.explain}
Un sistema **DSP** con **AI-acceleration** che, a bordo veicolo, genera i **5 parametri** di un modello di
car-following (**ACC-IIDM**) a partire dai **segnali V2X** — su hardware **FPGA**.
:::
::: {.eq}
segnali V2X  →  [ SNN su FPGA ]  →  `[v0, T, s0, a, b]`  →  controllo ACC
:::
:::
:::

::: {.notes}
Placeholder illustrazione: in rifinitura, schema dedicato "FPGA che riceve V2X e restituisce i 5 parametri".
:::

::: {.footerbar}
Il progetto · obiettivo
:::

## Perché una rete neurale?

::: {.threecol}
::: {.card}
[Velocità d'inferenza]{.card-title}
Un passo si calcola in **microsecondi**: mappa diretta ingresso→parametri, senza ottimizzazione iterativa online.
:::
::: {.card}
[Oltre il deterministico]{.card-title}
La natura **probabilistica** della rete abilita comportamenti diversi dal classico stimatore deterministico — si adatta a pattern di guida non catturati da regole fisse.
:::
::: {.card}
[Problema inverso appreso]{.card-title}
Impara il **mapping inverso** traiettoria→parametri dai dati, dove l'inversione analitica sarebbe mal posta.
:::
:::

::: {.footerbar}
Il progetto · perché una NN
:::

## Perché una FPGA?

::: {.threecol}
::: {.card}
[Determinismo temporale]{.card-title}
Nessun ramo dipendente dai dati → **WCET == BCET**, jitter zero. Hard-real-time by design.
:::
::: {.card}
[Basso consumo]{.card-title}
Datapath dedicato, sinapsi **po2 = shift** (0 DSP): energia proporzionale agli eventi, non al clock.
:::
::: {.card}
[Fast-prototyping]{.card-title}
Riconfigurabile in ore, non mesi: iterazione rapida rispetto all'**ASIC**, a parità di determinismo.
:::
:::

::: {.footerbar}
Il progetto · perché FPGA
:::
````

- [ ] **Step 2: Render + verifica**

Run: `cd presentation/cf_fsnn_nn && quarto render slides_nn.qmd`
Expected: exit 0; `grep -c "Perché una FPGA" _output/slides_nn.html` ≥ 1.

- [ ] **Step 3: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act0_progetto.qmd
git commit -m "feat(presentation): atto 0 — obiettivo, perché NN, perché FPGA"
```

---

## Task 4: Atto 1 — Le reti neurali (SNN) (divider + s6, s7, s8)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act1_snn.qmd`

**Manifest riuso:**

| Slide | Fonte (`_acts_slim/act1.qmd`) · heading | Adattamento |
|---|---|---|
| s7 | `## Le tre generazioni di reti neurali vivono su assi diversi {.act1}` | copia invariata |
| s8 | `## ANN vs SNN — Funzionamento {.act1}` | base; retitle → `## Confronto tra generazioni e scelta {.act1}`; footerbar → `Parte 1 · confronto e scelta`; **aggiungi** in coda il blocco `.explain` "scelta" (Step 2) |

- [ ] **Step 1: Apri `act1_snn.qmd` e scrivi il divider + s6 (nuova)**

````markdown
# Parte 1 — Le reti neurali (SNN) {.divider .act1}

## Come funziona una rete neurale {.act1}

::: {.twocol}
::: {.vis}
![](assets/img/membrane.png)
:::
::: {.side}
::: {.explain}
Un **neurone** somma ingressi pesati e applica una **non-linearità**; impilando strati la rete approssima una
funzione. L'**addestramento** regola i pesi minimizzando una perdita via discesa del gradiente.
:::
::: {.eq .math}
$$ y = \phi\!\Big(\sum_i w_i x_i + b\Big) $$
:::
:::
:::

::: {.footerbar}
Parte 1 · principio di funzionamento
:::
````

- [ ] **Step 2: Copia s7 (invariata) e s8 (base + aggiunta) dopo s6**

Copia il blocco `## Le tre generazioni...` da `_acts_slim/act1.qmd` (s7, invariato). Poi copia `## ANN vs SNN — Funzionamento {.act1}` (s8), **retitle** l'heading in `## Confronto tra generazioni e scelta {.act1}`, cambia la footerbar in `Parte 1 · confronto e scelta`, e **prima** della footerbar aggiungi:

```markdown
::: {.explain}
**La scelta.** Per un controllore automotive su FPGA — dove contano determinismo, energia e silicio, non i punti di accuratezza su GPU — la **3ª generazione (SNN)** è l'asse giusto: eventi invece di clock, accumulo invece di MAC.
:::
```

- [ ] **Step 3: Render + verifica**

Run: `quarto render slides_nn.qmd`
Expected: exit 0; `grep -c "Parte 1 — Le reti neurali" _output/slides_nn.html` ≥ 1 e `grep -c "Confronto tra generazioni" _output/slides_nn.html` ≥ 1.

- [ ] **Step 4: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act1_snn.qmd
git commit -m "feat(presentation): atto 1 — principio NN, tre generazioni, confronto+scelta"
```

---

## Task 5: Atto 2 — La nostra rete (divider + s9–s15)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act2_rete.qmd`

**Manifest riuso** (da `_acts_slim/act2.qmd` salvo nota):

| Slide | Fonte · heading | Adattamento |
|---|---|---|
| s9 | `## Approccio PINN — il processo {.act2}` | base; retitle → `## Algoritmo PINN — cos'è e perché {.act2}`; **aggiungi** blocco `.explain` "cos'è/perché" (Step 2) |
| s10 | `## Architettura {.act2}` | copia invariata |
| s12a | `## Architettura — Neurone ALIF {.act2}` | copia invariata |
| s12b | `## Architettura — Low-Rank {.act2}` | copia invariata |
| s15 | `## FPGA-Friendly — Po2 {.act2}` | base; retitle → `## Ottimizzazioni — pesi Po2 + ricorrenza {.act2}`; footerbar → `Parte 2 · ottimizzazioni`; **aggiungi** `.explain` recap ricorrenza (Step 4) |

Slide **nuove** in quest'atto: s11 (input), s13 (output), s14 (decode) — markup completo negli step.
> Nota d'onestà (per commit/rifinitura): le 2 slide `Modello Fisico — ACC-IIDM` esistenti NON sono nello storyboard e restano escluse in v1.

- [ ] **Step 1: Scrivi il divider + s9 (base PINN + aggiunta)**

Scrivi in testa ad `act2_rete.qmd`:

```markdown
# Parte 2 — La nostra rete (CF-SNN) {.divider .act2}
```

Poi copia `## Approccio PINN — il processo {.act2}` da `_acts_slim/act2.qmd`, retitle in `## Algoritmo PINN — cos'è e perché {.act2}`, e **subito dopo** il `.pill`/gif, dentro la colonna `.side`, aggiungi come primo blocco `.explain`:

```markdown
::: {.explain}
**Cos'è.** Un Physics-Informed NN: la rete non fitta i parametri (non osservabili) ma li fa passare nel modello
fisico, e allena il confronto con l'accelerazione osservata. **Perché qui:** i 5 parametri ACC-IIDM non sono
misurabili direttamente — la fisica fa da ponte e da regolarizzatore.
:::
```
(In rifinitura: animazione PINN esaustiva al posto di `pinn_loop.gif`.)

- [ ] **Step 2: Copia s10 (Architettura) invariata**, subito dopo s9.

- [ ] **Step 3: Scrivi s11 (input, nuova) e s13 (output, nuova)**

````markdown
## Architettura — Layer d'ingresso {.act2}

::: {.twocol}
::: {.vis}
![](figures/eq_norm.png)
:::
::: {.side}
::: {.explain}
I **4 segnali V2X** (gap `s`, velocità `v`, Δv, velocità leader) sono **normalizzati** e iniettati come
**corrente continua** `I = W·x` nello strato nascosto — **non** come spike. È il ponte continuo→spiking.
:::
::: {.eq .math}
$$ x_\text{norm} = \frac{x}{x_\text{scala}}, \qquad I_\text{in} = W_\text{fc}\,x_\text{norm} $$
:::
:::
:::

::: {.footerbar}
Parte 2 · layer d'ingresso
:::
````

Poi copia s12a (`## Architettura — Neurone ALIF`) e s12b (`## Architettura — Low-Rank`) invariate. Poi s13:

````markdown
## Architettura — Layer d'uscita {.act2}

::: {.twocol}
::: {.vis}
![](figures/eq_li.png)
:::
::: {.side}
::: {.explain}
**5 neuroni LI** (Leaky-Integrate, senza soglia): non sparano, **integrano** la corrente e il readout è la
loro **tensione** di membrana. Una **sigmoide** vincola ogni uscita nel suo intervallo prima del decode.
:::
::: {.eq .math}
$$ V^\text{out} \leftarrow \beta\,V^\text{out} + I, \qquad o = \sigma(V^\text{out}) \in (0,1) $$
:::
:::
:::

::: {.footerbar}
Parte 2 · layer d'uscita (LI)
:::
````

- [ ] **Step 4: Scrivi s14 (decode, nuova) e s15 (Po2 base + recap)**

s14:

````markdown
## Architettura — Decode {.act2}

::: {.twocol}
::: {.vis}
[▶ prima/dopo — placeholder]{.pill}
![](figures/eq_decode.png)
:::
::: {.side}
::: {.explain}
Il **decode** mappa le 5 uscite normalizzate `(0,1)` nel **range fisico** di ciascun parametro
`[v0, T, s0, a, b]` — un riscalamento affine per-canale. Ultimo anello prima del modello ACC-IIDM.
:::
::: {.eq .math}
$$ p_k = p_k^\text{min} + o_k\,(p_k^\text{max} - p_k^\text{min}) $$
:::
:::
:::

::: {.notes}
Placeholder: in rifinitura, visual "prima/dopo" del decode (uscita normalizzata → valore fisico).
:::

::: {.footerbar}
Parte 2 · decode (uscita → fisico)
:::
````

Poi copia `## FPGA-Friendly — Po2 {.act2}` (s15), retitle → `## Ottimizzazioni — pesi Po2 + ricorrenza {.act2}`, footerbar → `Parte 2 · ottimizzazioni`, e **prima** della footerbar aggiungi:

```markdown
::: {.explain}
**Seconda ottimizzazione: la ricorrenza low-rank.** Il feedback 32×32 (1024 molt.) è fattorizzato in `U·V`
rango-8 (512 molt.), dimezzando i moltiplicatori — e il rango-8 fa da regolarizzatore (ρ, Parte 5).
:::
```

- [ ] **Step 5: Render + verifica**

Run: `quarto render slides_nn.qmd`
Expected: exit 0; presenti gli heading `Layer d'ingresso`, `Layer d'uscita`, `Decode`, `Ottimizzazioni` (`grep -c` ≥ 1 ciascuno).

- [ ] **Step 6: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act2_rete.qmd
git commit -m "feat(presentation): atto 2 — PINN, architettura (input/hidden/output/decode), ottimizzazioni"
```

---

## Task 6: Atto 3 — Addestramento (divider + s16–s19)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act3_training.qmd`

**Manifest riuso:**

| Slide | Fonte · heading | Adattamento |
|---|---|---|
| s16 | `_acts_slim/act2.qmd` → `## Training — BPTT {.act2}` | base; retitle classe `{.act2}`→`{.act3}`; **prependi** la spiegazione "perché il backprop classico non basta" (Step 2) |
| s18 | `_acts_slim/act2.qmd` → `## Training — EventProp {.act2}` | copia; classe `{.act2}`→`{.act3}` |

Slide **nuove**: s17 (risultati BPTT), s19 (risultati EventProp).

- [ ] **Step 1: Divider + s16 (BPTT, base + prepend)**

```markdown
# Parte 3 — Addestramento {.divider .act3}
```

Copia `## Training — BPTT` da `_acts_slim/act2.qmd`, cambia la classe heading in `{.act3}`, e **come primo blocco** della colonna `.side` (prima di `.explain` esistente) inserisci:

```markdown
::: {.explain}
**Perché il backprop classico non basta.** Lo spike è un gradino: derivata nulla quasi ovunque → il gradiente
muore. Serve il **surrogato** (campana liscia nel backward) e propagare l'errore **indietro nel tempo**.
:::
```
(In rifinitura: animazione BPTT passo-passo con frecce, parallela al codice, al posto di `bptt_training.gif`.)

- [ ] **Step 2: Scrivi s17 (risultati BPTT, nuova)** — numeri reali da `VALIDATION_REPORT_v3.md`

````markdown
## BPTT — risultati {.act3}

::: {.twocol}
::: {.card}
[Risultato]{.card-title}
Accuratezza media **73%**. Migliore **Leonardo 77.53%** (NRMSE 0.225); Raffaello 69.34% (NRMSE 0.307, `v0` sbagliato a 0.499).
:::
::: {.card}
[Pro / Contro]{.card-title}

- \+ standard, robusto, largamente diffuso
- − **ρ>1** (1.16 / 2.99): espansivo → non FPGA-safe in virgola fissa
- − 10/32 **neuroni morti** · memoria ∝ durata `T`
:::
:::

::: {.explain}
BPTT ottiene reti valide sul software ma **espansive**: la ricorrenza amplifica lo stato, un problema sul silicio.
:::

::: {.footerbar}
Parte 3 · risultati BPTT
:::
````

- [ ] **Step 3: Copia s18 (EventProp)** da `_acts_slim/act2.qmd` (`## Training — EventProp`), classe → `{.act3}`.

- [ ] **Step 4: Scrivi s19 (risultati EventProp, nuova)**

````markdown
## EventProp — risultati {.act3}

::: {.twocol}
::: {.card}
[Risultato]{.card-title}
Accuratezza media **82%**. Migliore **Donatello 84.75%** (NRMSE **0.152**, la più bassa); Michelangelo 79.18% (NRMSE 0.208).
:::
::: {.card}
[Pro / Contro]{.card-title}

- \+ gradiente **esatto** · **ρ<1** (0.05 / 0.39): contrattivo → FPGA-safe
- \+ **0 neuroni morti** · memoria ∝ #spike
- − richiede ρ<1 per convergere (vincolo spettrale)
:::
:::

::: {.explain}
EventProp dà **stabilità per costruzione** (ρ<1) e la miglior identificazione: ha prodotto il candidato **Donatello**.
:::

::: {.footerbar}
Parte 3 · risultati EventProp
:::
````

- [ ] **Step 5: Render + verifica**

Run: `quarto render slides_nn.qmd`
Expected: exit 0; `grep -c "BPTT — risultati" _output/slides_nn.html` ≥ 1 e `grep -c "EventProp — risultati" _output/slides_nn.html` ≥ 1.

- [ ] **Step 6: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act3_training.qmd
git commit -m "feat(presentation): atto 3 — BPTT + risultati, EventProp + risultati (numeri reali)"
```

---

## Task 7: Atto 4 — Risultati (divider + s20–s25)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act4_risultati.qmd`

**Manifest riuso** (da `_acts_slim/act3a.qmd`, tutte invariate salvo la classe già `{.act3}`):

| Slide | Fonte · heading |
|---|---|
| s20 | `## Quattro campioni, un oracolo, nessun «migliore» assoluto {.act3}` |
| s21 | `## Come li valutiamo: sei livelli, dal reporting all'FPGA {.act3}` |
| s22 | `## T0 · Accuratezza: la mappa dei cinque parametri {.act3}` |
| s23 | `## T1 · Sicurezza: il residuo è fisica dello scenario, non la rete {.act3}` |
| s24 | `## T2 · Robustezza: plant e canale sono limiti esterni, non la rete {.act3}` |
| s25 | `## T3 · Traffico: micro → meso → macro, l'onda stop-and-go si smorza {.act3}` |

> Escluse in v1 (non nello storyboard): `T4 · Identificabilità sloppy`, `T4 · Fisher`.

- [ ] **Step 1: Scrivi il divider e copia le 6 slide in ordine**

Scrivi in testa: `# Parte 4 — Risultati {.divider .act3}` — poi copia i 6 blocchi elencati **nell'ordine s20→s25** da `_acts_slim/act3a.qmd` (salta la riga divider `# Parte 3 — I risultati` e i divider `# 3A —` del sorgente; copia solo i `##` elencati).

- [ ] **Step 2: Render + verifica**

Run: `quarto render slides_nn.qmd`
Expected: exit 0; `grep -c "Parte 4 — Risultati" _output/slides_nn.html` ≥ 1 e presenti gli heading `Accuratezza`, `Sicurezza`, `Robustezza`, `Traffico`.

- [ ] **Step 3: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act4_risultati.qmd
git commit -m "feat(presentation): atto 4 — campioni, leve, NRMSE, safety, robustezza, traffico"
```

---

## Task 8: Atto 5 — Idoneità FPGA (divider + s26–s30)

**Files:** Modify `presentation/cf_fsnn_nn/_acts_nn/act5_fpga.qmd`

**Manifest riuso** (da `_acts_slim/act3b.qmd`):

| Slide | Fonte · heading | Adattamento |
|---|---|---|
| s26 | `## T5 · Quantizzazione: come è quantizzata la rete {.act3}` | base; **aggiungi** una seconda `.vis`/riga con `figures/state_ranges.png` + `figures/eq_qmn.png` (Step 2) |
| s27 | `## T5 · Stabilità spettrale: ρ<1 tiene lo stato limitato {.act3}` | copia invariata (placeholder animazione overflow in rifinitura) |
| s28 | `## T5 · Timing: microsecondi contro una deadline di 100 ms {.act3}` | copia invariata |
| s29 | `## T5 · Energia: il vantaggio viene dall'operazione {.act3}` | copia invariata (framing report 5–8×, AC<MAC); opz. `figures/synops_split.png` in rifinitura |
| s30 | `## T5 · Robustezza ai bit-flip (SEU): TMR mirato, non totale {.act3}` | copia invariata (placeholder animazione bit-flip: `figures/seu_concept.png` disponibile) |

> Escluse in v1: `T5 · Neuroni morti e saturi`, `T5 · Fixed-point robusto (floor leak)` — disponibili per rifinitura.

- [ ] **Step 1: Divider + copia s27, s28, s29, s30 invariate**

Scrivi in testa `# Parte 5 — Idoneità FPGA {.divider .act3}`, poi copia i blocchi s27, s28, s29, s30 da `_acts_slim/act3b.qmd`.

- [ ] **Step 2: Copia s26 (quantizzazione) e aggiungi range/Qm.n**

Copia `## T5 · Quantizzazione: come è quantizzata la rete {.act3}`. Subito dopo le `.threecol` e prima della `.explain`, inserisci un blocco visivo con le due figure aggiuntive:

```markdown
::: {.twocol}
::: {.vis}
![](figures/state_ranges.png)
:::
::: {.vis}
![](figures/eq_qmn.png)
:::
:::
```
Metti s26 **come prima** slide dell'atto (prima di s27) così l'ordine è 26→27→28→29→30.

- [ ] **Step 3: Render + verifica**

Run: `quarto render slides_nn.qmd`
Expected: exit 0; `grep -c "Parte 5 — Idoneità FPGA" _output/slides_nn.html` ≥ 1; presenti `Quantizzazione`, `Stabilità spettrale`, `Timing`, `Energia`, `bit-flip`.

- [ ] **Step 4: Commit**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act5_fpga.qmd
git commit -m "feat(presentation): atto 5 — quantizzazione, rho, timing, energia, SEU"
```

---

## Task 9: Atto 6 — Verdetto + chiusura, render finale, docs

**Files:**
- Modify `presentation/cf_fsnn_nn/_acts_nn/act6_verdetto.qmd`
- Modify `document/SESSION_RESUME.md` *(nota: `document/` è fuori dallo sparse-checkout; vedi Step 5)*

**Manifest riuso** (da `_acts_slim/act3b.qmd`):

| Slide | Fonte · heading | Adattamento |
|---|---|---|
| s31 | `## Il candidato al deploy è Donatello {.act3}` | base; **aggiungi** una seconda `.vis` con `figures/readiness_radar.png` (fonde radar+verdetto) |

Slide **nuova**: s32 (chiusura).

- [ ] **Step 1: Divider + s31 (verdetto, base + radar)**

Scrivi in testa `# Verdetto {.divider .act3}`. Copia `## Il candidato al deploy è Donatello {.act3}`; dentro la `.twocol`, **sostituisci** il singolo `::: {.vis}` con due pannelli:

```markdown
::: {.vis}
![](figures/champions_roster.png)
:::
::: {.vis}
![](figures/readiness_radar.png)
:::
```
(così s31 mostra roster + radar; il resto della slide invariato.)

- [ ] **Step 2: Scrivi s32 (chiusura, nuova)**

````markdown
# Fine {.divider .act3}

::: {.explain}
Grazie dell'attenzione.

*Restiamo a disposizione per domande.*
:::
````

- [ ] **Step 3: Render finale completo + conteggio slide**

Run:
```bash
cd presentation/cf_fsnn_nn && quarto render slides_nn.qmd
grep -o 'class="[^"]*section[^"]*"' _output/slides_nn.html | wc -l   # sanity conteggio sezioni
```
Expected: exit 0, nessun warning di figura mancante; il deck apre in `_output/slides_nn.html` con l'ordine A0→Verdetto. Verifica a vista (aprendo l'HTML) che title-slide+logo, i 6 divider e le ~31 slide ci siano e lo stile combaci col deck esistente.

- [ ] **Step 4: Verifica integrità figure (nessun riferimento rotto)**

```bash
cd presentation/cf_fsnn_nn
grep -rho '!\[\](\([^)]*\))' _acts_nn/*.qmd | sed -E 's/.*\((.*)\)/\1/' | sort -u | while read p; do
  [ -f "$p" ] || echo "ROTTO: $p"
done
```
Expected: nessun output `ROTTO`. Se presente → copiare la figura mancante (Task 2, §5 spec), **non** rimuovere la slide.

- [ ] **Step 5: Aggiorna la documentazione di stato**

`document/` è **fuori** dallo sparse-checkout. Estenderlo temporaneamente e aggiungere una voce di stato:
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Presentation_NN"
git sparse-checkout add document
```
Poi in `document/SESSION_RESUME.md` aggiungi una riga di stato sotto l'header (track presentazione): *"Presentation_NN: v1 del deck NN-first assemblata (`presentation/cf_fsnn_nn/`, quarto render OK); placeholder = logo, illustrazione s2, 4 animazioni, visual decode; slide escluse per outline: ACC-IIDM×2, T4 sloppy/Fisher, morti/saturi, fixed-point-floor, 'in una frase'. Prossimo: rifinitura per-slide."* Se preferisci non toccare `document/` su questo branch, salta e riportalo solo in memoria.

- [ ] **Step 6: Commit finale + push**

```bash
git add presentation/cf_fsnn_nn/_acts_nn/act6_verdetto.qmd
git add document/SESSION_RESUME.md 2>/dev/null || true
git commit -m "feat(presentation): atto 6 — verdetto+radar, chiusura; v1 deck NN-first completa

Slide escluse per outline (disponibili in rifinitura): ACC-IIDM x2, T4 sloppy/Fisher,
morti/saturi, fixed-point-floor, 'in una frase'. Placeholder: logo, illustrazione s2,
4 animazioni nuove, visual decode."
git push -u origin Presentation_NN
```

---

## Self-review del piano (coperture spec)

- **Storyboard 32 slide:** coperte s1 (title), s2–s4 (Task 3), s6–s8 (Task 4), s9–s15 (Task 5), s16–s19 (Task 6), s20–s25 (Task 7), s26–s30 (Task 8), s31–s32 (Task 9). s5 omessa (da decisione). ✓
- **Decisioni locked:** hidden = low-rank (s12a/b, no WTA) ✓; energia framing report (s29 invariata) ✓; 4 animazioni come placeholder (s9/16/27/30) ✓; logo placeholder (Task 1) ✓; numeri s17/s19 reali dal report ✓.
- **Build approach:** nuovo progetto affiancato che riusa `_shared` (Task 1), asset+figure bundlati e committati (Task 2) ✓.
- **Onestà/omissioni:** slide esistenti fuori-outline elencate ed escluse esplicitamente (Task 5/7/8/9) ✓.
- **Placeholder scan:** i "placeholder" sono elementi di design dichiarati (logo, illustrazione, animazioni, visual decode), non lacune del piano; ogni step ha comandi/markup concreti. ✓
- **Coerenza nomi:** file-atto, heading e percorsi figura coerenti tra Task 2 (copia) e Task 3–9 (riferimenti). ✓

## Handoff d'esecuzione

Alla fine di questo documento l'orchestratore proporrà: **(1) Subagent-Driven** (un subagent per task, review tra task) o **(2) Inline** (executing-plans, checkpoint).
