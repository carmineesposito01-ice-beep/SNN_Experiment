# Presentazione CF_FSNN — Milestone (2026-07-06)

Deck di tesi **completo, finalizzato, verificato e pushato** su `main`. Questo documento è il runbook operativo: cosa esiste, come si costruisce, quale file presentare, i vincoli tecnici, i limiti noti.

## Cosa è la presentazione
Deck **Quarto → reveal.js, tema scuro**, in 3 parti: ① le reti spiking (SNN) da zero · ② la nostra rete (CF-SNN: architettura ibrida, ALIF, low-rank, ρ spettrale, ACC-IIDM, PINN, po2/STE, BPTT ed EventProp) · ③ i risultati, organizzati per **tier T0→T5** (3A comportamento fisico T0-T4, 3B idoneità FPGA T5, verdetto). Bilingue (IT + termini EN). Tono work-report, non vetrina. Contenuti dai documenti sorgente `HOW_IT_WORKS_v3` / `VALIDATION_REPORT_v3` / `FPGA_REPORT` — ogni numero tracciabile, nessuno inventato.

## Quale file presentare — DECK UNICO
La presentazione è **una sola** (il deck denso è stato eliminato il 2026-07-06). In `presentation/cf_fsnn_thesis/_output/` (git-ignored, si rigenera):

| File | Cos'è | Uso |
|---|---|---|
| **`deck_slim.html`** | 42 slide, tema scuro, entra a zoom normale | ⭐ **da presentare** (animazioni live) |
| `slides_slim.pptx` | export pptx fedele (immagini full-slide + GIF + note) | hand-off / PowerPoint |

Per aprire l'HTML serve la cartella `slides_files/` accanto. Verifica: 42 slide, nav lineare, 0 overflow (equazioni + verticale), 0 errori KaTeX/immagini.

## Sorgenti (in `presentation/cf_fsnn_thesis/`)
- **`slides_slim.qmd`** → include `_acts_slim/{act1,act2,act3a,act3b}.qmd` = **il** deck (tema `[../_shared/theme/cf_dark.scss, cf_slim.scss]`). *(Il vecchio deck denso `slides.qmd`+`_acts/` è stato rimosso: un solo sorgente, un solo render.)*
- Tema scuro `../_shared/theme/cf_dark.scss` (+ `cf_slim.scss` overlay compatto). Stile figure scure: `../_shared/figures_common_dark.py`.
- Figure dati: `figures.py` + `figs_fpga.py` → `figures/` (git-ignored, rigenerabili). Animazioni: `scripts/viz/build_*.py` + `scripts/manim/*.py` → `assets/manim/*.gif` (tracciate). Figure esterne bundlate in `assets/results/`, `assets/img/`.
- Roster intro **senza spoiler**: `figures/champions_roster_intro.png` (generatore `scripts/viz/build_champions_roster_intro.py`) sulla slide dei 4 candidati; la roster con i verdetti resta sulla slide del verdetto.
- `fit-equations.js` (via `include-after-body`): auto-scala le equazioni perché non escano dai riquadri `.eq`.

## Build (deterministico, singolo output)
Quarto NON è nel PATH bash → path completo. Da `presentation/cf_fsnn_thesis/`:
```bash
QUARTO="/c/Program Files/Quarto/bin/quarto"
"$QUARTO" render slides_slim.qmd && cp _output/slides_slim.html _output/deck_slim.html
python build_pptx.py _output/deck_slim.html   # -> _output/slides_slim.pptx (dopo il render)
```
Verifica: `python <skill>/scripts/verify_deck.py _output/deck_slim.html` (nav / overflow / eq-spill / KaTeX / 404).
**Rigenerare figure/animazioni prima del render se cambiate** (i generatori sono deterministici: RNG seedato / CSV; `md5sum` identico a doppio run).

## PPTX — attenzione
`quarto --to pptx` sul deck reveal è una **perdita totale**: produce 42 slide con testo e note ma **0 figure, 0 animazioni, nessun tema/layout** (pandoc-pptx non esprime reveal/HTML/CSS). NON usarlo come deliverable. Il pptx fedele si costruisce con **`build_pptx.py`**: screenshot full-slide di ogni slide (2×, design esatto) + le GIF reali sovrapposte sulle slide animate (PowerPoint le riproduce in slideshow) + le note. Non è testo-editabile — è il compromesso per la fedeltà del tema scuro.

## Vincoli tecnici (gotcha risolti — vedi la skill `/create-presentation`)
1. **KaTeX, non MathJax** (`html-math-method: katex`) — mathjax congelava la navigazione.
2. **Niente `###` nelle slide** — creano sotto-slide di 3° livello che bloccano `next()`. Titoli card = `[Titolo]{.card-title}`.
3. **Niente `title:` negli `{{< include >}}`** — azzerava la slide-titolo.
4. **Figure esterne bundlate** in-progetto — Quarto non riscrive i path che escono dalla root.
5. **Equazioni auto-fittate** (`fit-equations.js`) — altrimenti sforano il riquadro `.eq`.
6. **Overflow verticale**: contenuto più alto della slide viene tagliato in basso (footer spinto giù) → misurare per-slide e trimmare.
7. **Box `.eq` a backtick riflowano**: righe monospace consecutive senza riga vuota si uniscono e vanno a capo → separare ogni riga con una riga vuota (paragrafo), tenerle corte.

## Stato di qualità (verificato con Playwright)
- **42 slide**, navigazione lineare integra, 0 freeze, 0 errori JS/KaTeX, 0 immagini rotte.
- Layout: 0 equazioni fuori dai box, 0 overflow verticale, 0 sovrapposizioni.
- Correttezza: contenuti tracciati ai documenti sorgente; audit adversariale storico (4 errori fattuali corretti: ghiaccio 63.70%, eccezione po2 = Raffaello, spike-rate ~13-21%, ranking FIM s0/T). Slide tecniche rifinite 2026-07-06 con i fatti dal codice (a_CAH ch12 Eq.12.35, surrogato σ' γ=1, adjoint EventProp, dati quant reali).
- **Determinismo**: tutti i generatori figure/animazioni producono output byte-identico a doppio run.

## La skill riusabile
Tutto il know-how è distillato nella skill **`/create-presentation`** (`~/.claude/skills/create-presentation/`): flusso guidato in 5 fasi, i gotcha (inclusi overflow verticale + reflow `.eq`), i pattern di chiarezza (equazioni etichettate + bullet colorati), i principi per le animazioni (un concetto, niente moto senza significato, spiegare la direzione, moto continuo, intro senza spoiler), il determinismo, la consolidazione a deck unico, l'export pptx (`scripts/build_pptx.py`), i template e lo script di verifica Playwright. Usarla per le prossime presentazioni.
