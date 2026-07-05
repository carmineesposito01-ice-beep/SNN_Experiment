# Presentazione CF_FSNN — Milestone (2026-07-05)

Deck di tesi **completo, verificato e pushato** su `EventProp_Study`. Questo documento è il runbook operativo: cosa esiste, come si costruisce, quale file presentare, i vincoli tecnici, i limiti noti.

## Cosa è la presentazione
Deck **Quarto → reveal.js, tema scuro**, in 3 parti: ① le reti spiking (SNN) da zero · ② la nostra rete (architettura ibrida, ALIF, low-rank, ρ spettrale, ACC-IIDM, PINN, po2/STE, EventProp) · ③ i risultati (3A comportamento fisico, 3B idoneità FPGA, verdetto). Bilingue (IT + termini EN). Tono work-report, non vetrina. Contenuti dai documenti sorgente `HOW_IT_WORKS_v3` / `VALIDATION_REPORT_v3` / `FPGA_REPORT` — ogni numero tracciabile, nessuno inventato.

## Quale file presentare
Tutti in `presentation/cf_fsnn_thesis/_output/` (git-ignored; si rigenerano):

| File | Cos'è | Overflow verticale | Uso |
|---|---|---|---|
| **`deck_slim.html`** | ridotto, compatto | **entra** (1 slide a +18px, bordo footer) | ⭐ **da presentare** — a zoom normale entra |
| `deck_reduced.html` | denso, core | 25 slide (voluto) | riferimento esaustivo (core) |
| `deck_full.html` | denso + appendice | 28 slide (voluto) | riferimento profondo |

Denso e slim condividono figure/tema/fatti: il denso è la versione **esaustiva** (trabocca di proposito, per consultazione), lo slim è quella che **entra in slide**. Per aprirlo serve la cartella `slides_files/` accanto all'HTML.

## Sorgenti (in `presentation/cf_fsnn_thesis/`)
- `slides.qmd` → include `_acts/{act1,act2,act3a,act3b}.qmd` = deck **denso**.
- `slides_slim.qmd` → include `_acts_slim/*.qmd` = deck **slim** (tema `[cf_dark.scss, cf_slim.scss]`).
- Tema: `../_shared/theme/cf_dark.scss` (+ `cf_slim.scss` overlay compatto). Stile figure scure: `../_shared/figures_common_dark.py`.
- Figure dati: `figs_{id_safety,traffic,fpga}.py` → `figures/` (16 figure). Animazioni: `scripts/viz/build_*.py` + `scripts/manim/*.py` → `assets/manim/*.gif` (12 GIF). Figure esterne bundlate in `assets/results/` e `assets/img/`.
- `fit-equations.js` (agganciato via `include-after-body`): auto-scala le equazioni perché non escano dai riquadri.

## Build
Quarto NON è nel PATH bash → path completo. Da `presentation/cf_fsnn_thesis/`:
```bash
QUARTO="/c/Program Files/Quarto/bin/quarto"
"$QUARTO" render slides.qmd      --profile full    && cp _output/slides.html      _output/deck_full.html
"$QUARTO" render slides.qmd      --profile reduced && cp _output/slides.html      _output/deck_reduced.html
"$QUARTO" render slides_slim.qmd --profile reduced && cp _output/slides_slim.html _output/deck_slim.html
```
Verifica: `python <skill>/scripts/verify_deck.py _output/deck_slim.html` (nav / overflow / eq-spill / KaTeX / 404).

## Vincoli tecnici (gotcha risolti — vedi la skill `/create-presentation`)
1. **KaTeX, non MathJax** (`html-math-method: katex`) — mathjax congelava la navigazione.
2. **Niente `###` nelle slide** — creano sotto-slide di 3° livello che bloccano `next()`. Titoli card = `[Titolo]{.card-title}`.
3. **Niente `title:` negli `{{< include >}}`** — azzerava la slide-titolo.
4. **Figure esterne bundlate** in-progetto — Quarto non riscrive i path che escono dalla root.
5. **Equazioni auto-fittate** (`fit-equations.js`) — altrimenti sforano il riquadro `.eq`.

## Stato di qualità (verificato con Playwright)
- Navigazione: 100% navigabile, 0 freeze, 0 errori JS/KaTeX, 0 immagini rotte (tutti e 3 i deck).
- Layout: 0 equazioni fuori dai box, 0 sforamenti di contenuto dai pannelli, 0 sovrapposizioni (slim); il denso trabocca in verticale di proposito.
- Correttezza: audit adversariale vs i 3 documenti sorgente → 4 errori fattuali trovati e corretti (ghiaccio 63.70%, eccezione po2 = Raffaello, spike-rate ~13-21%, ranking FIM s0/T), 10 link malformati corretti.
- **Limite noto (leggibilità)**: alcune figure/animazioni dense (radar 4-pannelli, meso 5-heatmap, animazioni concettuali) hanno **testo interno piccolo** (etichette assi, formule) poco leggibile da proiezione. Il **messaggio e i numeri sono sempre portati dalla prosa e dai riquadri-equazione** (ridondanza voluta), quindi non compromette la chiarezza; è polish. Migliorabile ridisegnando quelle figure con meno pannelli / font più grandi.

## La skill riusabile
Tutto il know-how è stato distillato nella skill **`/create-presentation`** (`~/.claude/skills/create-presentation/`): flusso guidato in 5 fasi, i 5 gotcha, i template (tema, `_quarto.yml`, scheletri qmd, `fit-equations.js`), lo script di verifica Playwright, l'helper figure scure. Usarla per le prossime presentazioni.
