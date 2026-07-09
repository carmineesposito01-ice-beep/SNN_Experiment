# presentation/ — Deck di presentazione (Quarto + reveal.js)

La presentazione del progetto (SNN + PINN + EventProp) come slide reveal.js generate con
**Quarto**. È un deliverable **autonomo**: ha le proprie figure e non dipende dalla terna di
`report/` né da `document/figures*`.

## Struttura

| Cartella | Contenuto |
|---|---|
| `cf_fsnn_thesis/` | Il progetto Quarto della presentazione: gli "atti" (`_acts*`), i sorgenti `.qmd`, le figure e l'output renderizzato. |
| `_shared/` | Risorse comuni (tema, stili, asset condivisi). |

La presentazione è organizzata in **3 atti** (SNN / la rete / i risultati) con una versione
**slim** (deck definitivo, tema scuro). Impostazioni e design sono documentati in
`document/PRESENTATION_DESIGN.md` e `document/PRESENTATION_PLAN.md`.

## Come si renderizza

```bash
# da presentation/cf_fsnn_thesis/ (richiede Quarto installato)
quarto render
```

> Note tecniche apprese (in `document/`): usare **KaTeX** (non MathJax) per le formule, evitare
> heading `###` dentro le card, non usare `title:""` negli include, bundlare le figure esterne.
> Le animazioni concettuali sono generate con Manim (`scripts/manim/`).
